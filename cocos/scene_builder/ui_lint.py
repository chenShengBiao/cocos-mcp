"""UI-specific lint rules, separate from ``validate_scene``.

``validate_scene`` catches structural bugs (dangling __id__ refs,
Canvas-Camera missing, UI node outside a Canvas ancestor) — things that
make the scene refuse to load. This module catches *quality* issues
that build cleanly and run silently but produce bad UX:

* Touch targets below the iOS HIG / Material 48dp minimum — an AI that
  laid out a 30×30 button "looks fine" in the editor preview but is
  unclickable on a 400-dpi phone.
* Non-Default layer on a node that sits under a Canvas — layer masks
  between Camera (visibility bitmask) and node layer determine whether
  the node renders at all; a commonly-broken path.
* Label with overflow=NONE and ``enable_wrap=False`` — any real text
  that doesn't fit silently clips off the right edge.

Rules are non-fatal warnings. Callers (or the orchestrating LLM) decide
what to do with them.
"""
from __future__ import annotations

from pathlib import Path

from ._helpers import LAYER_UI_2D, _load_scene

# iOS HIG minimum touch target. Apple: 44pt. Google Material: 48dp. We
# go with the lower of the two since Cocos design units are already
# logical-pixel density-adjusted.
_MIN_TOUCH_TARGET = 44

# WCAG AA minimum contrast ratios. Per
# https://www.w3.org/TR/WCAG22/#contrast-minimum :
#   4.5:1 for normal text (< 18pt regular / < 14pt bold)
#   3.0:1 for large text (≥ 18pt regular — about 24px rendered at typical
#                          design-resolution DPI)
# Cocos font_size is in logical pixels, so we use 32 as the "large"
# threshold — that's roughly 24pt on a typical 1.33× design ratio and
# matches our own theme's body/heading/title sizes (32/48/72).
_WCAG_AA_MIN_CONTRAST_NORMAL = 4.5
_WCAG_AA_MIN_CONTRAST_LARGE = 3.0
_LARGE_TEXT_THRESHOLD = 32

# Overlap lint: flag when two same-parent buttons share more than this
# fraction of the smaller button's area. 0.25 = 25% overlap. Lower
# thresholds trigger on nearly-adjacent buttons that touch at the
# border; higher thresholds miss truly bad overlaps.
_OVERLAP_AREA_FRACTION = 0.25


def _components_on(scene: list, node_id: int) -> list[dict]:
    """All component objects attached to the node, resolved from _components refs."""
    node = scene[node_id]
    out = []
    for ref in node.get("_components", []):
        cid = ref.get("__id__") if isinstance(ref, dict) else None
        if cid is not None and 0 <= cid < len(scene):
            out.append(scene[cid])
    return out


def _find_uitransform_on_node(scene: list, node_id: int) -> dict | None:
    for cmp in _components_on(scene, node_id):
        if isinstance(cmp, dict) and cmp.get("__type__") == "cc.UITransform":
            return cmp
    return None


def _find_sprite_on_node(scene: list, node_id: int) -> dict | None:
    """Return the node's cc.Sprite component, if any. Used for contrast
    checks — we compare a label's color against its node's (or nearest
    ancestor's) sprite background."""
    for cmp in _components_on(scene, node_id):
        if isinstance(cmp, dict) and cmp.get("__type__") == "cc.Sprite":
            return cmp
    return None


def _parent_id(scene: list, node_id: int) -> int | None:
    node = scene[node_id]
    parent_ref = node.get("_parent")
    if isinstance(parent_ref, dict):
        return parent_ref.get("__id__")
    return None


def _find_button_on_node(scene: list, node_id: int) -> dict | None:
    for cmp in _components_on(scene, node_id):
        if isinstance(cmp, dict) and cmp.get("__type__") == "cc.Button":
            return cmp
    return None


def _nearest_bg_color(scene: list, node_id: int) -> dict | None:
    """Walk up from ``node_id`` looking for the nearest ancestor whose
    node paints a background — either a cc.Sprite or a cc.Button whose
    normal color acts as the button's fill. Returns a ``cc.Color``-like
    dict (``{r,g,b,a}``) or None when we walk off the tree.

    Button normal color wins over an outer Sprite because a label inside
    a button is visually on the button, not on whatever surface the
    button sits on top of — otherwise the contrast lint false-positives
    on white-text-on-primary-button (label against outer bg, not button).
    """
    cur = _parent_id(scene, node_id)
    depth = 0
    while cur is not None and depth < 12:  # finite guard against cycles
        btn = _find_button_on_node(scene, cur)
        if btn is not None:
            # _N$normalColor is the serialized fill color used when
            # transition=COLOR; for SCALE transition the value still
            # exists and represents the intended fill at rest.
            nc = btn.get("_N$normalColor")
            if isinstance(nc, dict):
                return nc
        sprite = _find_sprite_on_node(scene, cur)
        if sprite is not None:
            color = sprite.get("_color")
            if isinstance(color, dict):
                return color
        cur = _parent_id(scene, cur)
        depth += 1
    return None


def _color_to_srgb(color: dict) -> tuple[float, float, float]:
    """cc.Color dict (r, g, b channel ints 0-255) → sRGB tuple 0-1."""
    return (
        max(0, min(255, color.get("r", 0))) / 255,
        max(0, min(255, color.get("g", 0))) / 255,
        max(0, min(255, color.get("b", 0))) / 255,
    )


def _relative_luminance(srgb: tuple[float, float, float]) -> float:
    """WCAG 2.2 relative luminance formula. Operates on linear-space
    color, so we have to un-gamma the sRGB components first."""
    def _linearize(c: float) -> float:
        # https://www.w3.org/TR/WCAG22/#dfn-relative-luminance
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_linearize(c) for c in srgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(c1: dict, c2: dict) -> float:
    """WCAG contrast ratio — always ≥ 1. 4.5:1 is the AA min for
    normal text; 3:1 for large text."""
    L1 = _relative_luminance(_color_to_srgb(c1))
    L2 = _relative_luminance(_color_to_srgb(c2))
    lighter, darker = max(L1, L2), min(L1, L2)
    return (lighter + 0.05) / (darker + 0.05)


def _node_bbox_local(scene: list, node_id: int) -> tuple[float, float, float, float] | None:
    """Return the (min_x, min_y, max_x, max_y) local-space bounding box
    of the node's UITransform, centered on its _lpos. Anchor-aware —
    default anchor (0.5, 0.5) means bbox straddles the node position.

    Returns None if the node lacks a UITransform (no visible extent)."""
    node = scene[node_id]
    uit = _find_uitransform_on_node(scene, node_id)
    if uit is None:
        return None
    size = uit.get("_contentSize") or {}
    w, h = size.get("width", 0), size.get("height", 0)
    anchor = uit.get("_anchorPoint") or {}
    ax = anchor.get("x", 0.5)
    ay = anchor.get("y", 0.5)
    lpos = node.get("_lpos") or {}
    px = lpos.get("x", 0)
    py = lpos.get("y", 0)
    return (px - ax * w, py - ay * h, px + (1 - ax) * w, py + (1 - ay) * h)


def _bbox_overlap_area(a: tuple[float, float, float, float],
                      b: tuple[float, float, float, float]) -> float:
    """Axis-aligned bounding-box intersection area. Returns 0 when
    they don't overlap."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])


def lint_ui(scene_path: str | Path) -> dict:
    """Walk the scene and report UI-quality issues.

    Returns::

        {
          "ok": bool,                  # True iff warnings is empty
          "scene_path": str,
          "warnings": [
            {"rule": str, "node_id": int, "node_name": str, "message": str}
          ],
        }

    Rules are intentionally small and actionable. Skip structural
    issues — those belong in validate_scene.
    """
    scene = _load_scene(scene_path)
    warnings: list[dict] = []

    for i, obj in enumerate(scene):
        if not isinstance(obj, dict):
            continue
        if obj.get("__type__") != "cc.Node":
            continue
        node_name = obj.get("_name", "?")

        components = _components_on(scene, i)
        has_button = any(c.get("__type__") == "cc.Button" for c in components)
        label_cmp = next((c for c in components if c.get("__type__") == "cc.Label"), None)
        uit = _find_uitransform_on_node(scene, i)

        # ---- Rule: button too small for touch ----
        if has_button and uit is not None:
            content_size = uit.get("_contentSize") or {}
            w = content_size.get("width", 100)
            h = content_size.get("height", 100)
            if w < _MIN_TOUCH_TARGET or h < _MIN_TOUCH_TARGET:
                warnings.append({
                    "rule": "button_touch_target",
                    "node_id": i,
                    "node_name": node_name,
                    "message": (
                        f"cc.Button on '{node_name}' has UITransform {int(w)}×{int(h)}"
                        f", below the {_MIN_TOUCH_TARGET}×{_MIN_TOUCH_TARGET} minimum "
                        "(iOS HIG / Material Design 48dp). Enlarge the UITransform."
                    ),
                })

        # ---- Rule: label with overflow=NONE risks clipping ----
        if label_cmp is not None:
            # Serialized field name: _N$overflow (Cocos convention) or overflow.
            overflow = label_cmp.get("_N$overflow", label_cmp.get("overflow", 0))
            enable_wrap = label_cmp.get("_enableWrapText",
                                        label_cmp.get("enableWrapText", False))
            text_length = len(label_cmp.get("_string", label_cmp.get("string", "")))
            if overflow == 0 and not enable_wrap and text_length > 8 and uit is not None:
                w = (uit.get("_contentSize") or {}).get("width", 100)
                # Heuristic: if text is >8 chars and UITransform width < 200,
                # almost certainly going to clip. Don't try to measure actual
                # font metrics — too brittle across font assets.
                if w < 200:
                    warnings.append({
                        "rule": "label_overflow_risk",
                        "node_id": i,
                        "node_name": node_name,
                        "message": (
                            f"cc.Label on '{node_name}' ({text_length} chars) has "
                            f"overflow=NONE + wrap=off in a {int(w)}-wide box — text "
                            "likely clips. Set overflow=SHRINK (2) or enable_wrap=True, "
                            "or widen the UITransform."
                        ),
                    })

        # ---- Rule: text/background contrast below WCAG AA ----
        if label_cmp is not None:
            label_color = label_cmp.get("_color")
            bg_color = _nearest_bg_color(scene, i)
            if isinstance(label_color, dict) and bg_color is not None:
                ratio = _contrast_ratio(label_color, bg_color)
                # Large text relaxes to AA-Large 3:1 threshold per WCAG spec.
                font_size = label_cmp.get("_fontSize", 0)
                min_ratio = (_WCAG_AA_MIN_CONTRAST_LARGE
                             if font_size >= _LARGE_TEXT_THRESHOLD
                             else _WCAG_AA_MIN_CONTRAST_NORMAL)
                if ratio < min_ratio:
                    tier = "Large" if font_size >= _LARGE_TEXT_THRESHOLD else "Normal"
                    warnings.append({
                        "rule": "contrast_too_low",
                        "node_id": i,
                        "node_name": node_name,
                        "message": (
                            f"cc.Label on '{node_name}' has contrast ratio "
                            f"{ratio:.2f}:1 against its nearest background — "
                            f"below WCAG AA {tier} minimum of {min_ratio}:1. "
                            "Pick a brighter/darker text color or change the "
                            "bg; for themed UI try color_preset='text' (high "
                            "contrast against surface/bg) or flip to "
                            "color_preset='bg' on colored variants."
                        ),
                    })

        # ---- Rule: UI layer mismatch ----
        # Nodes with UI components should be on LAYER_UI_2D (33554432) so
        # the Canvas camera renders them. A common gotcha: AI sets a
        # custom layer and the component silently doesn't draw.
        has_ui_cmp = any(
            c.get("__type__") in ("cc.Sprite", "cc.Label", "cc.Graphics",
                                  "cc.RichText", "cc.Mask", "cc.Button",
                                  "cc.ProgressBar", "cc.ScrollView",
                                  "cc.EditBox", "cc.Slider", "cc.Toggle")
            for c in components
        )
        layer = obj.get("_layer")
        if has_ui_cmp and layer is not None and layer != LAYER_UI_2D:
            warnings.append({
                "rule": "ui_layer_mismatch",
                "node_id": i,
                "node_name": node_name,
                "message": (
                    f"'{node_name}' has UI components but layer={layer} "
                    f"(expected UI_2D={LAYER_UI_2D}). UICamera's visibility "
                    "mask won't include other layers by default → component "
                    "won't render. Use cocos_set_node_layer to fix."
                ),
            })

    # ---- Rule: overlapping buttons (same parent) ----
    # Two tappable nodes stacked on top of each other produce ambiguous
    # clicks — whichever wins in render order eats the touch and the
    # other button appears dead. Cocos renders later-appended siblings
    # on top, so this is easy to do accidentally via batch_scene_ops.
    #
    # We scope the check to same-parent buttons: cross-parent overlaps
    # (e.g. dialog button on top of a HUD button) are the whole point
    # of a modal dialog, not a bug. Local-space bboxes are sufficient
    # since same-parent nodes share the transform chain.
    #
    # Skip parents with cc.Layout — the layout component repositions
    # children at runtime, so serialized _lpos values don't reflect
    # where they'll actually be drawn.
    buttons_by_parent: dict[int, list[tuple[int, str, tuple]]] = {}
    for i, obj in enumerate(scene):
        if not isinstance(obj, dict) or obj.get("__type__") != "cc.Node":
            continue
        if not any(c.get("__type__") == "cc.Button" for c in _components_on(scene, i)):
            continue
        parent = _parent_id(scene, i)
        if parent is None:
            continue
        # Parent with cc.Layout? Layout will rearrange at runtime — the
        # serialized lpos is meaningless for overlap purposes.
        if any(c.get("__type__") == "cc.Layout"
               for c in _components_on(scene, parent)):
            continue
        bbox = _node_bbox_local(scene, i)
        if bbox is None:
            continue
        buttons_by_parent.setdefault(parent, []).append(
            (i, obj.get("_name", "?"), bbox)
        )

    for parent, buttons in buttons_by_parent.items():
        for a_idx in range(len(buttons)):
            for b_idx in range(a_idx + 1, len(buttons)):
                a_id, a_name, a_bbox = buttons[a_idx]
                b_id, b_name, b_bbox = buttons[b_idx]
                overlap = _bbox_overlap_area(a_bbox, b_bbox)
                if overlap == 0:
                    continue
                smaller_area = min(_bbox_area(a_bbox), _bbox_area(b_bbox))
                if smaller_area <= 0:
                    continue
                fraction = overlap / smaller_area
                if fraction >= _OVERLAP_AREA_FRACTION:
                    warnings.append({
                        "rule": "overlapping_buttons",
                        "node_id": a_id,
                        "node_name": a_name,
                        "message": (
                            f"cc.Button '{a_name}' overlaps cc.Button '{b_name}' "
                            f"by {fraction:.0%} of the smaller's area — "
                            "touches will be ambiguous at runtime (later-appended "
                            "sibling eats the click). Move one button, shrink one, "
                            "or split them across different parents."
                        ),
                    })

    return {
        "ok": not warnings,
        "scene_path": str(scene_path),
        "warnings": warnings,
    }

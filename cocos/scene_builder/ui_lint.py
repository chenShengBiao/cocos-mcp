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

    return {
        "ok": not warnings,
        "scene_path": str(scene_path),
        "warnings": warnings,
    }

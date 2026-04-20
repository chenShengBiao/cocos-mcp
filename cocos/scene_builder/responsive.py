"""Declarative responsive-layout helpers.

Cocos Creator's ``cc.Widget`` anchoring and ``cc.Layout`` auto-arrange
both carry surprising footguns:

* ``cc.Widget._alignFlags`` is a bitmask combining six edge/axis bits
  (``top=1``, ``bottom=2``, ``left=4``, ``right=8``, ``horizCenter=16``,
  ``vertCenter=32``). "Pin top-right with a 20-px margin" becomes the
  magic number ``9`` — plus a separate write into ``_top`` / ``_right``
  — and AIs routinely invert bits, OR in the wrong constants, or pick
  ``horizCenter`` when they meant ``top`` for a vertically-centered
  column. A typo here silently anchors to the wrong edge at runtime.
* ``cc.Layout._layoutType`` / ``_resizeMode`` / ``_N$horizontalDirection``
  are integer enums with no cross-file reference; "stack children
  top-to-bottom, centered" requires remembering ``layout_type=2`` AND
  ``h_direction=1`` AND ``resize_mode=1`` together, or the children end
  up mis-aligned / collapsed / stretched unpredictably.

This module collapses those incantations into five verbs that read the
way a designer briefs them ("make this fullscreen", "anchor that to
bottom-right", "stack those vertically, centered, with lg padding"),
and reuses the design-token spacing vocab so a caller can say
``padding="lg"`` instead of materializing the pixel value themselves.

The public API deliberately stays small: five primitives that compose
into the common responsive patterns. Anything the grid-snap or
free-form positioning lets you do via ``add_widget`` / ``add_layout``
directly is still available — these helpers are ergonomic sugar, not a
replacement.
"""
from __future__ import annotations

from pathlib import Path

# cc.Widget align bitmask — exported as module constants so tests and
# advanced callers can build custom combinations without reaching into
# private knowledge.
ALIGN_TOP = 1
ALIGN_BOTTOM = 2
ALIGN_LEFT = 4
ALIGN_RIGHT = 8
ALIGN_HORIZ_CENTER = 16
ALIGN_VERT_CENTER = 32

# cc.Layout enums
_LAYOUT_TYPE_HORIZONTAL = 1
_LAYOUT_TYPE_VERTICAL = 2

# h_direction on a VERTICAL layout controls horizontal alignment of
# children inside the column. Cocos ships:
#   0 = LEFT_TO_RIGHT, 1 = RIGHT_TO_LEFT, 2 = CENTER_HORIZONTAL
# The engine reuses the same field for vertical alignment on a
# HORIZONTAL layout (v_direction), with the mirror values.
_H_DIR_LEFT = 0
_H_DIR_RIGHT = 1
_H_DIR_CENTER = 2

# On a HORIZONTAL layout, v_direction controls top/center/bottom lanes
# of children. The engine's default is 1 (BOTTOM_TO_TOP); we remap the
# user-friendly "top"/"center"/"bottom" strings to the right int below.
_V_DIR_TOP = 0
_V_DIR_BOTTOM = 1  # engine default
_V_DIR_CENTER = 2

# _resizeMode=1 = CONTAINER — children keep their size, layout resizes
# the container to fit them. This is almost always what a UI builder
# wants; the alternative (=2, CHILDREN) stretches children to fill the
# container, which makes padding/spacing behave surprisingly.
_RESIZE_MODE_CONTAINER = 1

# Valid spacing/padding token names — kept in sync with
# ``cocos.project.ui_tokens.SPACING_NAMES`` but duplicated here so an
# error message can enumerate them without importing.
_VALID_SPACING_TOKENS = ("xs", "sm", "md", "lg", "xl")

# edge string → (align_flags_bits, margin_field_names).
# margin_field_names lists the Widget fields that should be set to the
# caller's ``margin`` value; corner edges pin both adjacent margins.
_EDGE_MAP: dict[str, tuple[int, tuple[str, ...]]] = {
    "top":          (ALIGN_TOP,                    ("_top",)),
    "bottom":       (ALIGN_BOTTOM,                 ("_bottom",)),
    "left":         (ALIGN_LEFT,                   ("_left",)),
    "right":        (ALIGN_RIGHT,                  ("_right",)),
    "top-left":     (ALIGN_TOP | ALIGN_LEFT,       ("_top", "_left")),
    "top-right":    (ALIGN_TOP | ALIGN_RIGHT,      ("_top", "_right")),
    "bottom-left":  (ALIGN_BOTTOM | ALIGN_LEFT,    ("_bottom", "_left")),
    "bottom-right": (ALIGN_BOTTOM | ALIGN_RIGHT,   ("_bottom", "_right")),
}


def _resolve_gap(scene_path: str | Path, value: str | int, kind: str) -> int:
    """Resolve a spacing/padding argument to an integer pixel count.

    Accepts either a token string (``"xs"``..``"xl"``) or a raw int.
    Raises ValueError for an unknown token string so typos surface as a
    loud error rather than a silent fallback to zero.

    ``kind`` is only used in the error message ("spacing" / "padding")
    so the caller sees which argument was wrong.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        # Raw pixel count — pass straight through. Negative values are
        # nonsensical but the engine clamps them, so no guard here.
        return value
    if isinstance(value, str):
        if value not in _VALID_SPACING_TOKENS:
            raise ValueError(
                f"unknown {kind} token {value!r}. "
                f"Valid names: {list(_VALID_SPACING_TOKENS)}"
            )
        from ..project.ui_tokens import resolve_spacing
        return resolve_spacing(scene_path, value)
    raise ValueError(
        f"{kind} must be an int or one of {list(_VALID_SPACING_TOKENS)}, "
        f"got {type(value).__name__}"
    )


def _set_widget_margin(scene_path: str | Path, widget_id: int,
                       fields: tuple[str, ...], margin: int) -> None:
    """Write the margin distance into the appropriate ``_top`` /
    ``_bottom`` / ``_left`` / ``_right`` field(s) on a just-created
    Widget. We do this inline rather than re-opening via
    ``cocos_set_property`` to keep the helper one round-trip."""
    if margin == 0 or not fields:
        return
    # Late import to avoid load-time cycles with ``__init__.py``.
    from ._helpers import _load_scene, _save_scene
    s = _load_scene(scene_path)
    widget = s[widget_id]
    for f in fields:
        widget[f] = margin
    _save_scene(scene_path, s)


# ----------- public API -----------

def make_fullscreen(scene_path: str | Path, node_id: int) -> int:
    """Attach cc.Widget configured to stretch ``node_id`` across the
    entirety of its parent.

    The Widget sets all four edge-pin flags (top+bottom+left+right),
    which tells the engine to keep the node's four edges at fixed
    distances from the parent's four edges — the distances default to
    zero, so the node fills the parent exactly.

    Typical callers: background sprites, modal backdrops, full-bleed
    panels, any "this should cover everything behind it" node. Cheaper
    than setting the node's ``_contentSize`` to the parent's dimensions
    because it auto-re-stretches when the parent resizes (e.g. on a
    device rotation, or when the Canvas resizer fires).

    Returns the Widget component id.
    """
    # Late import — ``__init__.py`` re-exports from this module, so a
    # top-level import would cycle at load time.
    from . import add_widget
    flags = ALIGN_TOP | ALIGN_BOTTOM | ALIGN_LEFT | ALIGN_RIGHT  # = 15
    return add_widget(scene_path, node_id, align_flags=flags)


def anchor_to_edge(scene_path: str | Path, node_id: int, edge: str,
                   margin: int = 0) -> int:
    """Attach cc.Widget that pins ``node_id`` to a specific edge or
    corner of its parent, with an optional fixed ``margin`` offset.

    ``edge`` accepts:

      * ``"top"``, ``"bottom"``, ``"left"``, ``"right"`` — single-edge
        pin; the opposite two edges float, keeping the node's own size.
      * ``"top-left"``, ``"top-right"``, ``"bottom-left"``,
        ``"bottom-right"`` — corner pin; both adjacent edges hold the
        same ``margin`` distance.

    ``margin`` is logical pixels from the pinned edge(s). For corner
    pins it applies to BOTH adjacent edges (simpler than having callers
    pass a tuple when the vast majority of real UIs use the same gutter
    on both axes).

    Why this exists: the LLM doesn't have to memorize the bitmask
    (``top=1``, ``bottom=2``, ``left=4``, ``right=8``) AND which of
    ``_top``/``_bottom``/``_left``/``_right`` to poke for the distance —
    it just names the edge in English.

    Returns the Widget component id.
    """
    if edge not in _EDGE_MAP:
        raise ValueError(
            f"unknown edge {edge!r}. Valid edges: {sorted(_EDGE_MAP)}"
        )
    from . import add_widget
    flags, margin_fields = _EDGE_MAP[edge]
    cid = add_widget(scene_path, node_id, align_flags=flags)
    _set_widget_margin(scene_path, cid, margin_fields, margin)
    return cid


def center_in_parent(scene_path: str | Path, node_id: int,
                     horizontal: bool = True,
                     vertical: bool = True) -> int:
    """Attach cc.Widget that centers ``node_id`` within its parent.

    ``horizontal=True`` (default) enables ``horizCenter`` alignment;
    ``vertical=True`` (default) enables ``vertCenter``. Passing both
    ``False`` is nonsensical — the Widget would do nothing — so we
    raise early instead of silently attaching a no-op component.

    Use cases: loading spinners, error banners, single modal panels,
    anything where the node should stay in the middle regardless of
    parent size.

    Returns the Widget component id.
    """
    if not (horizontal or vertical):
        raise ValueError(
            "center_in_parent needs at least one of horizontal/vertical=True; "
            "disabling both would attach a Widget that does nothing."
        )
    flags = 0
    if horizontal:
        flags |= ALIGN_HORIZ_CENTER
    if vertical:
        flags |= ALIGN_VERT_CENTER
    from . import add_widget
    return add_widget(scene_path, node_id, align_flags=flags)


def stack_vertically(scene_path: str | Path, node_id: int,
                     spacing: str | int = "md",
                     padding: str | int = "lg",
                     align: str = "center") -> int:
    """Attach cc.Layout (``type=VERTICAL``) to ``node_id`` so its
    children arrange top-to-bottom in a column.

    ``spacing`` is the vertical gap between children;
    ``padding`` is the inset on all four edges of the container.
    Both accept either a design-token name (``"xs"``, ``"sm"``, ``"md"``,
    ``"lg"``, ``"xl"``) — resolved via the project's active UI theme —
    or a raw int (logical pixels, passed through verbatim).

    ``align`` controls how children line up on the horizontal axis:

      * ``"left"``   → left-edge-aligned column
      * ``"center"`` → horizontally centered (typical for menu stacks)
      * ``"right"``  → right-edge-aligned column

    Resize mode is fixed to CONTAINER so the column's height grows to
    fit its children; swap to ``add_layout`` directly if you need the
    children-resize variant.

    Returns the Layout component id.
    """
    _ALIGN_TO_H_DIR = {
        "left": _H_DIR_LEFT,
        "center": _H_DIR_CENTER,
        "right": _H_DIR_RIGHT,
    }
    if align not in _ALIGN_TO_H_DIR:
        raise ValueError(
            f"align must be 'left' | 'center' | 'right', got {align!r}"
        )
    spacing_px = _resolve_gap(scene_path, spacing, "spacing")
    padding_px = _resolve_gap(scene_path, padding, "padding")
    h_direction = _ALIGN_TO_H_DIR[align]

    from . import add_layout
    return add_layout(
        scene_path, node_id,
        layout_type=_LAYOUT_TYPE_VERTICAL,
        resize_mode=_RESIZE_MODE_CONTAINER,
        spacing_y=spacing_px,
        padding_top=padding_px, padding_bottom=padding_px,
        padding_left=padding_px, padding_right=padding_px,
        h_direction=h_direction,
    )


def stack_horizontally(scene_path: str | Path, node_id: int,
                       spacing: str | int = "md",
                       padding: str | int = "lg",
                       align: str = "top") -> int:
    """Attach cc.Layout (``type=HORIZONTAL``) to ``node_id`` so its
    children arrange left-to-right in a row.

    ``spacing`` / ``padding`` behave like ``stack_vertically``: token
    string (resolved via the project theme) or raw int.

    ``align`` controls how children line up on the vertical axis:

      * ``"top"``    → top-edge-aligned row
      * ``"center"`` → vertically centered (typical for HUD / toolbar)
      * ``"bottom"`` → bottom-edge-aligned row

    Returns the Layout component id.
    """
    _ALIGN_TO_V_DIR = {
        "top": _V_DIR_TOP,
        "center": _V_DIR_CENTER,
        "bottom": _V_DIR_BOTTOM,
    }
    if align not in _ALIGN_TO_V_DIR:
        raise ValueError(
            f"align must be 'top' | 'center' | 'bottom', got {align!r}"
        )
    spacing_px = _resolve_gap(scene_path, spacing, "spacing")
    padding_px = _resolve_gap(scene_path, padding, "padding")
    v_direction = _ALIGN_TO_V_DIR[align]

    from . import add_layout
    return add_layout(
        scene_path, node_id,
        layout_type=_LAYOUT_TYPE_HORIZONTAL,
        resize_mode=_RESIZE_MODE_CONTAINER,
        spacing_x=spacing_px,
        padding_top=padding_px, padding_bottom=padding_px,
        padding_left=padding_px, padding_right=padding_px,
        v_direction=v_direction,
    )

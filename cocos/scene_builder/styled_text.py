"""Styled typographic block — title + subtitle + divider + body paragraph.

A "heading block" is the single most frequent pattern that composes 4-6
primitive calls to get right: a title at the top of a card, a subtitle
directly underneath, an optional divider rule, and a wrapped body
paragraph below. Every composite that has any significant text content
(dialog, card, modal, about-screen) ends up rebuilding this stack by
hand, so we hoist it here.

The layout is computed bottom-up: we sum each piece's intrinsic height
(font size for labels, 2px for the divider) plus the inter-piece gaps
first, then lay them out top-down from ``total_h/2``. The whole block
reports its height back through its container UITransform so callers
can stack further content below it without guessing spacing.
"""
from __future__ import annotations

from pathlib import Path

from ..project.ui_tokens import resolve_size, resolve_spacing


_ALIGN_MAP = {"left": 0, "center": 1, "right": 2}


def add_styled_text_block(scene_path: str | Path,
                          parent_id: int,
                          title: str,
                          subtitle: str | None = None,
                          body: str | None = None,
                          width: int = 400,
                          show_divider: bool = True,
                          align: str = "center") -> dict:
    """Build a theme-aware typographic block: title, optional subtitle,
    optional horizontal divider rule, optional wrapped body paragraph.

    Exists because ~every UI panel that has more than one line of
    prose needs the same composition of heading-sized title, dim-color
    subtitle, a thin separator, then a multi-line body. Hand-assembled
    that's ten primitive calls plus the y-offset arithmetic each time;
    here it's one.

    The divider is emitted only when a body is actually present — a
    line that separates nothing is visual clutter. ``show_divider=False``
    suppresses it even with a body, for callers who want the compact
    title/subtitle/body stack without a rule.

    ``align`` applies uniformly to all three labels (title/subtitle/body).
    Mixed alignment (e.g. left title, centered body) is uncommon enough
    that forcing a second call beats widening this API.

    Returns::

        {
          "block_node_id": int,
          "title_node_id": int,
          "subtitle_node_id": int | None,
          "divider_node_id": int | None,
          "body_node_id": int | None,
        }
    """
    from . import add_label, add_node, add_sprite, add_uitransform

    if align not in _ALIGN_MAP:
        raise ValueError(
            f"align must be 'left'|'center'|'right', got {align!r}"
        )
    h_align = _ALIGN_MAP[align]

    title_size = resolve_size(scene_path, "heading")
    body_size = resolve_size(scene_path, "body")
    spacing_sm = resolve_spacing(scene_path, "sm")
    spacing_md = resolve_spacing(scene_path, "md")

    # Divider only makes sense when there's a body to divide off from
    # the heading; suppress it otherwise regardless of show_divider.
    emit_divider = bool(body) and show_divider
    divider_h = 2

    # Allocate per-piece heights up front so we can size the container
    # UITransform before creating the children (callers often Widget-
    # anchor the block and need its final dimensions).
    title_box_h = title_size + 12
    subtitle_box_h = (body_size + 8) if subtitle else 0
    # Body height: allow ~3 lines at body_size + a little breathing room
    # before overflow=RESIZE_HEIGHT (3) grows it further at runtime.
    body_box_h = (body_size * 3 + 12) if body else 0

    total_h = title_box_h
    if subtitle:
        total_h += spacing_sm + subtitle_box_h
    if emit_divider:
        # md gap above + line + md gap below — symmetric so body sits
        # visually balanced against the title stack.
        total_h += spacing_md + divider_h + spacing_md
    elif body:
        # No divider but still a body: keep a md gap so the body
        # doesn't crash into the heading stack.
        total_h += spacing_md
    if body:
        total_h += body_box_h

    block = add_node(scene_path, parent_id, "StyledTextBlock")
    add_uitransform(scene_path, block, width, total_h)

    # Top-down cursor: start at the top edge, subtract each piece's
    # own half-height to arrive at its center, then advance past the
    # remaining half plus the gap.
    cursor_y = total_h / 2

    cursor_y -= title_box_h / 2
    title_node = add_node(scene_path, block, "Title",
                          lpos=(0, cursor_y, 0))
    add_uitransform(scene_path, title_node, width, title_box_h)
    add_label(scene_path, title_node, title,
              color_preset="text", size_preset="heading",
              h_align=h_align, v_align=1, overflow=2)  # SHRINK
    cursor_y -= title_box_h / 2

    subtitle_node: int | None = None
    if subtitle:
        cursor_y -= spacing_sm
        cursor_y -= subtitle_box_h / 2
        subtitle_node = add_node(scene_path, block, "Subtitle",
                                 lpos=(0, cursor_y, 0))
        add_uitransform(scene_path, subtitle_node, width, subtitle_box_h)
        add_label(scene_path, subtitle_node, subtitle,
                  color_preset="text_dim", size_preset="body",
                  h_align=h_align, v_align=1, overflow=2)
        cursor_y -= subtitle_box_h / 2

    divider_node: int | None = None
    if emit_divider:
        cursor_y -= spacing_md
        cursor_y -= divider_h / 2
        divider_node = add_node(scene_path, block, "Divider",
                                lpos=(0, cursor_y, 0))
        add_uitransform(scene_path, divider_node, width, divider_h)
        add_sprite(scene_path, divider_node, color_preset="border")
        cursor_y -= divider_h / 2
        cursor_y -= spacing_md
    elif body:
        cursor_y -= spacing_md

    body_node: int | None = None
    if body:
        cursor_y -= body_box_h / 2
        body_node = add_node(scene_path, block, "Body",
                             lpos=(0, cursor_y, 0))
        add_uitransform(scene_path, body_node, width, body_box_h)
        add_label(scene_path, body_node, body,
                  color_preset="text", size_preset="body",
                  h_align=h_align, v_align=1,
                  overflow=3,  # RESIZE_HEIGHT — grow to fit wrapped lines
                  enable_wrap=True)

    return {
        "block_node_id": block,
        "title_node_id": title_node,
        "subtitle_node_id": subtitle_node,
        "divider_node_id": divider_node,
        "body_node_id": body_node,
    }

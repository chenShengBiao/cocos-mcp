"""Pre-assembled UI composites — dialogs, menus, HUD bars.

Each pattern is a composite of the primitive ``add_*`` helpers, wired
together with sensible defaults pulled from the project's UI theme
(via the design-token system) so that the output is visually coherent
without the AI having to pick and co-ordinate twenty separate RGBAs
and sizes.

Return shapes are intentionally rich — every node/component id the
pattern created, plus the canonical "handles" the caller is likely
to wire next (e.g. dialog buttons needing click events bound to a
script).

Animations are NOT attached here — use ``add_fade_in`` /
``add_slide_in`` from ``animation_presets`` on the top-level node
returned below for entrance motion.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..project.ui_tokens import resolve_color, resolve_size, resolve_spacing
from ._helpers import _load_scene, _save_scene


def _pick_color(scene_path: str | Path, preset: str, alpha: int = 255) -> tuple:
    return resolve_color(scene_path, preset, alpha=alpha)


def add_dialog_modal(scene_path: str | Path,
                     parent_id: int,
                     title: str,
                     body: str = "",
                     buttons: list[dict] | None = None,
                     width: int = 560,
                     height: int = 360,
                     backdrop_alpha: int = 180) -> dict:
    """Build a modal dialog: full-screen backdrop + centered panel +
    title + body + button row.

    ``buttons`` is a list of ``{"text": str, "variant": "primary"|
    "secondary"|"danger"|"ghost", "click_events": [...]? }``. Each
    entry spawns a themed button; the ``variant`` picks the
    ``color_preset`` passed to ``add_button`` so colors stay coherent
    with the active theme. ``"ghost"`` uses ``surface`` as the fill
    (a subdued cancel-style button).

    Returns::

        {
          "backdrop_node_id": int,
          "panel_node_id": int,
          "title_node_id": int,
          "body_node_id": int | None,    # None when body was empty
          "button_row_node_id": int,
          "button_ids": [{"node_id": int, "component_id": int, "text": str}, ...]
        }

    The caller wires per-button click handlers via ``cocos_link_property``
    (for script-driven buttons) or by rebuilding with ``click_events``
    in the buttons dicts.
    """
    from . import (
        add_block_input_events,
        add_button,
        add_label,
        add_layout,
        add_node,
        add_sprite,
        add_uitransform,
        add_widget,
    )

    buttons = buttons or [{"text": "OK", "variant": "primary"}]

    # [backdrop] full-screen overlay that eats touch events
    backdrop = add_node(scene_path, parent_id, "DialogBackdrop")
    add_uitransform(scene_path, backdrop, 9999, 9999)  # oversized; Widget will clamp
    add_widget(scene_path, backdrop, align_flags=45)   # top+bottom+left+right
    add_sprite(scene_path, backdrop, color=(0, 0, 0, backdrop_alpha))
    add_block_input_events(scene_path, backdrop)

    # [panel] centered content surface
    panel = add_node(scene_path, backdrop, "DialogPanel")
    add_uitransform(scene_path, panel, width, height)
    add_sprite(scene_path, panel, color_preset="surface")

    # Vertical layout on the panel: title (30%), body (flex), buttons (fixed)
    spacing_md = resolve_spacing(scene_path, "md")
    spacing_lg = resolve_spacing(scene_path, "lg")
    add_layout(scene_path, panel,
               layout_type=2,  # VERTICAL
               resize_mode=1,
               padding_top=spacing_lg, padding_bottom=spacing_lg,
               padding_left=spacing_lg, padding_right=spacing_lg,
               spacing_y=spacing_md)

    # [title] heading-sized label, text_preset color
    title_node = add_node(scene_path, panel, "Title")
    add_uitransform(scene_path, title_node, width - 2 * spacing_lg,
                    resolve_size(scene_path, "heading") + 12)
    add_label(scene_path, title_node, title,
              color_preset="text", size_preset="heading",
              h_align=1, v_align=1, overflow=2)  # SHRINK

    # [body] body-sized label with wrap
    body_node: int | None = None
    if body:
        body_node = add_node(scene_path, panel, "Body")
        add_uitransform(scene_path, body_node, width - 2 * spacing_lg, 120)
        add_label(scene_path, body_node, body,
                  color_preset="text_dim", size_preset="body",
                  h_align=1, v_align=1, overflow=3,  # RESIZE_HEIGHT
                  enable_wrap=True)

    # [button row] horizontal layout with each themed button
    row_node = add_node(scene_path, panel, "ButtonRow")
    add_uitransform(scene_path, row_node, width - 2 * spacing_lg, 64)
    add_layout(scene_path, row_node,
               layout_type=1,  # HORIZONTAL
               resize_mode=1,
               spacing_x=spacing_md)

    button_ids: list[dict] = []
    # Evenly split the row width across buttons (account for spacing)
    n = len(buttons)
    btn_w = (width - 2 * spacing_lg - spacing_md * (n - 1)) // max(n, 1)
    btn_h = 56

    for spec in buttons:
        btn_node = add_node(scene_path, row_node, f"Btn_{spec['text']}")
        add_uitransform(scene_path, btn_node, btn_w, btn_h)
        variant = spec.get("variant", "primary")
        # Map variants → token preset names. "ghost" = surface = subdued
        # cancel-style; the other three map 1:1 to semantic color names.
        preset = {
            "primary": "primary", "secondary": "secondary",
            "danger": "danger", "ghost": "surface",
        }.get(variant, "primary")
        cid = add_button(scene_path, btn_node,
                         color_preset=preset,
                         click_events=spec.get("click_events"))
        # label on the button
        label_node = add_node(scene_path, btn_node, "Label")
        add_uitransform(scene_path, label_node, btn_w - 16, btn_h - 8)
        add_widget(scene_path, label_node, align_flags=45)
        # Ghost buttons need darker text so they read on surface colour
        label_color = "text" if variant == "ghost" else "bg"
        add_label(scene_path, label_node, spec["text"],
                  color_preset=label_color, size_preset="body",
                  h_align=1, v_align=1, overflow=2)  # SHRINK
        button_ids.append({
            "node_id": btn_node, "component_id": cid, "text": spec["text"]
        })

    return {
        "backdrop_node_id": backdrop,
        "panel_node_id": panel,
        "title_node_id": title_node,
        "body_node_id": body_node,
        "button_row_node_id": row_node,
        "button_ids": button_ids,
    }


def add_main_menu(scene_path: str | Path,
                  parent_id: int,
                  title: str,
                  buttons: list[dict] | None = None,
                  button_width: int = 280,
                  button_height: int = 72) -> dict:
    """Full-screen vertical main menu: background + centered title +
    vertical button stack.

    ``buttons``: same shape as ``add_dialog_modal``'s; each produces
    a themed button in a vertical stack under the title.

    Returns::

        {
          "bg_node_id": int,
          "title_node_id": int,
          "button_stack_node_id": int,
          "button_ids": [{"node_id": int, "component_id": int, "text": str}, ...]
        }
    """
    from . import (
        add_button,
        add_label,
        add_layout,
        add_node,
        add_sprite,
        add_uitransform,
        add_widget,
    )

    buttons = buttons or [
        {"text": "Start", "variant": "primary"},
        {"text": "Settings", "variant": "ghost"},
    ]

    spacing_lg = resolve_spacing(scene_path, "lg")
    spacing_md = resolve_spacing(scene_path, "md")

    # Full-screen background with bg color
    bg = add_node(scene_path, parent_id, "MainMenuBg")
    add_uitransform(scene_path, bg, 9999, 9999)
    add_widget(scene_path, bg, align_flags=45)
    add_sprite(scene_path, bg, color_preset="bg")

    # Vertical layout container centered on screen
    layout_node = add_node(scene_path, bg, "MainMenuLayout")
    # Width derived from button width + padding; height grows with children
    add_uitransform(scene_path, layout_node, button_width + spacing_lg * 2,
                    resolve_size(scene_path, "title") + 48 + button_height * len(buttons)
                    + spacing_md * len(buttons) + spacing_lg * 2)
    add_widget(scene_path, layout_node, align_flags=18)  # horizontal+vertical center
    add_layout(scene_path, layout_node,
               layout_type=2,  # VERTICAL
               resize_mode=1,
               padding_top=spacing_lg, padding_bottom=spacing_lg,
               padding_left=spacing_lg, padding_right=spacing_lg,
               spacing_y=spacing_md)

    # [title]
    title_node = add_node(scene_path, layout_node, "Title")
    add_uitransform(scene_path, title_node, button_width,
                    resolve_size(scene_path, "title") + 12)
    add_label(scene_path, title_node, title,
              color_preset="primary", size_preset="title",
              h_align=1, v_align=1, overflow=2)  # SHRINK

    # [button stack]
    button_ids: list[dict] = []
    for spec in buttons:
        btn_node = add_node(scene_path, layout_node, f"Btn_{spec['text']}")
        add_uitransform(scene_path, btn_node, button_width, button_height)
        variant = spec.get("variant", "primary")
        preset = {
            "primary": "primary", "secondary": "secondary",
            "danger": "danger", "ghost": "surface",
        }.get(variant, "primary")
        cid = add_button(scene_path, btn_node,
                         color_preset=preset,
                         click_events=spec.get("click_events"))
        label_node = add_node(scene_path, btn_node, "Label")
        add_uitransform(scene_path, label_node, button_width - 20, button_height - 8)
        add_widget(scene_path, label_node, align_flags=45)
        label_color = "text" if variant == "ghost" else "bg"
        add_label(scene_path, label_node, spec["text"],
                  color_preset=label_color, size_preset="body",
                  h_align=1, v_align=1, overflow=2)
        button_ids.append({
            "node_id": btn_node, "component_id": cid, "text": spec["text"]
        })

    return {
        "bg_node_id": bg,
        "title_node_id": title_node,
        "button_stack_node_id": layout_node,
        "button_ids": button_ids,
    }


def add_hud_bar(scene_path: str | Path,
                parent_id: int,
                items: list[dict] | None = None,
                height: int = 80,
                side: str = "top") -> dict:
    """A horizontal HUD bar pinned to the top (or bottom) of the screen.

    ``items`` is a list of ``{"kind": "label" | "spacer",
    "text": str, "size_preset": str, "color_preset": str,
    "width": int, "align": "left"|"right"|"center"}``. ``spacer`` pads
    space between items; its ``width`` is the gap in logical pixels.

    ``side``: ``"top"`` (default) or ``"bottom"``.

    Returns::

        {
          "bar_node_id": int,
          "background_node_id": int,
          "item_node_ids": [{"text": str, "node_id": int}, ...]  # labels only
        }
    """
    from . import (
        add_label,
        add_layout,
        add_node,
        add_sprite,
        add_uitransform,
        add_widget,
    )

    items = items or [
        {"kind": "label", "text": "Score: 0", "size_preset": "body",
         "color_preset": "text", "width": 160, "align": "left"},
        {"kind": "spacer", "width": 40},
        {"kind": "label", "text": "Lv 1", "size_preset": "body",
         "color_preset": "text_dim", "width": 100, "align": "left"},
    ]

    # Align_flags for Widget: 1=top, 2=bottom, 4=left, 8=right.
    # For top bar: top + left + right = 1+4+8 = 13. Bottom bar: 2+4+8=14.
    align_flags = 13 if side == "top" else 14

    bar = add_node(scene_path, parent_id, f"HUD_{side.capitalize()}Bar")
    add_uitransform(scene_path, bar, 9999, height)
    add_widget(scene_path, bar, align_flags=align_flags)

    # Semi-transparent surface color so game content under it is still
    # partially visible — feels less heavy than opaque
    surface_rgba = _pick_color(scene_path, "surface", alpha=200)
    add_sprite(scene_path, bar, color=surface_rgba)

    spacing_md = resolve_spacing(scene_path, "md")
    add_layout(scene_path, bar,
               layout_type=1,  # HORIZONTAL
               resize_mode=1,
               padding_top=spacing_md, padding_bottom=spacing_md,
               padding_left=spacing_md, padding_right=spacing_md,
               spacing_x=spacing_md)

    item_ids: list[dict] = []
    for i, item in enumerate(items):
        kind = item.get("kind", "label")
        width = item.get("width", 100)
        if kind == "spacer":
            spacer = add_node(scene_path, bar, f"Spacer_{i}")
            add_uitransform(scene_path, spacer, width, height - 2 * spacing_md)
        elif kind == "label":
            node = add_node(scene_path, bar, f"Item_{item.get('text', i)}")
            add_uitransform(scene_path, node, width, height - 2 * spacing_md)
            # Left/right/center alignment — maps to cc.Label h_align ints
            h_align = {"left": 0, "center": 1, "right": 2}.get(
                item.get("align", "left"), 0)
            add_label(scene_path, node, item.get("text", ""),
                      color_preset=item.get("color_preset", "text"),
                      size_preset=item.get("size_preset", "body"),
                      h_align=h_align, v_align=1,
                      overflow=2)  # SHRINK
            item_ids.append({"text": item.get("text", ""), "node_id": node})
        else:
            # Unknown kind — skip instead of raising; lets callers
            # forward-compat-add new kinds (e.g. "progress") later.
            continue

    # Touching _load/_save is unnecessary here — every primitive call
    # already does its own save. The cache keeps successive calls fast.
    return {
        "bar_node_id": bar,
        "background_node_id": bar,  # backdrop and bar share the same node here
        "item_node_ids": item_ids,
    }

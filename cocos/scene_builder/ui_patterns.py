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


def add_toast(scene_path: str | Path,
              parent_id: int,
              text: str,
              duration: float = 2.0,
              position: str = "bottom",
              variant: str = "info",
              width: int = 420,
              height: int = 72,
              margin: int = 40) -> dict:
    """Transient pill-shaped notification that auto-fades.

    Three phases in one animation clip:
      1. fade-in   (0 → 255 opacity over 0.25s)
      2. hold      (stay at 255 for ``duration`` - 0.5s)
      3. fade-out  (255 → 0 over 0.25s)

    Clip plays once (WrapMode.Normal) and holds the last keyframe — the
    toast stays in-scene but invisible. To truly free memory the caller
    wraps this with a timed ``cocos_delete_node`` via a script. For most
    game UX the invisible-but-present toast is fine; they accumulate at
    most a handful per scene.

    ``variant`` maps to the theme's semantic colour for the background:
      - ``"info"`` → surface (neutral)
      - ``"success"`` / ``"warn"`` / ``"danger"`` → the matching preset
    Text always uses ``text`` (or ``bg`` for danger/warn — see body).

    Returns::

        {
          "toast_node_id": int,
          "label_node_id": int,
          "animation_component_id": int,
        }
    """
    from ..project import create_animation_clip
    from ..project.ui_tokens import _find_project_from_scene
    from . import (
        add_animation,
        add_label,
        add_node,
        add_sprite,
        add_ui_opacity,
        add_uitransform,
        add_widget,
    )

    if position not in ("top", "bottom"):
        raise ValueError(f"position must be 'top' or 'bottom', got {position!r}")
    if duration < 0.6:
        # Fade-in (0.25) + fade-out (0.25) = 0.5; need SOME hold time for
        # the message to actually be readable.
        raise ValueError(
            f"toast duration must be >= 0.6s (fade-in + fade-out + minimum hold), "
            f"got {duration}"
        )

    # variant → bg color preset. 'info' is the subtle neutral surface;
    # success/warn/danger use semantic colours so the toast *communicates*
    # severity visually without the user reading the text.
    bg_preset = {
        "info": "surface",
        "success": "success",
        "warn": "warn",
        "danger": "danger",
    }.get(variant)
    if bg_preset is None:
        raise ValueError(
            f"variant must be 'info'|'success'|'warn'|'danger', got {variant!r}"
        )
    # Info toast text uses the theme's text colour; coloured variants use
    # bg so the text reads against the saturated background (white text
    # on red/green/amber is the standard pattern).
    label_color = "text" if variant == "info" else "bg"

    # Widget align flags: bottom = 2+4+8 = 14 (bottom+left+right isn't
    # right for a centered pill; we want horizontal center + top/bottom)
    # Actually Widget works on per-edge distances. For a centered
    # horizontal pill we use alignment 2+1 = 3 (bottom+top ambiguous...)
    # Simpler approach: place via _lpos and widget only for horizontal
    # centering. Use the node's lpos directly.
    toast = add_node(scene_path, parent_id, f"Toast_{variant}",
                     lpos=(0, -260 if position == "bottom" else 260, 0))
    add_uitransform(scene_path, toast, width, height)
    # Horizontal center + pin to bottom (align 2+16 won't work — cc.Widget
    # flags are bitmask {top=1,bottom=2,left=4,right=8,horizCenter=16,
    # vertCenter=32}). Pick horizontal center + vertical distance via _lpos.
    add_widget(scene_path, toast, align_flags=16 | (2 if position == "bottom" else 1))

    # Background sprite with variant color
    add_sprite(scene_path, toast, color_preset=bg_preset)

    # Label centered on the toast
    label_node = add_node(scene_path, toast, "Label")
    add_uitransform(scene_path, label_node, width - 2 * margin, height - 16)
    add_widget(scene_path, label_node, align_flags=16 | 32)  # horiz+vert center
    add_label(scene_path, label_node, text,
              color_preset=label_color, size_preset="body",
              h_align=1, v_align=1, overflow=2)  # SHRINK

    # UIOpacity starting at 0 so the first rendered frame doesn't flash
    add_ui_opacity(scene_path, toast, opacity=0)

    # Three-phase fade clip. Times deliberately don't use sample=60's
    # frame-aligned values because we want durations in tenths, not
    # sixtieths — Cocos's interpolator handles fractional times fine.
    fade_in_end = 0.25
    fade_out_start = duration - 0.25
    keyframes = [
        {"time": 0.0, "value": 0},
        {"time": fade_in_end, "value": 255},
        {"time": fade_out_start, "value": 255},
        {"time": duration, "value": 0},
    ]

    project = _find_project_from_scene(scene_path)
    if project is None:
        raise FileNotFoundError(
            f"couldn't locate a Cocos project above {scene_path}. "
            "Toast presets need to write a .anim asset; move the scene "
            "under a project root."
        )
    clip = create_animation_clip(
        project, clip_name=f"toast_{variant}_{toast}",
        duration=duration, sample=60,
        tracks=[{"path": "", "property": "opacity", "keyframes": keyframes}],
        wrap_mode=1,  # Normal — play once and hold
    )
    anim_cid = add_animation(scene_path, toast,
                             default_clip_uuid=clip["uuid"],
                             play_on_load=True,
                             clip_uuids=[clip["uuid"]])

    return {
        "toast_node_id": toast,
        "label_node_id": label_node,
        "animation_component_id": anim_cid,
    }


def add_loading_spinner(scene_path: str | Path,
                        parent_id: int,
                        sprite_frame_uuid: str | None = None,
                        text: str | None = "Loading...",
                        icon_size: int = 80,
                        rotation_period: float = 1.0) -> dict:
    """Centered rotating icon + optional caption.

    When ``sprite_frame_uuid`` is given the icon spins continuously;
    without one, falls back to a text-only loading indicator with a
    gentle opacity pulse on the caption (via ``add_pulse``-equivalent
    opacity cycle) so the user still sees activity.

    ``rotation_period``: one full 360° revolution in seconds. Faster
    feels impatient; slower feels stuck. 1.0s is the iOS / Material
    default cadence.

    Returns::

        {
          "spinner_node_id": int,
          "icon_node_id": int | None,    # None when no sprite was given
          "label_node_id": int | None,   # None when text=None
          "rotation_component_id": int | None,
        }
    """
    from ..project import create_animation_clip
    from ..project.ui_tokens import _find_project_from_scene
    from . import (
        add_animation,
        add_label,
        add_node,
        add_sprite,
        add_uitransform,
        add_widget,
    )

    spacing_md = resolve_spacing(scene_path, "md")
    label_size = resolve_size(scene_path, "body")
    total_h = icon_size + (spacing_md + label_size if text else 0)

    # Container centered on parent via Widget
    spinner = add_node(scene_path, parent_id, "LoadingSpinner")
    add_uitransform(scene_path, spinner, max(icon_size, 240), total_h)
    add_widget(scene_path, spinner, align_flags=16 | 32)  # center both

    icon_node: int | None = None
    rotation_cid: int | None = None

    if sprite_frame_uuid is not None:
        # Icon positioned at the top of the container so the label can
        # sit below it without overlap.
        icon_node = add_node(scene_path, spinner, "Icon",
                             lpos=(0, total_h / 2 - icon_size / 2, 0))
        add_uitransform(scene_path, icon_node, icon_size, icon_size)
        add_sprite(scene_path, icon_node, sprite_frame_uuid=sprite_frame_uuid)

        # Rotation clip: 0° → -360° for visually standard clockwise
        # spin. (Cocos 2D eulerZ rotation: positive = counter-clockwise.)
        project = _find_project_from_scene(scene_path)
        if project is None:
            raise FileNotFoundError(
                f"couldn't locate a Cocos project above {scene_path}. "
                "Loading spinner needs to write a .anim asset."
            )
        clip = create_animation_clip(
            project, clip_name=f"spinner_rot_{icon_node}",
            duration=rotation_period, sample=60,
            tracks=[{
                "path": "", "property": "rotation",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": rotation_period, "value": -360},
                ],
            }],
            wrap_mode=4,  # Loop
        )
        rotation_cid = add_animation(scene_path, icon_node,
                                     default_clip_uuid=clip["uuid"],
                                     play_on_load=True,
                                     clip_uuids=[clip["uuid"]])

    label_node: int | None = None
    if text:
        # Label sits at the bottom of the container
        label_y = -total_h / 2 + label_size / 2
        label_node = add_node(scene_path, spinner, "LoadingLabel",
                              lpos=(0, label_y, 0))
        add_uitransform(scene_path, label_node, 240, label_size + 8)
        add_label(scene_path, label_node, text,
                  color_preset="text_dim", size_preset="body",
                  h_align=1, v_align=1, overflow=2)

    return {
        "spinner_node_id": spinner,
        "icon_node_id": icon_node,
        "label_node_id": label_node,
        "rotation_component_id": rotation_cid,
    }


def add_card_grid(scene_path: str | Path,
                  parent_id: int,
                  cards: list[dict],
                  columns: int = 3,
                  card_width: int = 200,
                  card_height: int = 240,
                  spacing: int = 20) -> dict:
    """Build a grid of tappable cards — level select, shop, character picker.

    ``cards`` is a list of ``{"title": str, "subtitle": str?,
    "icon_sprite_frame_uuid": str?, "variant": "primary"|"surface",
    "click_events": [...]? }``. Each card renders as:

      [ icon (top half, if sprite given) ]
      [ title (heading-sized)            ]
      [ subtitle (body-sized, dim)       ]

    Laid out manually on a 2D grid (not cc.Layout GRID, which requires
    an inspector-only ``cellSize`` field we don't expose). Grid is
    centered on ``parent_id``'s UITransform origin. ``columns`` caps
    how many cards per row; extras wrap to new rows below.

    Returns::

        {
          "grid_node_id": int,
          "cards": [
            {"node_id": int, "title_node_id": int, "subtitle_node_id": int | None,
             "icon_node_id": int | None, "button_component_id": int},
            ...
          ],
        }
    """
    from . import (
        add_button,
        add_label,
        add_node,
        add_sprite,
        add_uitransform,
    )

    if not cards:
        raise ValueError("cards must be a non-empty list")
    if columns < 1:
        raise ValueError(f"columns must be ≥ 1, got {columns}")

    # Grid container node. Its UITransform spans the full grid so callers
    # can anchor / Widget it as a single block.
    n_rows = (len(cards) + columns - 1) // columns
    grid_w = columns * card_width + (columns - 1) * spacing
    grid_h = n_rows * card_height + (n_rows - 1) * spacing

    grid = add_node(scene_path, parent_id, "CardGrid")
    add_uitransform(scene_path, grid, grid_w, grid_h)

    # Starting offset so the grid is centered on grid's own origin.
    # Card centers sit at -grid_w/2 + card_w/2 + col * (card_w + spacing)
    # and the equivalent on Y. Y grows downward in our layout so the
    # first row is at the top.
    start_x = -grid_w / 2 + card_width / 2
    start_y = grid_h / 2 - card_height / 2

    body_font = resolve_size(scene_path, "body")
    heading_font = resolve_size(scene_path, "heading")
    spacing_sm = resolve_spacing(scene_path, "sm")

    card_results: list[dict] = []

    for idx, spec in enumerate(cards):
        row = idx // columns
        col = idx % columns
        cx = start_x + col * (card_width + spacing)
        cy = start_y - row * (card_height + spacing)

        card = add_node(scene_path, grid, f"Card_{idx}",
                        lpos=(cx, cy, 0))
        add_uitransform(scene_path, card, card_width, card_height)

        # Card background. "primary" variant uses the theme primary color
        # (useful for the 'featured' card); default is surface.
        variant = spec.get("variant", "surface")
        bg_preset = "primary" if variant == "primary" else "surface"
        add_sprite(scene_path, card, color_preset=bg_preset)

        # Whole card is tappable — attach cc.Button so it gets hover /
        # press visual feedback AND the click event binding.
        btn_cid = add_button(scene_path, card,
                             color_preset=bg_preset,
                             click_events=spec.get("click_events"))

        # Icon occupies the top ~60% if provided; otherwise text takes
        # the full card.
        icon_node: int | None = None
        has_icon = bool(spec.get("icon_sprite_frame_uuid"))
        if has_icon:
            icon_h = int(card_height * 0.55)
            icon_node = add_node(scene_path, card, "Icon",
                                 lpos=(0, card_height / 2 - icon_h / 2 - 10, 0))
            add_uitransform(scene_path, icon_node, card_width - 40, icon_h - 20)
            add_sprite(scene_path, icon_node,
                       sprite_frame_uuid=spec["icon_sprite_frame_uuid"])

        # Title: heading-sized, sitting below icon (or centered if no icon).
        # Text color contrasts with the card bg — primary bg needs bg-
        # preset label; surface bg uses text preset.
        label_color = "bg" if variant == "primary" else "text"
        title_y = (-card_height / 2 + heading_font + 40) if has_icon \
            else card_height / 4
        title_node = add_node(scene_path, card, "Title",
                              lpos=(0, title_y, 0))
        add_uitransform(scene_path, title_node, card_width - 20,
                        heading_font + 12)
        add_label(scene_path, title_node, spec["title"],
                  color_preset=label_color, size_preset="heading",
                  h_align=1, v_align=1, overflow=2)  # SHRINK

        subtitle_node: int | None = None
        if spec.get("subtitle"):
            sub_y = title_y - heading_font - spacing_sm
            subtitle_node = add_node(scene_path, card, "Subtitle",
                                     lpos=(0, sub_y, 0))
            add_uitransform(scene_path, subtitle_node,
                            card_width - 20, body_font + 8)
            sub_color = "bg" if variant == "primary" else "text_dim"
            add_label(scene_path, subtitle_node, spec["subtitle"],
                      color_preset=sub_color, size_preset="body",
                      h_align=1, v_align=1, overflow=2)

        card_results.append({
            "node_id": card,
            "title_node_id": title_node,
            "subtitle_node_id": subtitle_node,
            "icon_node_id": icon_node,
            "button_component_id": btn_cid,
        })

    return {
        "grid_node_id": grid,
        "cards": card_results,
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

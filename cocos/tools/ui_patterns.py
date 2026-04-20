"""MCP tool registrations for the UI-composite patterns + animation presets.

Every tool here is a single call that produces a batch of primitive
mutations + returns a structured "what got created" dict the caller
can use to wire further behaviour (click handlers, extra labels, etc.).

The patterns themselves live in
``cocos/scene_builder/{ui_patterns,animation_presets}.py`` — these
thin wrappers exist only to publish them at the MCP layer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import scene_builder as sb

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- UI composite patterns ----------------

    @mcp.tool()
    def cocos_add_dialog_modal(scene_path: str, parent_node_id: int,
                               title: str, body: str = "",
                               buttons: list[dict] | None = None,
                               width: int = 560, height: int = 360,
                               backdrop_alpha: int = 180) -> dict:
        """Build a centered modal dialog: backdrop + panel + title + body + buttons.

        One call replaces 15+ primitive calls. Inherits colors from
        the project's UI theme (set via ``cocos_set_ui_theme``).

        ``buttons``: list of ``{"text": str, "variant": ..., "click_events": [...]?}``
        where ``variant`` is ``"primary"`` / ``"secondary"`` / ``"danger"`` /
        ``"ghost"`` (surface-colored for cancel). Defaults to one
        primary "OK" button.

        Returns all created node + component IDs so the caller can wire
        click handlers or modify individual parts later.
        """
        return sb.add_dialog_modal(scene_path, parent_node_id, title, body,
                                   buttons, width, height, backdrop_alpha)

    @mcp.tool()
    def cocos_add_main_menu(scene_path: str, parent_node_id: int,
                            title: str,
                            buttons: list[dict] | None = None,
                            button_width: int = 280,
                            button_height: int = 72) -> dict:
        """Build a full-screen vertical main menu: bg + title + stacked buttons.

        Buttons use same shape as ``cocos_add_dialog_modal``. Default is
        a "Start" (primary) + "Settings" (ghost) pair.

        Typical flow::

          scene = cocos_create_scene(...)
          cocos_set_ui_theme(project, theme="dark_game")
          cocos_add_main_menu(scene, scene["canvas_node_id"], "Flappy Bird",
                              buttons=[{"text": "Start", "variant": "primary",
                                        "click_events": [click_evt]}])
        """
        return sb.add_main_menu(scene_path, parent_node_id, title,
                                buttons, button_width, button_height)

    @mcp.tool()
    def cocos_add_toast(scene_path: str, parent_node_id: int,
                        text: str,
                        duration: float = 2.0,
                        position: str = "bottom",
                        variant: str = "info",
                        width: int = 420,
                        height: int = 72) -> dict:
        """Transient pill notification — fade in, hold, fade out.

        ``variant`` picks the background:
          - ``"info"`` → surface (neutral gray/slate)
          - ``"success"`` / ``"warn"`` / ``"danger"`` → matching semantic color
        Text uses ``text`` preset (info) or ``bg`` (colored variants) so it
        always reads against the bg.

        ``duration`` is total time including 0.25s fade-in + 0.25s fade-out.
        Minimum 0.6s (else there's no readable hold window).
        Clip plays once and holds invisible — toast stays in scene as a
        zero-opacity node.

        Returns {toast_node_id, label_node_id, animation_component_id}.
        """
        return sb.add_toast(scene_path, parent_node_id, text, duration,
                            position, variant, width, height)

    @mcp.tool()
    def cocos_add_loading_spinner(scene_path: str, parent_node_id: int,
                                  sprite_frame_uuid: str | None = None,
                                  text: str | None = "Loading...",
                                  icon_size: int = 80,
                                  rotation_period: float = 1.0) -> dict:
        """Centered rotating icon + optional caption.

        Pass ``sprite_frame_uuid`` to get the rotation animation; pass
        ``None`` for a text-only indicator. ``rotation_period`` is one
        full 360° revolution — 1.0s is the iOS/Material default cadence.

        Tip: generate a spinner sprite via
        ``cocos_generate_asset(prompt='loading spinner icon, radial',
        style='icon')`` then pass the returned sprite_frame_uuid here.

        Returns {spinner_node_id, icon_node_id, label_node_id,
        rotation_component_id}.
        """
        return sb.add_loading_spinner(scene_path, parent_node_id,
                                      sprite_frame_uuid, text,
                                      icon_size, rotation_period)

    @mcp.tool()
    def cocos_add_styled_text_block(scene_path: str, parent_node_id: int,
                                    title: str,
                                    subtitle: str | None = None,
                                    body: str | None = None,
                                    width: int = 400,
                                    show_divider: bool = True,
                                    align: str = "center") -> dict:
        """Title + optional subtitle + optional divider + optional body, stacked.

        The single most frequently rebuilt pattern in AI UI code — hoisted
        here so you don't compose it from 4-6 add_label calls every time.
        Pulls colors from the active UI theme: title uses ``text`` preset,
        subtitle uses ``text_dim``, divider uses ``border``. Body has
        wrap + overflow=RESIZE_HEIGHT so long paragraphs grow the block
        instead of clipping.

        Divider only materializes when body is present AND show_divider=True
        — dividing the top of the block from nothing is visual noise.
        ``align``: "left" / "center" / "right" applies to all text pieces.

        Returns {block_node_id, title_node_id, subtitle_node_id,
        divider_node_id, body_node_id}; None for absent pieces.
        """
        return sb.add_styled_text_block(scene_path, parent_node_id, title,
                                        subtitle, body, width, show_divider,
                                        align)

    # ---------------- Responsive helpers ----------------

    @mcp.tool()
    def cocos_make_fullscreen(scene_path: str, node_id: int) -> int:
        """Attach cc.Widget so the node stretches to fill its parent.

        Use for backgrounds, modal backdrops, full-bleed panels. Replaces
        the ``align_flags=15`` incantation (top+bottom+left+right bitmask).
        Returns the Widget component id.
        """
        return sb.make_fullscreen(scene_path, node_id)

    @mcp.tool()
    def cocos_anchor_to_edge(scene_path: str, node_id: int,
                             edge: str, margin: int = 0) -> int:
        """Pin node to an edge / corner of its parent via cc.Widget.

        ``edge``: ``top`` / ``bottom`` / ``left`` / ``right`` /
        ``top-left`` / ``top-right`` / ``bottom-left`` / ``bottom-right``.
        ``margin``: distance from the edge (from both edges for corners).
        Returns the Widget component id.
        """
        return sb.anchor_to_edge(scene_path, node_id, edge, margin)

    @mcp.tool()
    def cocos_center_in_parent(scene_path: str, node_id: int,
                               horizontal: bool = True,
                               vertical: bool = True) -> int:
        """Attach cc.Widget with centering flags on either/both axes.

        ``horizontal=False`` centers only vertically, and vice versa.
        Returns the Widget component id.
        """
        return sb.center_in_parent(scene_path, node_id, horizontal, vertical)

    @mcp.tool()
    def cocos_stack_vertically(scene_path: str, node_id: int,
                               spacing: str | int = "md",
                               padding: str | int = "lg",
                               align: str = "center") -> int:
        """cc.Layout type=VERTICAL — children arrange top-to-bottom.

        ``spacing`` / ``padding`` accept a design-token name
        (``xs``/``sm``/``md``/``lg``/``xl``) or a raw int in logical
        pixels. ``align``: ``left``/``center``/``right``.
        Returns the Layout component id.
        """
        return sb.stack_vertically(scene_path, node_id, spacing, padding, align)

    @mcp.tool()
    def cocos_stack_horizontally(scene_path: str, node_id: int,
                                 spacing: str | int = "md",
                                 padding: str | int = "lg",
                                 align: str = "top") -> int:
        """cc.Layout type=HORIZONTAL — children arrange left-to-right.

        ``align`` here is the cross-axis: ``top``/``center``/``bottom``.
        Returns the Layout component id.
        """
        return sb.stack_horizontally(scene_path, node_id, spacing, padding, align)

    @mcp.tool()
    def cocos_add_card_grid(scene_path: str, parent_node_id: int,
                            cards: list[dict],
                            columns: int = 3,
                            card_width: int = 200,
                            card_height: int = 240,
                            spacing: int = 20) -> dict:
        """Grid of tappable cards — level select, shop, character picker.

        Each ``cards[i]`` is::

            {"title": str,
             "subtitle": str | None,
             "icon_sprite_frame_uuid": str | None,
             "variant": "primary" | "surface",    # bg color, default "surface"
             "click_events": [...] | None}

        Whole card is the button (tap anywhere). Title + subtitle auto-
        pick contrasting text colors for the chosen variant ("primary"
        variant gets bg-colored text; "surface" gets text-colored).
        Extras wrap to new rows when count > columns.

        Returns {grid_node_id, cards: [{node_id, title_node_id,
        subtitle_node_id, icon_node_id, button_component_id}, ...]}.
        Wire per-card click by passing ``click_events`` in each spec.
        """
        return sb.add_card_grid(scene_path, parent_node_id, cards, columns,
                                card_width, card_height, spacing)

    @mcp.tool()
    def cocos_add_hud_bar(scene_path: str, parent_node_id: int,
                          items: list[dict] | None = None,
                          height: int = 80,
                          side: str = "top") -> dict:
        """Build a horizontal HUD bar pinned to the top (or bottom).

        ``items`` is a list of:
          - ``{"kind": "label", "text": str, "size_preset": str,
             "color_preset": str, "width": int, "align": str}`` — text cell
          - ``{"kind": "spacer", "width": int}`` — blank gap

        Default is a Score label + spacer + Lv label, good for endless-
        runner style games. ``side``: "top" (default) or "bottom".
        """
        return sb.add_hud_bar(scene_path, parent_node_id, items, height, side)

    # ---------------- Animation presets ----------------

    @mcp.tool()
    def cocos_add_fade_in(scene_path: str, node_id: int,
                          duration: float = 0.3,
                          delay: float = 0.0,
                          rel_dir: str | None = None) -> dict:
        """Fade a node from transparent → opaque at scene start.

        Generates a ``.anim`` clip in ``assets/animations/`` (override
        with ``rel_dir``), attaches ``cc.UIOpacity`` (initial 0 so the
        first frame doesn't flash), and attaches ``cc.Animation`` with
        play_on_load=True. ``delay`` holds at 0 opacity before the ramp
        — useful for staggering sibling fades.

        Returns {clip_uuid, clip_path, anim_component_id, opacity_component_id}.
        """
        return sb.add_fade_in(scene_path, node_id, duration, delay, rel_dir)

    @mcp.tool()
    def cocos_add_slide_in(scene_path: str, node_id: int,
                           from_side: str = "bottom",
                           distance: float = 200.0,
                           duration: float = 0.4,
                           delay: float = 0.0,
                           rel_dir: str | None = None) -> dict:
        """Slide a node in from off-screen at scene start.

        ``from_side``: "left" / "right" / "top" / "bottom".
        The end pose is the node's CURRENT _lpos — set the final
        position first, then call this to animate the entrance.

        Returns {clip_uuid, clip_path, anim_component_id}.
        """
        return sb.add_slide_in(scene_path, node_id, from_side, distance,
                               duration, delay, rel_dir)

    @mcp.tool()
    def cocos_add_scale_in(scene_path: str, node_id: int,
                           from_scale: float = 0.0,
                           duration: float = 0.3,
                           delay: float = 0.0,
                           rel_dir: str | None = None) -> dict:
        """Pop a node in from ``from_scale`` to 1.0 at scene start.

        ``from_scale=0`` → pop-in from nothing;
        ``from_scale=0.5`` → grow from half-size.

        Returns {clip_uuid, clip_path, anim_component_id}.
        """
        return sb.add_scale_in(scene_path, node_id, from_scale, duration,
                               delay, rel_dir)

    @mcp.tool()
    def cocos_add_bounce_in(scene_path: str, node_id: int,
                            overshoot: float = 1.15,
                            duration: float = 0.5,
                            delay: float = 0.0,
                            rel_dir: str | None = None) -> dict:
        """Entrance with a spring-like overshoot: 0 → overshoot → 1.0.

        Tune ``overshoot`` 1.05-1.3 — below that the bounce is invisible,
        above it reads as jittery. 0.5s duration is a good default for
        most UI; halve for faster games.

        Returns {clip_uuid, clip_path, anim_component_id}.
        """
        return sb.add_bounce_in(scene_path, node_id, overshoot, duration,
                                delay, rel_dir)

    @mcp.tool()
    def cocos_add_pulse(scene_path: str, node_id: int,
                        strength: float = 0.08,
                        period: float = 1.2,
                        rel_dir: str | None = None) -> dict:
        """Looping subtle scale pulse — attention-grabber for idle UI.

        ``strength``: how much bigger at peak (0.08 = 8%). Keep subtle;
        above ~0.15 looks anxious.
        ``period``: one cycle in seconds. 1.0-1.5 reads as a relaxed
        heartbeat; below 0.5 feels panicked.

        Clip loops forever — attach and forget.

        Returns {clip_uuid, clip_path, anim_component_id}.
        """
        return sb.add_pulse(scene_path, node_id, strength, period, rel_dir)

    @mcp.tool()
    def cocos_add_shake(scene_path: str, node_id: int,
                        intensity: float = 10.0,
                        duration: float = 0.3,
                        axis: str = "x",
                        rel_dir: str | None = None) -> dict:
        """One-shot position wobble — for damage / error / impact feedback.

        ``axis``: "x" (horizontal hit / invalid-input), "y" (stomp),
        "both" (explosion / big impact).
        ``intensity`` is the peak amplitude in logical pixels;
        oscillation decays linearly to 0 over ``duration``.

        Animates around the node's CURRENT _lpos — position the node
        first, then attach.

        Returns {clip_uuid, clip_path, anim_component_id}.
        """
        return sb.add_shake(scene_path, node_id, intensity, duration, axis,
                            rel_dir)

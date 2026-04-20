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

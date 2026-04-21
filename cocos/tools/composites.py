"""MCP tool registrations for cross-cutting composites.

Each tool here wraps a multi-step sequence that agents ran over and
over during the dogfood run — ``add_script`` → ``compress_uuid`` →
scene-level ``add_script`` being the clearest case. Surfacing them
directly as single MCP tools cuts per-operation bookkeeping roughly
in half on any non-trivial scene.

The implementation lives in ``cocos.composites`` so it's importable
from plain Python (tests, callers that don't spin up an MCP server),
and this module is the thin FastMCP adapter.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import composites as co

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def cocos_add_and_attach_script(project_path: str,
                                    rel_path: str,
                                    source: str,
                                    scene_path: str,
                                    node_id: int,
                                    props: dict | None = None,
                                    uuid: str | None = None) -> dict:
        """Write a TS script file + attach it as a component in ONE call.

        Replaces the 3-call sequence agents ran dozens of times per
        session::

            r = cocos_add_script(project, "Bird", source)       # file + meta
            short = cocos_compress_uuid(r["uuid"])               # UUID form
            cid = cocos_add_script(scene, node_id, short, props) # attach

        The two same-named ``cocos_add_script`` tools (the project-
        level writer vs. the scene-level attacher) were the main
        friction — agents accidentally passed the standard UUID to
        the attacher, or skipped the compress step entirely and got
        a silently-broken component.

        Arguments:

        * ``project_path`` / ``rel_path`` / ``source`` — where the .ts
          lives. ``rel_path`` follows ``cocos_add_script``'s prefix
          rules (bare name → ``assets/scripts/<name>.ts``).
        * ``scene_path`` / ``node_id`` — target scene (or .prefab) and
          the node's array index.
        * ``props`` — component @property values, forwarded verbatim.
          Use ``{"__id__": N}`` for node/component refs,
          ``{"__uuid__": "..."}`` for asset refs.
        * ``uuid`` — optional override for the .ts.meta UUID. Omit to
          let the underlying ``add_script`` preserve an existing UUID
          on overwrite (Bug A fix) or mint a fresh one on first write.

        Returns::

            {
              "script_path":    "/abs/path/Foo.ts",
              "rel_path":       "assets/scripts/Foo.ts",
              "uuid_standard":  "5372d6f5-...",       # 36-char form
              "uuid_compressed":"5372db1cH...",       # what scenes use
              "component_id":   <int>,                # attached comp's id
              "created":        <bool>,               # False if meta preserved
            }
        """
        return co.add_and_attach_script(project_path, rel_path, source,
                                        scene_path, node_id,
                                        props=props, uuid=uuid)

    @mcp.tool()
    def cocos_add_physics_body2d(scene_path: str,
                                 node_id: int,
                                 shape: str = "box",
                                 body_type: int = 2,
                                 gravity_scale: float = 1.0,
                                 linear_damping: float = 0.0,
                                 angular_damping: float = 0.0,
                                 fixed_rotation: bool = False,
                                 bullet: bool = False,
                                 awake_on_load: bool = True,
                                 density: float = 1.0,
                                 friction: float = 0.2,
                                 restitution: float = 0.0,
                                 is_sensor: bool = False,
                                 tag: int = 0,
                                 offset_x: float = 0.0,
                                 offset_y: float = 0.0,
                                 width: float = 100.0,
                                 height: float = 100.0,
                                 radius: float = 50.0,
                                 points: list[list[float]] | None = None) -> dict:
        """Attach cc.RigidBody2D + a shape collider in one call.

        Replaces the 2-call pattern every Bird / Pipe / Enemy needed:

            rb = cocos_add_rigidbody2d(scene, node, body_type=2, ...)
            col = cocos_add_box_collider2d(scene, node, width=W, ...)

        ``shape`` picks the collider: ``"box"`` / ``"circle"`` / ``"polygon"``.
        The relevant shape knobs (``width``×``height`` / ``radius`` /
        ``points``) are read based on the choice; the others are ignored.
        Raises ValueError on unknown shape rather than silently attaching
        a default.

        ``body_type``: 0=Static, 1=Kinematic, 2=Dynamic (default).

        Returns ``{rigidbody_id, collider_id, shape}``.
        """
        return co.add_physics_body2d(
            scene_path, node_id, shape=shape, body_type=body_type,
            gravity_scale=gravity_scale, linear_damping=linear_damping,
            angular_damping=angular_damping, fixed_rotation=fixed_rotation,
            bullet=bullet, awake_on_load=awake_on_load,
            density=density, friction=friction, restitution=restitution,
            is_sensor=is_sensor, tag=tag,
            offset_x=offset_x, offset_y=offset_y,
            width=width, height=height,
            radius=radius, points=points,
        )

    @mcp.tool()
    def cocos_add_button_with_label(scene_path: str,
                                    parent_id: int,
                                    label_text: str,
                                    width: float = 200.0,
                                    height: float = 60.0,
                                    name: str | None = None,
                                    pos_x: float = 0.0,
                                    pos_y: float = 0.0,
                                    font_size: int = 32,
                                    sprite_frame_uuid: str | None = None,
                                    label_color_preset: str | None = None,
                                    label_size_preset: str | None = None,
                                    bg_color_preset: str | None = None,
                                    transition: int = 2,
                                    zoom_scale: float = 1.1,
                                    click_events: list[dict] | None = None) -> dict:
        """Create a button node with a child Label in one call.

        The single most-repeated UI sequence in the dogfood run —
        every menu had 2-4 buttons, each needing:

            btn_node = cocos_create_node(scene, parent, name, ...)
            cocos_add_uitransform(scene, btn_node, W, H)
            cocos_add_sprite(scene, btn_node, sprite_frame_uuid, ...)  # optional
            btn = cocos_add_button(scene, btn_node, ...)
            lbl_node = cocos_create_node(scene, btn_node, "Label")
            cocos_add_uitransform(scene, lbl_node, W, H)
            lbl = cocos_add_label(scene, lbl_node, text, font_size, ...)

        Folds all seven calls into one. Structure produced::

            Btn (Node + UITransform + optional Sprite + Button)
             └── Label (Node + UITransform + Label)

        Design-token presets (``label_color_preset`` / ``label_size_preset``
        / ``bg_color_preset``) resolve through the project's UI theme.
        Forward ``click_events`` from ``cocos_make_click_event`` verbatim.

        Returns ``{button_node_id, label_node_id, button_component_id,
        label_component_id, sprite_component_id}``.
        """
        return co.add_button_with_label(
            scene_path, parent_id, label_text,
            width=width, height=height, name=name,
            pos_x=pos_x, pos_y=pos_y, font_size=font_size,
            sprite_frame_uuid=sprite_frame_uuid,
            label_color_preset=label_color_preset,
            label_size_preset=label_size_preset,
            bg_color_preset=bg_color_preset,
            transition=transition, zoom_scale=zoom_scale,
            click_events=click_events,
        )

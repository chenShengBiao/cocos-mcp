#!/usr/bin/env python3
"""cocos-mcp — headless Cocos Creator MCP server.

Lets Claude (or any MCP client) build a complete Cocos Creator 3.8 game
**without ever opening the editor GUI**. All operations are direct file
I/O on the project's JSON / TS / PNG / meta files, plus invoking
`CocosCreator --build` headlessly.

Companion to but independent from DaxianLee/cocos-mcp-server, which is a
Cocos Creator editor plugin (requires the editor to be running). Use this
one for CI / autonomous AI development; use the editor plugin when the
human is actively working inside the editor.

Tool naming follows DaxianLee's verb-first style for cross-tool consistency.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Make the local `cocos` package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

from cocos import build as cb
from cocos import meta_util as mu
from cocos import project as cp
from cocos import scene_builder as sb
from cocos import uuid_util as uu

mcp = FastMCP("cocos-mcp")


# =====================================================================
# UUID utilities
# =====================================================================

@mcp.tool()
def cocos_new_uuid() -> str:
    """Generate a fresh standard UUID4 (36-char dashed lowercase hex).

    Used as the main UUID for new scripts, scenes, prefabs, and images.
    """
    return uu.new_uuid()


@mcp.tool()
def cocos_compress_uuid(uuid: str) -> str:
    """Compress a 36-char UUID to Cocos Creator's 23-char short form.

    Required when referencing a custom TS script class as a component
    `__type__` in a scene/prefab JSON. Example:
      '5372d6f5-721e-43f6-b004-d30da1c8a9a0' -> '5372db1ch5D9rAE0w2hyKmg'
    """
    return uu.compress_uuid(uuid)


@mcp.tool()
def cocos_decompress_uuid(short_uuid: str) -> str:
    """Reverse cocos_compress_uuid: 23-char short -> 36-char dashed."""
    return uu.decompress_uuid(short_uuid)


# =====================================================================
# Project: detect / init / inspect
# =====================================================================

@mcp.tool()
def cocos_list_creator_installs() -> list[dict]:
    """List every locally installed Cocos Creator version.

    Returns a list of {version, exe, template_dir} dicts. Looks under
    /Applications/Cocos/Creator on macOS, C:/CocosDashboard/Creator on
    Windows, /opt/Cocos/Creator on Linux.
    """
    return cp.list_creator_installs()


@mcp.tool()
def cocos_init_project(dst_path: str, creator_version: str | None = None,
                       template: str = "empty-2d", project_name: str | None = None) -> dict:
    """Initialize a new Cocos Creator project from a template.

    Copies a built-in template (default empty-2d) into `dst_path`,
    patches `package.json` with a fresh project UUID and the right
    creator version, and creates standard `assets/` subdirectories.

    Use `cocos_list_creator_installs` first to see available versions.
    """
    return cp.init_project(dst_path, creator_version, template, project_name)


@mcp.tool()
def cocos_get_project_info(project_path: str) -> dict:
    """Read package.json + list assets / scenes / scripts in the project."""
    return cp.get_project_info(project_path)


@mcp.tool()
def cocos_list_assets(project_path: str) -> dict:
    """List all assets in the project grouped by type, with their UUIDs.

    Returns {scripts: [...], scenes: [...], images: [...], prefabs: [...]}.
    Each entry has at minimum {rel, uuid}; images additionally include
    `sprite_frame_uuid` if the meta is upgraded.
    """
    return cp.list_assets(project_path)


# =====================================================================
# Asset management: scripts and images
# =====================================================================

@mcp.tool()
def cocos_add_script(project_path: str, rel_path: str, source: str) -> dict:
    """Write a TypeScript script + its meta into the project.

    `rel_path` can be either:
      - bare name like 'GameManager' -> writes assets/scripts/GameManager.ts
      - full path like 'assets/scripts/sub/Foo.ts'

    Returns {path, rel_path, uuid}. The uuid is the standard 36-char form;
    use cocos_compress_uuid to get the 23-char form needed in scene files.
    """
    return cp.add_script(project_path, rel_path, source)


@mcp.tool()
def cocos_add_image(project_path: str, src_png: str, rel_path: str | None = None,
                    as_resource: bool = False) -> dict:
    """Copy a PNG into the project and write a complete sprite-frame meta.

    Default: assets/textures/. Set as_resource=True to put it under
    assets/resources/ (needed for runtime loading via resources.load()).

    Returns {path, rel_path, main_uuid, sprite_frame_uuid, texture_uuid}.
    """
    return cp.add_image(project_path, src_png, rel_path, as_resource=as_resource)


@mcp.tool()
def cocos_upgrade_image_meta(meta_path: str) -> dict:
    """Upgrade a texture-only PNG meta to include a sprite-frame sub.

    Cocos Creator's CLI `--build` auto-generates `type: texture` metas
    when it imports a fresh PNG. To reference such a PNG from
    `cc.Sprite`, run this tool to add the `f9941` (sprite-frame) sub.
    Idempotent — does nothing if the sub already exists.

    Returns the updated meta dict.
    """
    return mu.upgrade_texture_to_sprite_frame(meta_path)


@mcp.tool()
def cocos_get_sprite_frame_uuid(meta_path: str) -> str:
    """Return the `<uuid>@f9941` sprite-frame sub-uuid for a PNG meta."""
    return mu.get_sprite_frame_uuid(meta_path)


# =====================================================================
# Scene builder
# =====================================================================

@mcp.tool()
def cocos_create_scene(project_path: str, scene_name: str = "Game",
                       canvas_width: int = 960, canvas_height: int = 640,
                       clear_color_r: int = 135, clear_color_g: int = 206,
                       clear_color_b: int = 235) -> dict:
    """Create a minimal empty 2D scene + meta in assets/scenes/.

    Includes Canvas + UICamera (cc.Camera) + cc.Canvas + Widget +
    SceneGlobals (Ambient/Skybox/Shadows) + PrefabInfo. The Camera's
    `clearColor` is set so a solid sky-blue background is visible
    even before any sprite is added.

    Returns canonical IDs:
      {scene_path, scene_uuid, scene_node_id, canvas_node_id,
       ui_camera_node_id, camera_component_id, canvas_component_id}

    These IDs are array-index references into the scene's JSON;
    use them as `parent_id` / `node_id` in subsequent tool calls.
    """
    p = Path(project_path).expanduser().resolve()
    scene_path = p / "assets" / "scenes" / f"{scene_name}.scene"
    return sb.create_empty_scene(
        scene_path, canvas_width=canvas_width, canvas_height=canvas_height,
        clear_color=(clear_color_r, clear_color_g, clear_color_b, 255),
    )


@mcp.tool()
def cocos_create_node(scene_path: str, parent_id: int, name: str,
                      pos_x: float = 0, pos_y: float = 0, pos_z: float = 0,
                      scale: float = 1, layer: int = 33554432, active: bool = True) -> int:
    """Append a new cc.Node under `parent_id`, return its array index.

    `layer` defaults to UI_2D (33554432). Use 1073741824 for the camera node.
    The new node has no components yet — call `cocos_add_uitransform`,
    `cocos_add_sprite` etc. to attach them.
    """
    return sb.add_node(
        scene_path, parent_id, name,
        lpos=(pos_x, pos_y, pos_z), lscale=(scale, scale, 1),
        layer=layer, active=active,
    )


@mcp.tool()
def cocos_add_uitransform(scene_path: str, node_id: int, width: float, height: float,
                          anchor_x: float = 0.5, anchor_y: float = 0.5) -> int:
    """Attach a cc.UITransform to a node. Required for any UI rendering."""
    return sb.add_uitransform(scene_path, node_id, width, height, anchor_x, anchor_y)


@mcp.tool()
def cocos_add_sprite(scene_path: str, node_id: int, sprite_frame_uuid: str | None = None,
                     size_mode: int = 0,
                     color_r: int = 255, color_g: int = 255, color_b: int = 255, color_a: int = 255) -> int:
    """Attach a cc.Sprite to a node.

    `sprite_frame_uuid` is the `<uuid>@f9941` form returned by
    `cocos_add_image` or `cocos_get_sprite_frame_uuid`.
    `size_mode`: 0=CUSTOM (use UITransform's contentSize), 1=TRIMMED, 2=RAW.
    """
    return sb.add_sprite(scene_path, node_id, sprite_frame_uuid, size_mode,
                         (color_r, color_g, color_b, color_a))


@mcp.tool()
def cocos_add_label(scene_path: str, node_id: int, text: str, font_size: int = 40,
                    color_r: int = 255, color_g: int = 255, color_b: int = 255, color_a: int = 255,
                    h_align: int = 1, v_align: int = 1) -> int:
    """Attach a cc.Label to a node. h_align/v_align: 0=left/top 1=center 2=right/bottom."""
    return sb.add_label(scene_path, node_id, text, font_size,
                        (color_r, color_g, color_b, color_a), h_align, v_align)


@mcp.tool()
def cocos_add_graphics(scene_path: str, node_id: int) -> int:
    """Attach a cc.Graphics to a node (for runtime vector drawing)."""
    return sb.add_graphics(scene_path, node_id)


@mcp.tool()
def cocos_add_widget(scene_path: str, node_id: int, align_flags: int = 45,
                     target_id: int | None = None) -> int:
    """Attach a cc.Widget for screen-anchor layout. align_flags is a bitmask."""
    return sb.add_widget(scene_path, node_id, align_flags, target_id)


@mcp.tool()
def cocos_attach_script(scene_path: str, node_id: int, script_uuid_compressed: str,
                        props: dict | None = None) -> int:
    """Attach a custom TypeScript script component to a node.

    `script_uuid_compressed` is the 23-char short form (run
    `cocos_compress_uuid` on the .ts.meta uuid).

    `props` lets you set @property fields. Pass int values for
    node/component refs (they'll be wrapped as {"__id__": N}).
    Pass strings/numbers/bools for plain values.
    """
    return sb.add_script(scene_path, node_id, script_uuid_compressed, props)


@mcp.tool()
def cocos_link_property(scene_path: str, component_id: int, prop_name: str,
                        target_id: int | None) -> str:
    """Set a @property on a component to reference another node/component.

    Pass `target_id=None` to clear the reference.
    """
    sb.link_property(scene_path, component_id, prop_name, target_id)
    return f"linked {component_id}.{prop_name} -> {target_id}"


@mcp.tool()
def cocos_set_property(scene_path: str, object_id: int, prop_name: str, value: Any) -> str:
    """Set a literal (non-reference) property on any scene object.

    Use this for things like `_string`, `_fontSize`, `_color`, etc.
    For node/component references, use `cocos_link_property` instead.
    """
    sb.set_property(scene_path, object_id, prop_name, value)
    return f"set {object_id}.{prop_name}"


@mcp.tool()
def cocos_set_node_position(scene_path: str, node_id: int, x: float, y: float, z: float = 0) -> str:
    sb.set_node_position(scene_path, node_id, x, y, z)
    return f"node {node_id} -> ({x},{y},{z})"


@mcp.tool()
def cocos_set_node_active(scene_path: str, node_id: int, active: bool) -> str:
    sb.set_node_active(scene_path, node_id, active)
    return f"node {node_id} active={active}"


@mcp.tool()
def cocos_find_node_by_name(scene_path: str, name: str) -> int | None:
    """Find the first node with the given name. Returns its array index, or None."""
    return sb.find_node_by_name(scene_path, name)


@mcp.tool()
def cocos_list_scene_nodes(scene_path: str) -> list[dict]:
    """List every cc.Node in the scene with its id, name, parent, components, children."""
    return sb.list_nodes(scene_path)


@mcp.tool()
def cocos_validate_scene(scene_path: str) -> dict:
    """Sanity-check a scene file: ref ranges, type tags, parent linkage.

    Returns {valid: bool, object_count: int, issues: [...]}. Run this
    after building a scene to catch dangling __id__ references before
    invoking `cocos_build`.
    """
    return sb.validate_scene(scene_path)


# =====================================================================
# Prefab builder
# =====================================================================

@mcp.tool()
def cocos_create_prefab(project_path: str, prefab_name: str, root_name: str | None = None) -> dict:
    """Create an empty .prefab in assets/prefabs/ with a single root node."""
    p = Path(project_path).expanduser().resolve()
    prefab_path = p / "assets" / "prefabs" / f"{prefab_name}.prefab"
    return sb.create_prefab(prefab_path, root_name=root_name or prefab_name)


# =====================================================================
# Build / preview
# =====================================================================

@mcp.tool()
def cocos_build(project_path: str, platform: str = "web-mobile", debug: bool = True,
                creator_version: str | None = None, clean_temp: bool = True) -> dict:
    """Headlessly build the project via `CocosCreator --build`.

    Common platforms:
      web-mobile, web-desktop, wechatgame, ios, android, mac, windows

    Returns {exit_code, success, duration_sec, log_tail, build_dir, artifacts}.
    First build is slow (~1-2 min — engine compile, asset import).
    Subsequent builds with `clean_temp=False` can be much faster.
    """
    return cb.cli_build(project_path, platform, debug, creator_version, clean_temp=clean_temp)


@mcp.tool()
def cocos_start_preview(project_path: str, platform: str = "web-mobile", port: int = 8080) -> dict:
    """Start a local HTTP server serving the build/<platform>/ directory.

    Returns {port, url, serving}. Idempotent — replaces any server
    already on `port`. Run `cocos_build` first.
    """
    return cb.start_preview(project_path, platform, port)


@mcp.tool()
def cocos_stop_preview(port: int = 8080) -> dict:
    """Stop the preview HTTP server on the given port."""
    return cb.stop_preview(port)


@mcp.tool()
def cocos_preview_status() -> dict:
    """List currently running preview servers."""
    return cb.preview_status()


# =====================================================================
# Layer / type constants — exposed as a resource
# =====================================================================

@mcp.tool()
def cocos_constants() -> dict:
    """Return commonly used Cocos Creator constants.

    Saves you from looking up layer bitmasks, blend factors, alignment
    enum values, etc.
    """
    return {
        "layers": {
            "UI_2D": 33554432,    # bit 25
            "DEFAULT": 1073741824,  # bit 30 (used by Camera)
            "IGNORE_RAYCAST": 524288,  # bit 19
        },
        "blend_factors": {
            "ZERO": 0, "ONE": 1, "SRC_ALPHA": 2, "ONE_MINUS_SRC_ALPHA": 4,
            "DST_ALPHA": 8, "ONE_MINUS_DST_ALPHA": 16,
        },
        "label_align": {
            "LEFT": 0, "CENTER": 1, "RIGHT": 2,
            "TOP": 0, "MIDDLE": 1, "BOTTOM": 2,
        },
        "sprite_size_mode": {
            "CUSTOM": 0, "TRIMMED": 1, "RAW": 2,
        },
        "widget_align_flags": {
            "TOP": 1, "MIDDLE": 2, "BOTTOM": 4,
            "LEFT": 8, "CENTER": 16, "RIGHT": 32,
            "ALL": 45,  # TOP|BOTTOM|LEFT|RIGHT
        },
        "scene_globals_indices_in_empty_scene": {
            "comment": "These indices are stable in scenes created via cocos_create_scene",
            "scene_asset": 0,
            "scene": 1,
            "canvas": 2,
            "ui_camera_node": 3,
            "camera_component": 4,
            "canvas_uitransform": 5,
            "canvas_component": 6,
            "canvas_widget": 7,
            "scene_globals": 8,
            "ambient_info": 9,
            "skybox_info": 10,
            "shadows_info": 11,
            "prefab_info": 12,
        },
    }


# =====================================================================
# Scene builder: generic component & physics
# =====================================================================

@mcp.tool()
def cocos_add_component(scene_path: str, node_id: int, type_name: str,
                        props: dict | None = None) -> int:
    """Attach any cc component by its full type name (e.g. 'cc.RigidBody2D').

    `props` values are auto-wrapped: list[3]->Vec3, int->__id__ ref, etc.
    For resource refs pass {"__uuid__": "<uuid>"}.
    """
    return sb.add_component(scene_path, node_id, type_name, props)


@mcp.tool()
def cocos_add_rigidbody2d(scene_path: str, node_id: int,
                          body_type: int = 2, gravity_scale: float = 1.0,
                          linear_damping: float = 0.0, angular_damping: float = 0.0,
                          fixed_rotation: bool = False, bullet: bool = False,
                          awake_on_load: bool = True) -> int:
    """Attach cc.RigidBody2D. body_type: 0=Static, 1=Kinematic, 2=Dynamic."""
    return sb.add_rigidbody2d(scene_path, node_id, body_type, gravity_scale,
                              linear_damping, angular_damping, fixed_rotation,
                              bullet, awake_on_load)


@mcp.tool()
def cocos_add_box_collider2d(scene_path: str, node_id: int,
                             width: float = 100, height: float = 100,
                             offset_x: float = 0, offset_y: float = 0,
                             density: float = 1.0, friction: float = 0.2,
                             restitution: float = 0.0, is_sensor: bool = False,
                             tag: int = 0) -> int:
    """Attach cc.BoxCollider2D with given size, offset, and physics material."""
    return sb.add_box_collider2d(scene_path, node_id, width, height,
                                 offset_x, offset_y, density, friction,
                                 restitution, is_sensor, tag)


@mcp.tool()
def cocos_add_circle_collider2d(scene_path: str, node_id: int,
                                radius: float = 50,
                                offset_x: float = 0, offset_y: float = 0,
                                density: float = 1.0, friction: float = 0.2,
                                restitution: float = 0.0, is_sensor: bool = False,
                                tag: int = 0) -> int:
    """Attach cc.CircleCollider2D with given radius and physics material."""
    return sb.add_circle_collider2d(scene_path, node_id, radius,
                                    offset_x, offset_y, density, friction,
                                    restitution, is_sensor, tag)


@mcp.tool()
def cocos_add_polygon_collider2d(scene_path: str, node_id: int,
                                 points: list[list[float]] | None = None,
                                 density: float = 1.0, friction: float = 0.2,
                                 restitution: float = 0.0, is_sensor: bool = False,
                                 tag: int = 0) -> int:
    """Attach cc.PolygonCollider2D. `points` is [[x,y],...] vertex list."""
    return sb.add_polygon_collider2d(scene_path, node_id, points,
                                     density, friction, restitution,
                                     is_sensor, tag)


# =====================================================================
# Scene builder: UI components
# =====================================================================

@mcp.tool()
def cocos_add_button(scene_path: str, node_id: int,
                     transition: int = 2, zoom_scale: float = 1.1,
                     click_events: list[dict] | None = None,
                     normal_color_r: int = 255, normal_color_g: int = 255,
                     normal_color_b: int = 255, normal_color_a: int = 255,
                     hover_color_r: int = 211, hover_color_g: int = 211,
                     hover_color_b: int = 211, hover_color_a: int = 255,
                     pressed_color_r: int = 150, pressed_color_g: int = 150,
                     pressed_color_b: int = 150, pressed_color_a: int = 255,
                     disabled_color_r: int = 124, disabled_color_g: int = 124,
                     disabled_color_b: int = 124, disabled_color_a: int = 255) -> int:
    """Attach cc.Button. transition: 0=NONE, 1=COLOR, 2=SCALE, 3=SPRITE.

    click_events: list of dicts from cocos_make_click_event(). Each binds a
    button press to a script method. Example:
      evt = cocos_make_click_event(scene, gm_node, 'GameManager', 'onRestart')
      cocos_add_button(scene, btn_node, click_events=[evt])
    """
    return sb.add_button(scene_path, node_id, transition, zoom_scale,
                         (normal_color_r, normal_color_g, normal_color_b, normal_color_a),
                         (hover_color_r, hover_color_g, hover_color_b, hover_color_a),
                         (pressed_color_r, pressed_color_g, pressed_color_b, pressed_color_a),
                         (disabled_color_r, disabled_color_g, disabled_color_b, disabled_color_a),
                         click_events)


@mcp.tool()
def cocos_add_layout(scene_path: str, node_id: int,
                     layout_type: int = 1, spacing_x: float = 0, spacing_y: float = 0,
                     padding_top: float = 0, padding_bottom: float = 0,
                     padding_left: float = 0, padding_right: float = 0,
                     resize_mode: int = 1,
                     h_direction: int = 0, v_direction: int = 1) -> int:
    """Attach cc.Layout. layout_type: 0=NONE, 1=HORIZONTAL, 2=VERTICAL, 3=GRID."""
    return sb.add_layout(scene_path, node_id, layout_type, spacing_x, spacing_y,
                         padding_top, padding_bottom, padding_left, padding_right,
                         resize_mode, h_direction, v_direction)


@mcp.tool()
def cocos_add_progress_bar(scene_path: str, node_id: int,
                           bar_sprite_id: int | None = None,
                           mode: int = 0, total_length: float = 100,
                           progress: float = 1.0, reverse: bool = False) -> int:
    """Attach cc.ProgressBar. mode: 0=HORIZONTAL, 1=VERTICAL, 2=FILLED."""
    return sb.add_progress_bar(scene_path, node_id, bar_sprite_id,
                               mode, total_length, progress, reverse)


@mcp.tool()
def cocos_add_scroll_view(scene_path: str, node_id: int,
                          content_id: int | None = None,
                          horizontal: bool = False, vertical: bool = True,
                          inertia: bool = True, brake: float = 0.75,
                          elastic: bool = True, bounce_duration: float = 0.23) -> int:
    """Attach cc.ScrollView. content_id points to the scrollable content node."""
    return sb.add_scroll_view(scene_path, node_id, content_id,
                              horizontal, vertical, inertia, brake,
                              elastic, bounce_duration)


@mcp.tool()
def cocos_add_toggle(scene_path: str, node_id: int,
                     is_checked: bool = False, transition: int = 2) -> int:
    """Attach cc.Toggle. transition: 0=NONE, 1=COLOR, 2=SCALE, 3=SPRITE."""
    return sb.add_toggle(scene_path, node_id, is_checked, transition)


@mcp.tool()
def cocos_add_editbox(scene_path: str, node_id: int,
                      placeholder: str = "Enter text...",
                      max_length: int = -1, input_mode: int = 6,
                      return_type: int = 0) -> int:
    """Attach cc.EditBox. input_mode: 0=ANY, 6=SINGLE_LINE. -1=unlimited length."""
    return sb.add_editbox(scene_path, node_id, placeholder, max_length,
                          input_mode, return_type)


@mcp.tool()
def cocos_add_slider(scene_path: str, node_id: int,
                     direction: int = 0, progress: float = 0.5) -> int:
    """Attach cc.Slider. direction: 0=Horizontal, 1=Vertical."""
    return sb.add_slider(scene_path, node_id, direction, progress)


# =====================================================================
# Scene builder: audio & animation & particles
# =====================================================================

@mcp.tool()
def cocos_add_audio_source(scene_path: str, node_id: int,
                           clip_uuid: str | None = None,
                           play_on_awake: bool = False, loop: bool = False,
                           volume: float = 1.0) -> int:
    """Attach cc.AudioSource. clip_uuid references an audio-clip asset."""
    return sb.add_audio_source(scene_path, node_id, clip_uuid,
                               play_on_awake, loop, volume)


@mcp.tool()
def cocos_add_animation(scene_path: str, node_id: int,
                        default_clip_uuid: str | None = None,
                        play_on_load: bool = True,
                        clip_uuids: list[str] | None = None) -> int:
    """Attach cc.Animation. clip_uuids is a list of AnimationClip asset UUIDs."""
    return sb.add_animation(scene_path, node_id, default_clip_uuid,
                            play_on_load, clip_uuids)


@mcp.tool()
def cocos_add_particle_system_2d(scene_path: str, node_id: int,
                                 duration: float = -1, emission_rate: float = 10,
                                 life: float = 1, life_var: float = 0,
                                 total_particles: int = 150,
                                 start_color_r: int = 255, start_color_g: int = 255,
                                 start_color_b: int = 255, start_color_a: int = 255,
                                 end_color_r: int = 255, end_color_g: int = 255,
                                 end_color_b: int = 255, end_color_a: int = 0,
                                 angle: float = 90, angle_var: float = 360,
                                 speed: float = 180, speed_var: float = 50,
                                 gravity_x: float = 0, gravity_y: float = 0,
                                 start_size: float = 50, start_size_var: float = 0,
                                 end_size: float = 0, end_size_var: float = 0,
                                 emitter_mode: int = 0) -> int:
    """Attach cc.ParticleSystem2D with configurable emission, color, physics."""
    return sb.add_particle_system_2d(
        scene_path, node_id, duration, emission_rate, life, life_var,
        total_particles,
        (start_color_r, start_color_g, start_color_b, start_color_a),
        (end_color_r, end_color_g, end_color_b, end_color_a),
        angle, angle_var, speed, speed_var, gravity_x, gravity_y,
        start_size, start_size_var, end_size, end_size_var, emitter_mode)


# =====================================================================
# Scene builder: node mutation
# =====================================================================

@mcp.tool()
def cocos_set_node_scale(scene_path: str, node_id: int,
                         sx: float, sy: float, sz: float = 1) -> str:
    """Set a node's local scale."""
    sb.set_node_scale(scene_path, node_id, sx, sy, sz)
    return f"node {node_id} scale=({sx},{sy},{sz})"


@mcp.tool()
def cocos_set_node_rotation(scene_path: str, node_id: int, angle_z: float) -> str:
    """Set 2D rotation (euler Z) in degrees."""
    sb.set_node_rotation(scene_path, node_id, angle_z)
    return f"node {node_id} rotation={angle_z}"


@mcp.tool()
def cocos_move_node(scene_path: str, node_id: int, new_parent_id: int,
                    sibling_index: int = -1) -> str:
    """Re-parent a node. sibling_index=-1 appends as last child."""
    sb.move_node(scene_path, node_id, new_parent_id, sibling_index)
    return f"node {node_id} moved to parent {new_parent_id}"


@mcp.tool()
def cocos_delete_node(scene_path: str, node_id: int) -> str:
    """Soft-delete a node (disconnect from parent, deactivate). Indices stay stable."""
    sb.delete_node(scene_path, node_id)
    return f"node {node_id} deleted"


@mcp.tool()
def cocos_duplicate_node(scene_path: str, node_id: int,
                         new_name: str | None = None) -> int:
    """Shallow-copy a node (no children/components). Returns new node index."""
    return sb.duplicate_node(scene_path, node_id, new_name)


@mcp.tool()
def cocos_set_uuid_property(scene_path: str, object_id: int, prop_name: str,
                            uuid: str) -> str:
    """Set a property to a __uuid__ resource ref (SpriteFrame, AudioClip, etc.)."""
    sb.set_uuid_property(scene_path, object_id, prop_name, uuid)
    return f"set {object_id}.{prop_name} -> uuid:{uuid[:12]}..."


@mcp.tool()
def cocos_set_node_layer(scene_path: str, node_id: int, layer: int) -> str:
    """Set a node's layer bitmask. Common: UI_2D=33554432, DEFAULT=1073741824."""
    sb.set_node_layer(scene_path, node_id, layer)
    return f"node {node_id} layer={layer}"


@mcp.tool()
def cocos_get_object_count(scene_path: str) -> int:
    """Return the total number of objects in the scene/prefab JSON array."""
    return sb.get_object_count(scene_path)


@mcp.tool()
def cocos_get_object(scene_path: str, object_id: int) -> dict:
    """Return the raw JSON dict of a scene object (for debugging/inspection)."""
    return sb.get_object(scene_path, object_id)


# =====================================================================
# Asset management: audio & resource files
# =====================================================================

@mcp.tool()
def cocos_add_audio_file(project_path: str, src_path: str,
                         rel_path: str | None = None,
                         uuid: str | None = None) -> dict:
    """Copy an audio file (mp3/wav/ogg) into assets/resources/ + write meta.

    The file is placed under resources/ so it can be loaded at runtime
    via resources.load(). Returns {path, rel_path, uuid}.
    """
    return cp.add_audio_file(project_path, src_path, rel_path, uuid)


@mcp.tool()
def cocos_add_resource_file(project_path: str, src_path: str,
                            rel_path: str | None = None,
                            uuid: str | None = None) -> dict:
    """Copy any file into assets/resources/ + write a minimal meta.

    Suitable for JSON data, text assets, or custom resources.
    Returns {path, rel_path, uuid}.
    """
    return cp.add_resource_file(project_path, src_path, rel_path, uuid)


@mcp.tool()
def cocos_generate_asset(project_path: str, prompt: str, name: str,
                         style: str = "icon", width: int = 1024, height: int = 1024,
                         provider: str = "zhipu", transparent: bool = True,
                         as_resource: bool = False) -> dict:
    """Generate a game asset via AI and import it into the project in one step.

    Built-in AI image generation (no external dependencies):
    - 智谱 CogView-3-Flash (free) — set ZHIPU_API_KEY in cocos-mcp/.env
    - Pollinations Flux (free, no key) — use provider="pollinations"

    Flow: AI generate PNG → remove white background → write sprite-frame meta.
    Config: create .env file in cocos-mcp/ root with ZHIPU_API_KEY=your_key

    Example:
      result = cocos_generate_asset(project, "cute yellow cartoon bird",
                                    "bird", style="icon")
      cocos_add_sprite(scene, node, sprite_frame_uuid=result["sprite_frame_uuid"])

    Styles: icon, pixel, character, tile, ui, portrait, item, scene, none.
    """
    return cp.generate_and_import_image(project_path, prompt, name, style,
                                        width, height, provider, transparent, as_resource)


@mcp.tool()
def cocos_create_sprite_atlas(project_path: str, atlas_name: str,
                              png_paths: list[str],
                              rel_dir: str | None = None,
                              max_width: int = 2048, max_height: int = 2048) -> dict:
    """Bundle multiple PNGs into a SpriteAtlas (AutoAtlas .pac).

    Copies PNGs into assets/atlas/<name>/, writes sprite-frame metas,
    and creates a .pac config. Cocos Creator merges them into one
    texture at build time for better draw-call performance.

    Returns {dir, atlas_uuid, pac_path, images: [{path, uuid, sprite_frame_uuid}]}.
    Use each image's sprite_frame_uuid with cocos_add_sprite().
    """
    return cp.create_sprite_atlas(project_path, atlas_name, png_paths,
                                  rel_dir, max_width=max_width, max_height=max_height)


# =====================================================================
# AnimationClip generator
# =====================================================================

@mcp.tool()
def cocos_create_animation_clip(project_path: str, clip_name: str,
                                duration: float = 1.0, sample: int = 60,
                                tracks: list[dict] | None = None,
                                rel_dir: str | None = None) -> dict:
    """Create a .anim AnimationClip file.

    Each track dict: {path, property, keyframes: [{time, value}, ...]}.
    Properties: 'position' (value=[x,y,z]), 'scale' ([sx,sy,sz]),
    'rotation' ([ez]), 'opacity' (0-255), 'color' ([r,g,b,a]), 'active' (bool).

    Returns {path, rel_path, uuid}. Use uuid with cocos_add_animation().

    Example track:
      {"path": "", "property": "position",
       "keyframes": [{"time": 0, "value": [0,0,0]}, {"time": 1, "value": [100,0,0]}]}
    """
    return cp.create_animation_clip(project_path, clip_name, duration, sample,
                                    tracks, rel_dir)


@mcp.tool()
def cocos_make_click_event(scene_path: str, target_node_id: int,
                           component_name: str, handler: str,
                           custom_data: str = "") -> dict:
    """Build a cc.ClickEvent dict for use with cocos_add_button's click_events.

    Args:
        target_node_id: Node that holds the script (array index)
        component_name: @ccclass name (e.g. 'GameManager')
        handler: Method name to call (e.g. 'onStartClick')

    Returns a dict to pass in click_events list of cocos_add_button.

    Example workflow:
      evt = cocos_make_click_event(scene, gm_node, 'GameManager', 'onStart')
      cocos_add_button(scene, btn_node, click_events=[evt])
    """
    return sb.make_click_event(target_node_id, component_name, handler, custom_data)


# =====================================================================
# Spine / DragonBones skeletal animation
# =====================================================================

@mcp.tool()
def cocos_add_spine(scene_path: str, node_id: int,
                    skeleton_data_uuid: str | None = None,
                    default_skin: str = "default",
                    default_animation: str = "",
                    loop: bool = True, time_scale: float = 1.0) -> int:
    """Attach sp.Skeleton (Spine). Use cocos_add_spine_data to import assets first."""
    return sb.add_spine(scene_path, node_id, skeleton_data_uuid,
                        default_skin, default_animation, loop, True, time_scale)


@mcp.tool()
def cocos_add_spine_data(project_path: str, spine_json_path: str,
                         atlas_path: str,
                         texture_paths: list[str] | None = None,
                         rel_dir: str | None = None) -> dict:
    """Import Spine skeleton assets (.json + .atlas + textures).

    Returns {skeleton_data_uuid, atlas_uuid, textures, dir}.
    Use skeleton_data_uuid with cocos_add_spine().
    """
    return cp.add_spine_data(project_path, spine_json_path, atlas_path,
                             texture_paths, rel_dir)


@mcp.tool()
def cocos_add_dragonbones(scene_path: str, node_id: int,
                          dragon_asset_uuid: str | None = None,
                          dragon_atlas_asset_uuid: str | None = None,
                          armature_name: str = "",
                          animation_name: str = "",
                          play_times: int = -1,
                          time_scale: float = 1.0) -> int:
    """Attach dragonBones.ArmatureDisplay. Use cocos_add_dragonbones_data first."""
    return sb.add_dragonbones(scene_path, node_id, dragon_asset_uuid,
                              dragon_atlas_asset_uuid, armature_name,
                              animation_name, play_times, time_scale)


@mcp.tool()
def cocos_add_dragonbones_data(project_path: str, db_json_path: str,
                               atlas_json_path: str,
                               texture_paths: list[str] | None = None,
                               rel_dir: str | None = None) -> dict:
    """Import DragonBones assets (_ske.json + _tex.json + _tex.png).

    Returns {dragon_asset_uuid, dragon_atlas_uuid, textures, dir}.
    """
    return cp.add_dragonbones_data(project_path, db_json_path, atlas_json_path,
                                   texture_paths, rel_dir)


# =====================================================================
# TiledMap
# =====================================================================

@mcp.tool()
def cocos_add_tiled_map(scene_path: str, node_id: int,
                        tmx_asset_uuid: str | None = None) -> int:
    """Attach cc.TiledMap component. Use cocos_add_tiled_map_asset to import first."""
    return sb.add_tiled_map(scene_path, node_id, tmx_asset_uuid)


@mcp.tool()
def cocos_add_tiled_layer(scene_path: str, node_id: int,
                          layer_name: str = "") -> int:
    """Attach cc.TiledLayer (usually auto-created by TiledMap)."""
    return sb.add_tiled_layer(scene_path, node_id, layer_name)


@mcp.tool()
def cocos_add_tiled_map_asset(project_path: str, tmx_path: str,
                              tsx_paths: list[str] | None = None,
                              texture_paths: list[str] | None = None,
                              rel_dir: str | None = None) -> dict:
    """Import TiledMap assets (.tmx + .tsx tilesets + tileset PNGs).

    Returns {tmx_uuid, tsx_files, textures, dir}.
    Use tmx_uuid with cocos_add_tiled_map().
    """
    return cp.add_tiled_map_asset(project_path, tmx_path, tsx_paths,
                                  texture_paths, rel_dir)


# =====================================================================
# Camera / Mask / RichText / Sliced & Tiled Sprite
# =====================================================================

@mcp.tool()
def cocos_add_camera(scene_path: str, node_id: int,
                     projection: int = 0, priority: int = 0,
                     ortho_height: float = 320, fov: float = 45,
                     clear_color_r: int = 0, clear_color_g: int = 0,
                     clear_color_b: int = 0, clear_color_a: int = 255,
                     visibility: int = 41943040) -> int:
    """Attach cc.Camera. projection: 0=ORTHO, 1=PERSPECTIVE. For minimap/split-screen."""
    return sb.add_camera(scene_path, node_id, projection, priority, ortho_height, fov,
                         clear_color=(clear_color_r, clear_color_g, clear_color_b, clear_color_a),
                         visibility=visibility)


@mcp.tool()
def cocos_add_mask(scene_path: str, node_id: int,
                   mask_type: int = 0, inverted: bool = False, segments: int = 64) -> int:
    """Attach cc.Mask. mask_type: 0=RECT, 1=ELLIPSE, 2=GRAPHICS_STENCIL, 3=SPRITE_STENCIL."""
    return sb.add_mask(scene_path, node_id, mask_type, inverted, segments)


@mcp.tool()
def cocos_add_richtext(scene_path: str, node_id: int, text: str = "<b>Hello</b>",
                       font_size: int = 40, max_width: float = 0,
                       line_height: float = 40, horizontal_align: int = 0) -> int:
    """Attach cc.RichText. Supports <b>, <i>, <color=#FF0000>, <size=24>, <img> tags."""
    return sb.add_richtext(scene_path, node_id, text, font_size, max_width,
                           line_height, horizontal_align)


@mcp.tool()
def cocos_add_sliced_sprite(scene_path: str, node_id: int,
                            sprite_frame_uuid: str | None = None,
                            color_r: int = 255, color_g: int = 255,
                            color_b: int = 255, color_a: int = 255) -> int:
    """Attach cc.Sprite with type=SLICED (9-slice). Stretches center, keeps corners."""
    return sb.add_sliced_sprite(scene_path, node_id, sprite_frame_uuid,
                                (color_r, color_g, color_b, color_a))


@mcp.tool()
def cocos_add_tiled_sprite(scene_path: str, node_id: int,
                           sprite_frame_uuid: str | None = None,
                           color_r: int = 255, color_g: int = 255,
                           color_b: int = 255, color_a: int = 255) -> int:
    """Attach cc.Sprite with type=TILED (repeating pattern fill)."""
    return sb.add_tiled_sprite(scene_path, node_id, sprite_frame_uuid,
                               (color_r, color_g, color_b, color_a))


@mcp.tool()
def cocos_add_filled_sprite(scene_path: str, node_id: int,
                            sprite_frame_uuid: str | None = None,
                            fill_type: int = 0, fill_start: float = 0,
                            fill_range: float = 1.0,
                            fill_center_x: float = 0.5, fill_center_y: float = 0.5,
                            color_r: int = 255, color_g: int = 255,
                            color_b: int = 255, color_a: int = 255) -> int:
    """Attach cc.Sprite with type=FILLED (cooldown timer, radial progress).

    fill_type: 0=HORIZONTAL, 1=VERTICAL, 2=RADIAL.
    fill_range: 0~1 controls how much is filled (e.g. 0.3 = 30% filled).
    """
    return sb.add_filled_sprite(scene_path, node_id, sprite_frame_uuid,
                                fill_type, (fill_center_x, fill_center_y),
                                fill_start, fill_range,
                                (color_r, color_g, color_b, color_a))



@mcp.tool()
def cocos_add_ui_opacity(scene_path: str, node_id: int, opacity: int = 255) -> int:
    """Attach cc.UIOpacity (0=invisible, 255=opaque). Required for fade animations."""
    return sb.add_ui_opacity(scene_path, node_id, opacity)


@mcp.tool()
def cocos_add_block_input_events(scene_path: str, node_id: int) -> int:
    """Attach cc.BlockInputEvents. Blocks touch/mouse from passing through this node."""
    return sb.add_block_input_events(scene_path, node_id)


@mcp.tool()
def cocos_add_safe_area(scene_path: str, node_id: int) -> int:
    """Attach cc.SafeArea. Auto-fits node to device safe area (notch/cutout)."""
    return sb.add_safe_area(scene_path, node_id)


# =====================================================================
# Build: multi-scene & platform configuration
# =====================================================================

@mcp.tool()
def cocos_set_design_resolution(project_path: str, width: int = 960, height: int = 640,
                                fit_width: bool = True, fit_height: bool = True) -> dict:
    """Set design resolution for multi-screen adaptation.

    fit_width+fit_height=SHOW_ALL; only fit_width=FIT_WIDTH; only fit_height=FIT_HEIGHT.
    """
    return cb.set_design_resolution(project_path, width, height, fit_width, fit_height)


@mcp.tool()
def cocos_set_start_scene(project_path: str, scene_uuid: str) -> dict:
    """Set the project's start scene in settings/v2/packages/project.json.

    The engine loads this scene first at runtime.
    """
    return cb.set_start_scene(project_path, scene_uuid)


@mcp.tool()
def cocos_add_scene_to_build(project_path: str, scene_uuid: str) -> dict:
    """Add a scene to the includedScenes list in project settings.

    Idempotent -- skips if the UUID is already included.
    """
    return cb.add_scene_to_build(project_path, scene_uuid)


@mcp.tool()
def cocos_set_wechat_appid(project_path: str, appid: str) -> dict:
    """Write appid to builder.json for the wechatgame platform."""
    return cb.set_wechat_appid(project_path, appid)


@mcp.tool()
def cocos_clean_project(project_path: str, level: str = "default") -> dict:
    """Clean build artifacts. level: build/temp/library/all/default.

    'default' removes build/ + temp/. 'all' also removes library/
    (next build re-imports all assets, slow).
    """
    return cb.clean_project(project_path, level)


# =====================================================================
# Engine module configuration
# =====================================================================

@mcp.tool()
def cocos_set_engine_module(project_path: str, module_name: str, enabled: bool) -> dict:
    """Enable/disable an engine module (physics-2d-box2d, spine, dragon-bones, tiled-map, etc.).

    IMPORTANT: You MUST enable 'physics-2d-box2d' before using RigidBody2D/Collider2D,
    'spine' before using sp.Skeleton, 'dragon-bones' before DragonBones, 'tiled-map'
    before TiledMap. After changing modules, clean library+temp and rebuild.

    Common modules: physics-2d-box2d, physics-2d-builtin, spine, dragon-bones,
    tiled-map, particle-2d, audio, animation, 2d, ui, graphics, mask, rich-text,
    tween, video, webview.
    """
    return cb.set_engine_module(project_path, module_name, enabled)


@mcp.tool()
def cocos_get_engine_modules(project_path: str) -> dict:
    """List all engine modules and their enabled/disabled status."""
    return cb.get_engine_modules(project_path)


# =====================================================================
# Scene batch mode (reduce file I/O for bulk operations)
# =====================================================================

@mcp.tool()
def cocos_batch_scene_ops(scene_path: str, operations: list[dict]) -> dict:
    """Execute multiple scene operations in a single file read/write cycle.

    Each operation is a dict with 'op' key and operation-specific params.
    Returns a list of results (one per operation).

    Supported ops:
      - {"op": "add_node", "parent_id": N, "name": "X", "pos_x": 0, "pos_y": 0, ...}
      - {"op": "add_uitransform", "node_id": N, "width": W, "height": H}
      - {"op": "add_label", "node_id": N, "text": "...", "font_size": 40}
      - {"op": "add_sprite", "node_id": N, "sprite_frame_uuid": "..."}
      - {"op": "add_graphics", "node_id": N}
      - {"op": "add_component", "node_id": N, "type_name": "cc.X", "props": {...}}
      - {"op": "add_rigidbody2d", "node_id": N, "body_type": 2, ...}
      - {"op": "add_box_collider2d", "node_id": N, "width": W, ...}
      - {"op": "add_circle_collider2d", "node_id": N, "radius": R, ...}
      - {"op": "add_button", "node_id": N, ...}
      - {"op": "attach_script", "node_id": N, "script_uuid_compressed": "...", "props": {...}}
      - {"op": "link_property", "component_id": N, "prop_name": "...", "target_id": M}
      - {"op": "set_property", "object_id": N, "prop_name": "...", "value": ...}
      - {"op": "set_position", "node_id": N, "x": X, "y": Y}
      - {"op": "set_active", "node_id": N, "active": true/false}

    Node IDs returned by prior ops in the same batch can be referenced
    using "$N" where N is the 0-based op index. Example:
      [{"op": "add_node", "parent_id": 2, "name": "Bird"},
       {"op": "add_uitransform", "node_id": "$0", "width": 50, "height": 50}]
    """
    return sb.batch_ops(scene_path, operations)


if __name__ == "__main__":
    mcp.run()

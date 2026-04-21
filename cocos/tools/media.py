"""Audio / animation / particle / Spine / DragonBones / TiledMap / render extras."""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import project as cp
from cocos import scene_builder as sb

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- Audio / animation / particles ----------------

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

    # ---------------- Audio file & generic resource ----------------

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

    # ---------------- AI asset generation + atlas + animation clip ----------------

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
                                  png_paths: list[str] | None = None,
                                  rel_dir: str | None = None,
                                  max_width: int = 1024, max_height: int = 1024,
                                  padding: int = 2,
                                  power_of_two: bool = False,
                                  force_squared: bool = False,
                                  filter_unused: bool = True,
                                  algorithm: str = "MaxRects",
                                  quality: int = 80) -> dict:
        """Create an AutoAtlas bundle (Cocos 3.8 build-time packing).

        Drops a ``<atlas_name>.pac`` marker + correct meta into a folder
        (default ``assets/atlas/<name>/``). From that point on, **every
        sprite-frame PNG in that folder** is automatically packed into
        one atlas texture when ``cocos_build`` runs — no manual
        enumeration needed afterward.

        ``png_paths`` is optional. If provided, the PNGs are copied into
        the atlas folder + sprite-frame metas are written. For PNGs
        already in the folder (e.g. ``cocos_add_image(rel_path=
        "assets/atlas/<name>/foo.png")``), no copy is required; they
        are picked up at build time automatically.

        Tunables (all match Cocos Creator 3.8 defaults):
          * ``max_width`` / ``max_height`` — atlas texture size cap (1024).
          * ``padding``                    — gap between frames in px (2).
          * ``power_of_two``               — force ^2 sizes; usually off.
          * ``force_squared``              — force 1:1 aspect; usually off.
          * ``filter_unused``              — drop unreferenced sprite
                                             frames from the final bundle.
          * ``algorithm``                  — ``"MaxRects"`` (default) or
                                             ``"Basic"``.
          * ``quality``                    — 0-100 PNG quality.

        Returns ``{dir, atlas_uuid, pac_path, images, atlas_dir_rel}``.
        ``atlas_dir_rel`` is the project-relative folder — drop more
        PNGs there later to add them to the atlas without running this
        tool again.
        """
        return cp.create_sprite_atlas(
            project_path, atlas_name, png_paths, rel_dir,
            max_width=max_width, max_height=max_height, padding=padding,
            power_of_two=power_of_two, force_squared=force_squared,
            filter_unused=filter_unused, algorithm=algorithm,
            quality=quality,
        )

    @mcp.tool()
    def cocos_enable_dynamic_atlas(project_path: str,
                                   rel_path: str = "DynamicAtlasBooter.ts",
                                   max_frame_size: int = 512,
                                   class_name: str = "DynamicAtlasBooter") -> dict:
        """Generate a boot script that enables Cocos 3.8's runtime
        dynamic atlas (``dynamicAtlasManager.enabled = true``).

        Complements ``cocos_create_sprite_atlas`` — AutoAtlas packs at
        BUILD time, DynamicAtlas packs at RUN time. Turning both on
        catches small UI frames the AutoAtlas doesn't cover (e.g.
        runtime-generated text, sprite frames loaded lazily).

        The generated .ts flips the global flag on ``onLoad``; attach
        the resulting component to any persistent scene node (typically
        a GameManager). Typical flow::

            r = cocos_enable_dynamic_atlas(project)
            cocos_add_script(scene, gm_node_id, r["uuid_compressed"])

        Parameters:

        * ``rel_path``       — defaults to ``DynamicAtlasBooter.ts``
                               under ``assets/scripts/``.
        * ``max_frame_size`` — sprite frames larger than this (px) are
                               NOT batched. Engine default 512.
        * ``class_name``     — TypeScript class name on the script.

        Returns ``{path, rel_path, uuid_standard, uuid_compressed}``.
        """
        return cp.enable_dynamic_atlas(
            project_path, rel_path=rel_path,
            max_frame_size=max_frame_size, class_name=class_name,
        )

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

    # ---------------- Spine ----------------

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

    # ---------------- DragonBones ----------------

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

    # ---------------- TiledMap ----------------

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

    # ---------------- Render extras: Camera/Mask/RichText/Sprite variants ----------------

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
                           line_height: float = 40, horizontal_align: int = 0,
                           size_preset: str | None = None) -> int:
        """Attach cc.RichText. Supports <b>, <i>, <color=#FF0000>, <size=24>, <img> tags.

        ``size_preset`` (``"title"``/``"heading"``/``"body"``/``"caption"``)
        overrides font_size from the project's UI theme and sets
        line_height to ~1.25× of it.
        """
        return sb.add_richtext(scene_path, node_id, text, font_size, max_width,
                               line_height, horizontal_align,
                               size_preset=size_preset)

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

    @mcp.tool()
    def cocos_add_motion_streak(scene_path: str, node_id: int,
                                fade_time: float = 1.0, stroke: float = 64,
                                color_r: int = 255, color_g: int = 255,
                                color_b: int = 255, color_a: int = 255) -> int:
        """Attach cc.MotionStreak (trail effect). For sword trails, shooting stars."""
        return sb.add_motion_streak(scene_path, node_id, fade_time, 1, stroke,
                                    (color_r, color_g, color_b, color_a))

    @mcp.tool()
    def cocos_add_video_player(scene_path: str, node_id: int,
                               resource_type: int = 1,
                               remote_url: str = "",
                               clip_uuid: str | None = None,
                               play_on_awake: bool = True,
                               volume: float = 1.0,
                               mute: bool = False,
                               loop: bool = False,
                               keep_aspect_ratio: bool = True,
                               full_screen_on_awake: bool = False,
                               stay_on_bottom: bool = False) -> int:
        """Attach cc.VideoPlayer — plays mp4 from a local cc.VideoClip or remote URL.

        resource_type: 0=REMOTE (use remote_url), 1=LOCAL (use clip_uuid).

        Use cases:
          - Cinematic intro / cutscenes (LOCAL with clip_uuid)
          - Rewarded video ads (REMOTE with ad-server URL)
          - In-game tutorials (LOCAL, loop=True)

        On WeChat mini-game the player is a native overlay; stay_on_bottom
        and full_screen_on_awake change platform-specific layering.
        """
        return sb.add_video_player(
            scene_path, node_id, resource_type, remote_url, clip_uuid,
            play_on_awake, volume, mute, loop, keep_aspect_ratio,
            full_screen_on_awake, stay_on_bottom,
        )

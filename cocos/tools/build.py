"""Build, preview, project settings, engine modules — anything that touches the CLI or settings/."""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import build as cb

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- Headless build & preview ----------------

    @mcp.tool()
    def cocos_build(project_path: str, platform: str = "web-mobile", debug: bool = True,
                    creator_version: str | None = None, clean_temp: bool = True,
                    source_maps: bool | None = None,
                    md5_cache: bool | None = None,
                    skip_compress_texture: bool | None = None,
                    inline_enum: bool | None = None,
                    mangle_properties: bool | None = None,
                    build_options: dict | None = None) -> dict:
        """Headlessly build the project via `CocosCreator --build`.

        Common platforms:
          web-mobile, web-desktop, wechatgame, ios, android, mac, windows

        Convenience booleans for the most-tweaked release flags:
          - source_maps: emit .map files for stack-trace symbolication
          - md5_cache: append md5 hashes to asset filenames (cache busting)
          - skip_compress_texture: skip texture compression (faster iteration)
          - inline_enum: inline enum members to integer literals (smaller JS)
          - mangle_properties: minify property names (breaks reflection APIs)

        Pass None on any boolean to let Cocos's own default apply. For flags
        without an explicit param, use ``build_options={"flagName": value}``
        — explicit params still win on conflict.

        Returns {exit_code, success, duration_sec, log_tail, build_dir, artifacts,
        plus error_code/hint on failure}. First build is slow (~1-2 min);
        subsequent builds with clean_temp=False are much faster.
        """
        return cb.cli_build(project_path, platform, debug, creator_version,
                            clean_temp=clean_temp,
                            source_maps=source_maps, md5_cache=md5_cache,
                            skip_compress_texture=skip_compress_texture,
                            inline_enum=inline_enum,
                            mangle_properties=mangle_properties,
                            build_options=build_options)

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

    # ---------------- Project settings: scene / resolution / platform ----------------

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
    def cocos_set_wechat_subpackages(project_path: str,
                                     subpackages: list[dict]) -> dict:
        """Configure WeChat mini-game subpackages.

        Each entry must be {"name": "<short-id>", "root": "assets/<dir>"}.
        Example:
          [{"name": "level1", "root": "assets/levels/world1"},
           {"name": "audio",  "root": "assets/audio"}]

        WeChat hard-caps the main package at 4 MB; without subpackages
        any non-trivial game gets rejected at upload time.

        Replaces the entire subpackages list (atomic). Pair with
        cocos_set_bundle_config on each `root` folder to actually mark
        them as bundles in the asset DB.
        """
        return cb.set_wechat_subpackages(project_path, subpackages)

    @mcp.tool()
    def cocos_set_native_build_config(project_path: str, platform: str,
                                      package_name: str | None = None,
                                      orientation: str | None = None,
                                      icon_path: str | None = None,
                                      splash_path: str | None = None,
                                      ios_team_id: str | None = None,
                                      android_min_api: int | None = None,
                                      android_target_api: int | None = None,
                                      android_use_debug_keystore: bool | None = None,
                                      android_keystore_path: str | None = None,
                                      android_keystore_password: str | None = None,
                                      android_keystore_alias: str | None = None,
                                      android_keystore_alias_password: str | None = None,
                                      android_app_bundle: bool | None = None) -> dict:
        """Configure iOS or Android native build settings in builder.json.

        platform: 'ios' or 'android'.
        orientation: 'portrait' / 'landscape' / 'auto'.
        icon_path / splash_path: paths to PNG files (relative to project).
        ios_team_id: Apple Developer Team ID (10-char string).
        android_min_api / android_target_api: Android API levels (e.g. 21 / 30).
        android_use_debug_keystore=True for dev builds; set False + provide
          keystore_path/password/alias/alias_password for release signing.
        android_app_bundle: True to produce .aab instead of .apk.

        All fields are optional — None leaves existing values unchanged.
        """
        return cb.set_native_build_config(
            project_path, platform,
            package_name=package_name, orientation=orientation,
            icon_path=icon_path, splash_path=splash_path,
            ios_team_id=ios_team_id,
            android_min_api=android_min_api,
            android_target_api=android_target_api,
            android_use_debug_keystore=android_use_debug_keystore,
            android_keystore_path=android_keystore_path,
            android_keystore_password=android_keystore_password,
            android_keystore_alias=android_keystore_alias,
            android_keystore_alias_password=android_keystore_alias_password,
            android_app_bundle=android_app_bundle,
        )

    @mcp.tool()
    def cocos_set_bundle_config(project_path: str, folder_rel_path: str,
                                bundle_name: str | None = None,
                                is_bundle: bool = True,
                                priority: int = 1,
                                compression_type: dict | None = None,
                                is_remote: dict | None = None) -> dict:
        """Mark a folder as an Asset Bundle by patching its .meta sidecar.

        folder_rel_path: relative to project root, e.g. 'assets/levels/world1'.
        bundle_name: defaults to the folder's basename when None.
        priority: bundle load priority 1..N (higher = loaded first).
        compression_type: {platform: mode}. Common modes:
          - 'merge_dep'  (default for most platforms)
          - 'subpackage' (WeChat — requires also calling
                          cocos_set_wechat_subpackages with matching root)
          - 'zip'        (compress entire bundle)
          - 'none'       (no compression)
          Example: {"web-mobile": "merge_dep", "wechatgame": "subpackage"}
        is_remote: {platform: bool} to enable remote/CDN loading per platform.

        At runtime, load via `cc.assetManager.loadBundle('<bundle_name>')`.
        """
        return cb.set_bundle_config(project_path, folder_rel_path,
                                    bundle_name=bundle_name, is_bundle=is_bundle,
                                    priority=priority,
                                    compression_type=compression_type,
                                    is_remote=is_remote)

    @mcp.tool()
    def cocos_clean_project(project_path: str, level: str = "default") -> dict:
        """Clean build artifacts. level: build/temp/library/all/default.

        'default' removes build/ + temp/. 'all' also removes library/
        (next build re-imports all assets, slow).
        """
        return cb.clean_project(project_path, level)

    @mcp.tool()
    def cocos_set_physics_2d_config(project_path: str,
                                    gravity_x: float = 0, gravity_y: float = -320,
                                    fixed_time_step: float = 0.016667,
                                    velocity_iterations: int = 10,
                                    position_iterations: int = 10,
                                    allow_sleep: bool = True) -> dict:
        """Configure 2D physics: gravity, timestep, solver iterations.

        Default gravity is (0, -320). Must call this before build if using physics.
        """
        return cb.set_physics_2d_config(project_path, gravity_x, gravity_y,
                                        fixed_time_step, velocity_iterations,
                                        position_iterations, allow_sleep)

    @mcp.tool()
    def cocos_set_physics_3d_config(project_path: str,
                                    gravity_x: float = 0, gravity_y: float = -10,
                                    gravity_z: float = 0,
                                    fixed_time_step: float = 0.016667,
                                    max_sub_steps: int = 1,
                                    sleep_threshold: float = 0.1,
                                    allow_sleep: bool = True,
                                    auto_simulation: bool = True) -> dict:
        """Configure 3D physics: gravity (m/s²), timestep, sub-step cap.

        Default gravity is (0, -10, 0) in metric units (NOT pixels — 2D uses -320
        because of its pixel coord system). Writes settings/v2/packages/physics.json.
        Bump max_sub_steps to 3-4 if physics drops frames after hitches.
        """
        return cb.set_physics_3d_config(project_path, gravity_x, gravity_y, gravity_z,
                                        fixed_time_step, max_sub_steps,
                                        sleep_threshold, allow_sleep, auto_simulation)

    # ---------------- Engine module configuration ----------------

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

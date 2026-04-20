"""Cocos Creator CLI build wrapper + local preview server."""
from __future__ import annotations

import contextlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .errors import (
    BUILD_FAILED,
    BUILD_TIMEOUT,
    BUILD_TYPESCRIPT_ERROR,
    classify_build_log,
    parse_ts_errors,
)
from .project import find_creator
from .types import BuildResult, PreviewStartResult, PreviewStatusResult, PreviewStopResult

# track running preview servers: {port: (subprocess.Popen, build_dir)}
_preview_servers: dict[int, tuple] = {}

# Cross-platform tmp dir for build/preview logs (/tmp on POSIX, %TEMP% on Windows).
_LOG_DIR = Path(tempfile.gettempdir())


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Cross-platform 'is something listening on this port?' check."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
        except OSError:
            return True
    return False


def _fmt_build_opt(value: Any) -> str:
    """Encode a Python value for the ``--build "k=v;..."`` option string.

    Cocos's CLI parses the string char-by-char; semicolons + equals-signs
    are the hard separators, so we reject them in values outright (better
    than silently producing garbage build flags). Booleans must be the
    lowercase strings ``true`` / ``false``.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value)
    if ";" in s or "=" in s:
        raise ValueError(
            f"build option value {value!r} contains ';' or '=' which break "
            "Cocos CLI parsing — remove them or pre-escape"
        )
    return s


def cli_build(project_path: str | Path, platform: str = "web-mobile", debug: bool = True,
              creator_version: str | None = None, timeout_sec: int = 600,
              clean_temp: bool = True,
              source_maps: bool | None = None,
              md5_cache: bool | None = None,
              skip_compress_texture: bool | None = None,
              inline_enum: bool | None = None,
              mangle_properties: bool | None = None,
              build_options: dict[str, Any] | None = None,
              apply_patches: bool = True) -> BuildResult:
    """Run `CocosCreator --project ... --build "platform=...;debug=...;...`.

    Convenience params expose the most-commonly-tweaked Cocos CLI flags:
    ``source_maps``, ``md5_cache``, ``skip_compress_texture``, ``inline_enum``,
    ``mangle_properties`` — all booleans; pass None to let the CLI default
    apply. For anything else (e.g. ``splash.img``, per-platform flags),
    pass the k=v pairs through ``build_options``. Convenience params win
    over matching keys in ``build_options``.

    Returns:
      {
        "exit_code": int,         # 0 = success in CLI sense; 36 = build success in Cocos sense
        "success": bool,          # exit_code == 0 AND build dir exists
        "duration_sec": float,
        "log_tail": str,
        "build_dir": str | None,
        "artifacts": list[str],
      }
    """
    p = Path(project_path).expanduser().resolve()
    if not (p / "package.json").exists():
        raise FileNotFoundError(f"not a Cocos project (no package.json): {p}")

    creator = find_creator(creator_version)
    cc_exe = creator["exe"]

    if clean_temp:
        for sub in ("build", "temp"):
            shutil.rmtree(p / sub, ignore_errors=True)

    # Build the --build flag's k=v;k=v string. ``build_options`` flows in
    # first (lowest precedence); the explicit convenience params overwrite
    # any same-named keys so "I said source_maps=True" always wins.
    opts: dict[str, Any] = {"platform": platform, "debug": debug}
    if build_options:
        for k, v in build_options.items():
            opts[k] = v
    for k, v in (
        ("platform", platform),
        ("debug", debug),
        ("sourceMaps", source_maps),
        ("md5Cache", md5_cache),
        ("skipCompressTexture", skip_compress_texture),
        ("inlineEnum", inline_enum),
        ("mangleProperties", mangle_properties),
    ):
        if v is not None:
            opts[k] = v

    build_flag = ";".join(f"{k}={_fmt_build_opt(v)}" for k, v in opts.items())
    log_path = _LOG_DIR / f"cocos-build-{p.name}.log"
    cmd = [
        cc_exe,
        "--project", str(p),
        "--build", build_flag,
    ]

    start = time.time()
    timed_out = False
    with open(log_path, "w") as f:
        try:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout_sec)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            # subprocess.run already SIGKILLs the child on timeout, but we
            # lose the returncode — surface the timeout explicitly so the
            # caller doesn't confuse it with exit_code=-1 from a real crash.
            exit_code = -1
            timed_out = True
    duration = time.time() - start

    # Read tail of log
    log_tail = ""
    if log_path.exists():
        with open(log_path) as f:
            lines = f.readlines()
        log_tail = "".join(lines[-30:])

    # Cocos Creator CLI exit codes:
    #   36 = build success
    #   32 = invalid build parameters
    #   34 = unexpected errors during build
    #    0 = also reported success in some shell wrappers
    build_dir = p / "build" / platform
    success = (
        not timed_out
        and exit_code in (0, 36)
        and build_dir.exists()
        and any(build_dir.iterdir())
    )
    artifacts: list[str] = []
    if build_dir.exists():
        for entry in sorted(build_dir.glob("*"))[:20]:
            artifacts.append(str(entry.relative_to(build_dir)))

    # Post-build patches: auto-apply after a successful build so users don't
    # lose edits to files Cocos regenerates. Runs before we assemble the
    # result dict so patch info is part of the BuildResult handed back.
    patch_report: dict | None = None
    if success and apply_patches:
        from .project.post_build_patches import apply_patches as _apply
        try:
            patch_report = _apply(project_path, platform, dry_run=False)
            if not patch_report["ok"]:
                # Patches failed mid-apply. The build artifacts are still
                # valid — degrade to success=False with a clear error_code
                # so the caller sees something broke.
                success = False
        except Exception as e:
            # Defensive: never let a patch bug shadow a successful build as
            # a crash. Report it, keep success=True, surface via log.
            patch_report = {
                "platform": platform,
                "dry_run": False,
                "build_dir": str(build_dir),
                "applied": [],
                "skipped": [],
                "errors": [{"file": "<apply>", "message": str(e)}],
                "ok": False,
            }

    result: BuildResult = {
        "exit_code": exit_code,
        "success": success,
        "duration_sec": round(duration, 2),
        "log_path": str(log_path),
        "log_tail": log_tail,
        "build_dir": str(build_dir) if build_dir.exists() else None,
        "artifacts": artifacts,
    }
    if patch_report is not None:
        result["post_build_patches"] = patch_report

    # Structured error — give the LLM a recovery handle rather than a raw
    # log tail. `error_code` + `hint` are additive to `log_tail` so the
    # caller can still read the full log when a classifier misses.
    if timed_out:
        result["timed_out"] = True
        result["error_code"] = BUILD_TIMEOUT
        result["error"] = f"build killed after {timeout_sec}s timeout"
        result["hint"] = (f"raise timeout_sec above {timeout_sec} or inspect {log_path} "
                          "for where the build hung")
    elif not success:
        classified = classify_build_log(log_tail)
        if classified is not None:
            code, hint = classified
            result["error_code"] = code
            result["hint"] = hint
            # For TS errors, also surface the structured per-diagnostic list
            # so the caller can open+edit each offending file directly
            # without re-parsing the log tail.
            if code == BUILD_TYPESCRIPT_ERROR:
                ts_errors = parse_ts_errors(log_tail)
                if ts_errors:
                    result["ts_errors"] = ts_errors
        else:
            result["error_code"] = BUILD_FAILED
            result["hint"] = (f"generic build failure (exit_code={exit_code}); "
                              f"read log_tail or the full log at {log_path}")

    # If the build itself passed but post-build patches broke, overwrite the
    # (likely generic) error_code with a targeted one so the caller isn't
    # sent to grep the Cocos log for a nonexistent problem.
    if patch_report is not None and not patch_report["ok"]:
        first_err = patch_report["errors"][0]
        result["error_code"] = "POST_BUILD_PATCH_FAILED"
        result["hint"] = (
            f"post-build patch on {first_err['file']} failed: "
            f"{first_err['message']}. Build artifacts are valid; "
            "fix the patch (cocos_list_post_build_patches) or "
            "re-run with apply_patches=False to skip."
        )

    return result


def start_preview(project_path: str | Path, platform: str = "web-mobile", port: int = 8080) -> PreviewStartResult:
    """Serve build/<platform>/ over HTTP via a detached subprocess.

    Spawns ``python -m http.server`` (using the current interpreter, so this
    works on Windows / macOS / Linux without depending on a `python3` symlink
    or `bash`/`lsof`). Idempotent — first stops any preview we ourselves
    started on the same port.

    If something else is already bound to the port, returns an error result
    instead of trying to forcibly kill it (we'd have no portable way to do
    that, and silently nuking unrelated processes is the wrong default).
    """
    stop_preview(port)
    p = Path(project_path).expanduser().resolve()
    build_dir = p / "build" / platform
    if not build_dir.exists():
        raise FileNotFoundError(f"build dir not found: {build_dir}. Run cocos_build first.")

    if _port_in_use(port):
        return {
            "port": port,
            "url": None,
            "serving": str(build_dir),
            "error": (f"port {port} is already in use by another process; "
                      f"call cocos_stop_preview({port}) first or pick a different port"),
        }

    log_path = _LOG_DIR / f"cocos-preview-{port}.log"
    # `subprocess.Popen` dup()s the file descriptor, so we can close our handle
    # immediately after spawn — keeping the dangling Python file object would
    # leak the FD until GC, which matters in a long-lived MCP server.
    log_fh = open(log_path, "w")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "-d", str(build_dir)],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_fh.close()

    # Give the server a moment to bind
    time.sleep(0.4)
    if proc.poll() is not None:
        return {
            "port": port,
            "url": None,
            "serving": str(build_dir),
            "error": f"server died immediately, see {log_path}",
        }

    _preview_servers[port] = (proc, str(build_dir))

    return {
        "port": port,
        "pid": proc.pid,
        "url": f"http://localhost:{port}/",
        "serving": str(build_dir),
        "log": str(log_path),
    }


def stop_preview(port: int = 8080) -> PreviewStopResult:
    """Stop a preview started by start_preview.

    Only stops servers tracked in ``_preview_servers``. We deliberately do
    NOT try to kill arbitrary processes holding the port — that would
    require ``lsof`` (POSIX-only) plus signal-sending privileges that vary
    by platform, and silently SIGKILL-ing a process the caller didn't start
    has bitten us before.
    """
    if port in _preview_servers:
        proc, build_dir = _preview_servers.pop(port)
        # terminate() works cross-platform (SIGTERM on POSIX, TerminateProcess on Windows)
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        return {"stopped": True, "port": port, "was_serving": build_dir, "pid": proc.pid}

    return {"stopped": False, "port": port,
            "note": "no tracked preview on this port; if something else is bound, "
                    "kill it manually"}


def preview_status() -> PreviewStatusResult:
    return {
        "running": [
            {"port": port, "pid": v[0].pid, "serving": v[1]}
            for port, v in _preview_servers.items()
            if v[0].poll() is None
        ]
    }


# =====================================================================
# Multi-scene / platform configuration
# =====================================================================


def _read_project_settings(project_path: str | Path) -> tuple[Path, dict]:
    """Read settings/v2/packages/project.json, creating it if needed."""
    p = Path(project_path).expanduser().resolve()
    settings_path = p / "settings" / "v2" / "packages" / "project.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.exists():
        with open(settings_path) as f:
            data = json.load(f)
    else:
        data = {}
    return settings_path, data


def _write_project_settings(settings_path: Path, data: dict) -> None:
    with open(settings_path, "w") as f:
        json.dump(data, f, indent=2)


def set_start_scene(project_path: str | Path, scene_uuid: str) -> dict:
    """Update settings/v2/packages/project.json to set startScene.

    Sets ``general.startScene`` to the given scene UUID so the engine
    loads it first at runtime.
    """
    settings_path, data = _read_project_settings(project_path)
    general = data.setdefault("general", {})
    general["startScene"] = scene_uuid
    _write_project_settings(settings_path, data)
    return {
        "settings_path": str(settings_path),
        "startScene": scene_uuid,
    }


def add_scene_to_build(project_path: str | Path, scene_uuid: str) -> dict:
    """Add a scene to the includedScenes list in project settings.

    Ensures ``general.includedScenes`` contains the given UUID.
    Idempotent -- does nothing if the UUID is already present.
    """
    settings_path, data = _read_project_settings(project_path)
    general = data.setdefault("general", {})
    scenes: list[str] = general.setdefault("includedScenes", [])
    if scene_uuid not in scenes:
        scenes.append(scene_uuid)
    _write_project_settings(settings_path, data)
    return {
        "settings_path": str(settings_path),
        "includedScenes": scenes,
    }


def _read_builder_json(project_path: str | Path) -> tuple[Path, dict]:
    """Read settings/v2/packages/builder.json, creating an empty dict if missing."""
    p = Path(project_path).expanduser().resolve()
    builder_path = p / "settings" / "v2" / "packages" / "builder.json"
    builder_path.parent.mkdir(parents=True, exist_ok=True)
    if builder_path.exists():
        with open(builder_path) as f:
            return builder_path, json.load(f)
    return builder_path, {}


def _write_builder_json(builder_path: Path, data: dict) -> None:
    with open(builder_path, "w") as f:
        json.dump(data, f, indent=2)


def set_wechat_appid(project_path: str | Path, appid: str) -> dict:
    """Write appid to builder.json for the wechatgame platform.

    Creates or patches ``settings/v2/packages/builder.json`` with
    ``wechatgame.appid``.
    """
    builder_path, data = _read_builder_json(project_path)
    wechat = data.setdefault("wechatgame", {})
    wechat["appid"] = appid
    _write_builder_json(builder_path, data)
    return {
        "builder_path": str(builder_path),
        "appid": appid,
    }


def set_wechat_subpackages(project_path: str | Path,
                           subpackages: list[dict]) -> dict:
    """Configure WeChat mini-game subpackages in builder.json.

    Each entry: {"name": "<short-id>", "root": "assets/<dir>"}.
    The 4 MB main-package limit is the most common reason WeChat builds get
    rejected; subpackages let levels/audio/textures load lazily on demand.

    Replaces the entire subpackages list (atomic). Returns the saved entries.
    """
    for sp in subpackages:
        if not isinstance(sp, dict) or "name" not in sp or "root" not in sp:
            raise ValueError(f"each subpackage must be {{'name': str, 'root': str}}, got {sp!r}")
    builder_path, data = _read_builder_json(project_path)
    wechat = data.setdefault("wechatgame", {})
    wechat["subpackages"] = list(subpackages)
    _write_builder_json(builder_path, data)
    return {
        "builder_path": str(builder_path),
        "subpackages": wechat["subpackages"],
    }


def set_native_build_config(project_path: str | Path,
                            platform: str,
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
    """Configure iOS / Android native build settings in builder.json.

    `platform` must be 'ios' or 'android'. All other fields are optional —
    pass None to leave existing values unchanged.

    `orientation`: 'portrait' / 'landscape' / 'auto'. Builds Cocos's bitmask
    {portrait, upsideDown, landscapeLeft, landscapeRight}.

    The iOS-specific args are ignored on android (and vice-versa).
    """
    if platform not in ("ios", "android"):
        raise ValueError(f"platform must be 'ios' or 'android', got {platform!r}")

    builder_path, data = _read_builder_json(project_path)
    cfg = data.setdefault(platform, {})

    if package_name is not None:
        cfg["packageName"] = package_name

    if orientation is not None:
        ori = {"portrait": False, "upsideDown": False,
               "landscapeLeft": False, "landscapeRight": False}
        if orientation == "portrait":
            ori["portrait"] = True
        elif orientation == "landscape":
            ori["landscapeLeft"] = True
            ori["landscapeRight"] = True
        elif orientation == "auto":
            for k in ori:
                ori[k] = True
        else:
            raise ValueError(f"orientation must be portrait/landscape/auto, got {orientation!r}")
        cfg["orientation"] = ori

    if icon_path is not None:
        cfg["icon"] = icon_path
    if splash_path is not None:
        cfg["splash"] = splash_path

    if platform == "ios":
        if ios_team_id is not None:
            cfg["iosTeamID"] = ios_team_id
    else:  # android
        if android_min_api is not None:
            cfg["minApiLevel"] = android_min_api
        if android_target_api is not None:
            cfg["targetApiLevel"] = android_target_api
        if android_use_debug_keystore is not None:
            cfg["useDebugKeystore"] = android_use_debug_keystore
        if android_keystore_path is not None:
            cfg["keystorePath"] = android_keystore_path
        if android_keystore_password is not None:
            cfg["keystorePassword"] = android_keystore_password
        if android_keystore_alias is not None:
            cfg["keystoreAlias"] = android_keystore_alias
        if android_keystore_alias_password is not None:
            cfg["keystoreAliasPassword"] = android_keystore_alias_password
        if android_app_bundle is not None:
            cfg["appBundle"] = android_app_bundle

    _write_builder_json(builder_path, data)
    return {
        "builder_path": str(builder_path),
        "platform": platform,
        "config": cfg,
    }


def set_bundle_config(project_path: str | Path,
                      folder_rel_path: str,
                      bundle_name: str | None = None,
                      is_bundle: bool = True,
                      priority: int = 1,
                      compression_type: dict | None = None,
                      is_remote: dict | None = None) -> dict:
    """Mark a folder as an Asset Bundle by patching its directory .meta.

    `folder_rel_path` is relative to project root, e.g. 'assets/levels/world1'.
    `bundle_name` defaults to the folder's basename when None.
    `compression_type`: {platform: mode}, e.g.
        {"web-mobile": "merge_dep", "wechatgame": "subpackage", "android": "merge_dep"}.
    `is_remote`: {platform: bool}, mark the bundle for remote loading.

    Cocos Creator's CLI build packs each marked folder into its own bundle
    that the runtime loads via `AssetManager.loadBundle('<bundle_name>')`.
    Critical for multi-MB games that need lazy / level-by-level loading.
    """
    p = Path(project_path).expanduser().resolve()
    folder = p / folder_rel_path
    if not folder.is_dir():
        raise FileNotFoundError(f"not a directory: {folder}")

    meta_path = folder.with_suffix(folder.suffix + ".meta") if folder.suffix \
        else Path(str(folder) + ".meta")
    # Cocos uses <folder>.meta as a sibling, not <folder>/.meta
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
    else:
        # Generate a minimal directory meta if Creator hasn't seen the folder yet
        from .uuid_util import new_uuid
        meta = {
            "ver": "1.2.0",
            "importer": "directory",
            "imported": True,
            "uuid": new_uuid(),
            "files": [],
            "subMetas": {},
            "userData": {},
        }

    user = meta.setdefault("userData", {})
    user["isBundle"] = is_bundle
    user["bundleName"] = bundle_name or folder.name
    user["priority"] = priority
    if compression_type is not None:
        user["compressionType"] = dict(compression_type)
    if is_remote is not None:
        user["isRemoteBundle"] = dict(is_remote)

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return {
        "meta_path": str(meta_path),
        "folder": str(folder),
        "bundle_name": user["bundleName"],
        "is_bundle": is_bundle,
        "userData": user,
    }


def clean_project(project_path: str | Path, level: str = "default") -> dict:
    """Clean build artifacts.

    Levels:
      - ``build``   -- remove build/ only
      - ``temp``    -- remove temp/ only
      - ``library`` -- remove library/ (next build re-imports all assets)
      - ``all``     -- remove build/ + temp/ + library/
      - ``default`` -- remove build/ + temp/ (safe default)

    Raises ``ValueError`` on unknown level — previously this silently fell
    back to "default", which meant typos like "lib" (intending "library")
    would skip the actual library/ dir without warning.

    Returns a dict listing which directories were removed.
    """
    p = Path(project_path).expanduser().resolve()
    targets: dict[str, list[str]] = {
        "build": ["build"],
        "temp": ["temp"],
        "library": ["library"],
        "all": ["build", "temp", "library"],
        "default": ["build", "temp"],
    }
    if level not in targets:
        raise ValueError(
            f"clean_project: unknown level {level!r}. "
            f"Valid: {sorted(targets.keys())}"
        )
    dirs = targets[level]
    removed: list[str] = []
    for d in dirs:
        target = p / d
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed.append(d)
    return {
        "project_path": str(p),
        "level": level,
        "removed": removed,
    }


# =====================================================================
# Engine module configuration
# =====================================================================

def set_design_resolution(project_path: str | Path, width: int = 960, height: int = 640,
                          fit_width: bool = True, fit_height: bool = True) -> dict:
    """Set the design resolution in project settings.

    Controls how the game scales across different screen sizes.
    fit_width=True keeps width fixed; fit_height=True keeps height fixed.
    Both True = SHOW_ALL; both False = EXACT_FIT.
    """
    settings_path, data = _read_project_settings(project_path)
    general = data.setdefault("general", {})
    general["designResolution"] = {
        "width": width,
        "height": height,
        "fitWidth": fit_width,
        "fitHeight": fit_height,
    }
    _write_project_settings(settings_path, data)
    return {
        "settings_path": str(settings_path),
        "designResolution": general["designResolution"],
    }


def _read_engine_settings(project_path: str | Path) -> tuple[Path, dict]:
    p = Path(project_path).expanduser().resolve()
    engine_path = p / "settings" / "v2" / "packages" / "engine.json"
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    if engine_path.exists():
        with open(engine_path) as f:
            data = json.load(f)
    else:
        data = {}
    return engine_path, data


def _write_engine_settings(engine_path: Path, data: dict) -> None:
    with open(engine_path, "w") as f:
        json.dump(data, f, indent=4)


def set_engine_module(project_path: str | Path, module_name: str, enabled: bool) -> dict:
    """Enable or disable an engine module in settings/v2/packages/engine.json.

    Common modules:
      - physics-2d-box2d (Box2D physics — MUST enable for RigidBody2D/Collider2D)
      - physics-2d-builtin (lightweight physics, no full box2d)
      - spine (Spine skeletal animation — sp.Skeleton)
      - dragon-bones (DragonBones skeletal animation)
      - tiled-map (TiledMap support)
      - particle-2d (ParticleSystem2D)
      - audio (AudioSource)
      - animation (Animation component)
      - 2d / ui / graphics / mask / rich-text / tween / video / webview

    After enabling a module, you must clear library + temp and rebuild.
    """
    engine_path, data = _read_engine_settings(project_path)

    # Navigate to modules.configs.defaultConfig.cache.<module>._value
    modules = data.setdefault("modules", {})
    configs = modules.setdefault("configs", {})
    default_config = configs.setdefault("defaultConfig", {})
    cache = default_config.setdefault("cache", {})
    include_list = default_config.setdefault("includeModules", [])

    # Set the cache flag
    mod_entry = cache.setdefault(module_name, {})
    mod_entry["_value"] = enabled

    # Update includeModules list
    if enabled and module_name not in include_list:
        include_list.append(module_name)
    elif not enabled and module_name in include_list:
        include_list.remove(module_name)

    # Handle physics-2d parent module
    if module_name in ("physics-2d-box2d", "physics-2d-builtin"):
        physics_2d = cache.setdefault("physics-2d", {})
        if enabled:
            physics_2d["_value"] = True
            physics_2d["_option"] = module_name
        # Don't auto-disable parent when disabling sub

    _write_engine_settings(engine_path, data)

    return {
        "engine_path": str(engine_path),
        "module": module_name,
        "enabled": enabled,
        "includeModules": include_list,
    }


def get_engine_modules(project_path: str | Path) -> dict:
    """List all engine modules and their enabled/disabled status."""
    _, data = _read_engine_settings(project_path)
    cache = (data.get("modules", {}).get("configs", {})
             .get("defaultConfig", {}).get("cache", {}))
    include = (data.get("modules", {}).get("configs", {})
               .get("defaultConfig", {}).get("includeModules", []))
    modules = {}
    for name, entry in cache.items():
        modules[name] = entry.get("_value", False)
    return {
        "modules": modules,
        "includeModules": include,
    }


def set_physics_2d_config(project_path: str | Path,
                          gravity_x: float = 0, gravity_y: float = -320,
                          fixed_time_step: float = 1/60,
                          velocity_iterations: int = 10,
                          position_iterations: int = 10,
                          allow_sleep: bool = True) -> dict:
    """Configure 2D physics system in project settings.

    IMPORTANT: Cocos Creator's default gravity is (0, -320) in pixel units.
    If your physics objects don't fall, check this setting.

    This writes to settings/v2/packages/project.json under 'physics'.
    """
    settings_path, data = _read_project_settings(project_path)
    physics = data.setdefault("physics", {})
    physics["gravity"] = {"x": gravity_x, "y": gravity_y}
    physics["fixedTimeStep"] = fixed_time_step
    physics["velocityIterations"] = velocity_iterations
    physics["positionIterations"] = position_iterations
    physics["allowSleep"] = allow_sleep
    _write_project_settings(settings_path, data)
    return {
        "settings_path": str(settings_path),
        "physics": physics,
    }


def set_physics_3d_config(project_path: str | Path,
                          gravity_x: float = 0, gravity_y: float = -10,
                          gravity_z: float = 0,
                          fixed_time_step: float = 1/60,
                          max_sub_steps: int = 1,
                          sleep_threshold: float = 0.1,
                          allow_sleep: bool = True,
                          auto_simulation: bool = True) -> dict:
    """Configure 3D physics system in project settings.

    Default gravity is (0, -10, 0) — metric units (m/s²) unlike the 2D
    system's pixel units. Writes to ``settings/v2/packages/physics.json``
    which the engine reads alongside the per-scene 2D physics block.

    ``max_sub_steps`` caps the number of physics sub-steps per frame when
    the frame takes longer than ``fixed_time_step`` — bump to 3-4 if you
    see physics lag after a frame hitch.
    """
    p = Path(project_path).expanduser().resolve()
    physics_path = p / "settings" / "v2" / "packages" / "physics.json"
    physics_path.parent.mkdir(parents=True, exist_ok=True)
    if physics_path.exists():
        with open(physics_path) as f:
            data = json.load(f)
    else:
        data = {}
    data["gravity"] = {"x": gravity_x, "y": gravity_y, "z": gravity_z}
    data["fixedTimeStep"] = fixed_time_step
    data["maxSubSteps"] = max_sub_steps
    data["sleepThreshold"] = sleep_threshold
    data["allowSleep"] = allow_sleep
    data["autoSimulation"] = auto_simulation
    with open(physics_path, "w") as f:
        json.dump(data, f, indent=2)
    return {
        "settings_path": str(physics_path),
        "physics": data,
    }

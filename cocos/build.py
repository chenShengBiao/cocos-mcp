"""Cocos Creator CLI build wrapper + local preview server."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from .project import find_creator, get_project_info

# track running preview servers: {port: (subprocess.Popen, build_dir)}
_preview_servers: dict[int, tuple] = {}


def cli_build(project_path: str | Path, platform: str = "web-mobile", debug: bool = True,
              creator_version: str | None = None, timeout_sec: int = 600,
              clean_temp: bool = True) -> dict:
    """Run `CocosCreator --project ... --build "platform=...;debug=..."`.

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

    log_path = Path("/tmp") / f"cocos-build-{p.name}.log"
    cmd = [
        cc_exe,
        "--project", str(p),
        "--build", f"platform={platform};debug={'true' if debug else 'false'}",
    ]

    start = time.time()
    with open(log_path, "w") as f:
        try:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout_sec)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            exit_code = -1
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
        exit_code in (0, 36)
        and build_dir.exists()
        and any(build_dir.iterdir())
    )
    artifacts = []
    if build_dir.exists():
        for f in sorted(build_dir.glob("*"))[:20]:
            artifacts.append(str(f.relative_to(build_dir)))

    return {
        "exit_code": exit_code,
        "success": success,
        "duration_sec": round(duration, 2),
        "log_path": str(log_path),
        "log_tail": log_tail,
        "build_dir": str(build_dir) if build_dir.exists() else None,
        "artifacts": artifacts,
    }


def start_preview(project_path: str | Path, platform: str = "web-mobile", port: int = 8080) -> dict:
    """Serve build/<platform>/ over HTTP via a detached subprocess.

    Uses an out-of-process `python3 -m http.server` so the preview survives
    even if the calling MCP tool / Python interpreter exits. Idempotent —
    stops any existing server on the same port first.
    """
    stop_preview(port)
    p = Path(project_path).expanduser().resolve()
    build_dir = p / "build" / platform
    if not build_dir.exists():
        raise FileNotFoundError(f"build dir not found: {build_dir}. Run cocos_build first.")

    # Also kill anything currently bound to the port (e.g. from a prior run
    # in another process that we don't have a Popen handle for)
    try:
        subprocess.run(
            ["bash", "-c", f"lsof -ti :{port} | xargs -r kill -9"],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass

    log_path = Path("/tmp") / f"cocos-preview-{port}.log"
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(port)],
        cwd=str(build_dir),
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        preexec_fn=os.setpgrp,  # detach from parent's process group
    )
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


def stop_preview(port: int = 8080) -> dict:
    # First handle servers we ourselves started
    if port in _preview_servers:
        proc, build_dir = _preview_servers.pop(port)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        return {"stopped": True, "port": port, "was_serving": build_dir, "pid": proc.pid}

    # Otherwise try to kill anyone holding the port
    try:
        result = subprocess.run(
            ["bash", "-c", f"lsof -ti :{port}"],
            capture_output=True, text=True, timeout=3,
        )
        pids = result.stdout.strip().split("\n") if result.stdout.strip() else []
        if pids:
            subprocess.run(["bash", "-c", f"kill -9 {' '.join(pids)}"], timeout=3)
            return {"stopped": True, "port": port, "killed_pids": pids}
    except Exception:
        pass
    return {"stopped": False, "port": port}


def preview_status() -> dict:
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

import json


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


def set_wechat_appid(project_path: str | Path, appid: str) -> dict:
    """Write appid to builder.json for the wechatgame platform.

    Creates or patches ``settings/v2/packages/builder.json`` with
    ``wechatgame.appid``.
    """
    p = Path(project_path).expanduser().resolve()
    builder_path = p / "settings" / "v2" / "packages" / "builder.json"
    builder_path.parent.mkdir(parents=True, exist_ok=True)
    if builder_path.exists():
        with open(builder_path) as f:
            data = json.load(f)
    else:
        data = {}
    wechat = data.setdefault("wechatgame", {})
    wechat["appid"] = appid
    with open(builder_path, "w") as f:
        json.dump(data, f, indent=2)
    return {
        "builder_path": str(builder_path),
        "appid": appid,
    }


def clean_project(project_path: str | Path, level: str = "default") -> dict:
    """Clean build artifacts.

    Levels:
      - ``build``   -- remove build/ only
      - ``temp``    -- remove temp/ only
      - ``library`` -- remove library/ (next build re-imports all assets)
      - ``all``     -- remove build/ + temp/ + library/
      - ``default`` -- remove build/ + temp/ (safe default)

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
    dirs = targets.get(level, targets["default"])
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
    engine_path, data = _read_engine_settings(project_path)
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

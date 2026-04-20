"""Scene component ↔ engine-module mapping + scene audit.

Cocos Creator ships most subsystems (physics-2d/3d, spine, dragon-bones,
tiled-map, particle-2d, audio, animation, video, webview, ...) as opt-in
modules configured in ``settings/v2/packages/engine.json``. A build with
a disabled module still *produces* working artifacts — the scene JSON is
fine, `cocos_build` returns success — but at runtime, components of
that type are dark no-ops and the user sees nothing and gets no stack
trace. This is one of the top two "build succeeded but game broken"
failure modes the project logs.

``audit_scene_modules`` scans a scene, maps each ``__type__`` to its
required module, and cross-checks against the project's current engine.json
so the caller (typically the orchestrating LLM) can pre-flight before
hitting ``cocos_build``.

The mapping is intentionally conservative — we only list the types where
experience shows "required module missing" is the actual runtime failure
mode. Most UI components (Button / Label / Sprite / ...) don't need
anything beyond the ``ui`` / ``2d`` modules that Creator keeps on by
default, so they're absent from the table. If a component attaches
cleanly but behaves oddly at runtime and isn't listed here, check the
engine source for its required module and add it.
"""
from __future__ import annotations

import json
from pathlib import Path

from ._helpers import _load_scene

# ``__type__`` string → engine module name (as seen in engine.json
# ``modules.configs.defaultConfig.cache.<name>._value``).
#
# Some physics types have a choice of backend (box2d vs builtin for 2D;
# physX/bullet/cannon for 3D); we point at the *parent* module
# (``physics-2d``, ``physics``) because Cocos treats the backend choice
# as a sub-option of the parent. The full engine module list is in
# ``editor/inspector/assets/modules.ts`` in cocos-engine.
COMPONENT_REQUIRES_MODULE: dict[str, str] = {
    # 2D physics
    "cc.RigidBody2D": "physics-2d",
    "cc.BoxCollider2D": "physics-2d",
    "cc.CircleCollider2D": "physics-2d",
    "cc.PolygonCollider2D": "physics-2d",
    "cc.DistanceJoint2D": "physics-2d",
    "cc.FixedJoint2D": "physics-2d",
    "cc.HingeJoint2D": "physics-2d",
    "cc.MouseJoint2D": "physics-2d",
    "cc.RelativeJoint2D": "physics-2d",
    "cc.SliderJoint2D": "physics-2d",
    "cc.SpringJoint2D": "physics-2d",
    "cc.WheelJoint2D": "physics-2d",

    # 3D physics
    "cc.RigidBody": "physics",
    "cc.BoxCollider": "physics",
    "cc.SphereCollider": "physics",
    "cc.CapsuleCollider": "physics",
    "cc.CylinderCollider": "physics",
    "cc.ConeCollider": "physics",
    "cc.MeshCollider": "physics",
    "cc.PlaneCollider": "physics",
    "cc.TerrainCollider": "physics",
    "cc.BoxCharacterController": "physics",
    "cc.CapsuleCharacterController": "physics",

    # Plug-ins
    "sp.Skeleton": "spine",
    "dragonBones.ArmatureDisplay": "dragon-bones",
    "cc.TiledMap": "tiled-map",
    "cc.TiledLayer": "tiled-map",
    "cc.ParticleSystem2D": "particle-2d",
    "cc.VideoPlayer": "video",
    "cc.WebView": "webview",
    "cc.Terrain": "terrain",

    # Animation system
    "cc.Animation": "animation",
    "cc.SkinnedMeshRenderer": "animation",
    "cc.SkeletalAnimation": "animation",

    # 3D rendering. ``cc.Camera`` is intentionally NOT in this map —
    # every UI-only scene created by ``create_empty_scene`` attaches one
    # for the UI projection, and 2D-only builds work fine without the
    # base-3d module. Only the genuinely 3D-exclusive renderers need it.
    "cc.MeshRenderer": "base-3d",
    "cc.DirectionalLight": "base-3d",
    "cc.SphereLight": "base-3d",
    "cc.SpotLight": "base-3d",
}


def _find_project_from_scene(scene_path: str | Path) -> Path | None:
    """Walk up from a scene file until we find package.json (the project
    root marker). Returns None if we never find one — caller should fall
    back to a project_path argument instead of silently giving up."""
    cur = Path(scene_path).expanduser().resolve().parent
    while True:
        if (cur / "package.json").exists():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent


def _required_modules_in_scene(scene_path: str | Path) -> dict[str, list[int]]:
    """Return ``{module_name: [obj_idx, ...]}`` for every component in
    the scene whose ``__type__`` is in COMPONENT_REQUIRES_MODULE.

    Indices are kept so the caller can show exactly which objects depend
    on each missing module, which is much more actionable than a bare
    module list.
    """
    scene = _load_scene(scene_path)
    out: dict[str, list[int]] = {}
    for i, obj in enumerate(scene):
        if not isinstance(obj, dict):
            continue
        module = COMPONENT_REQUIRES_MODULE.get(obj.get("__type__", ""))
        if module is None:
            continue
        out.setdefault(module, []).append(i)
    return out


def _engine_modules_enabled(project_path: Path) -> dict[str, bool]:
    """Parse engine.json and return ``{module_name: enabled}``. Absent
    modules are reported as False (unknown ≡ off for our audit purposes).

    Missing engine.json is treated as "no modules configured, nothing on
    yet" — user should either save the project in Creator once, or call
    cocos_set_engine_module for the modules they need.
    """
    engine_json = project_path / "settings" / "v2" / "packages" / "engine.json"
    if not engine_json.exists():
        return {}
    try:
        with open(engine_json) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    cache = (data.get("modules", {}).get("configs", {})
             .get("defaultConfig", {}).get("cache", {}))
    return {name: bool(entry.get("_value", False))
            for name, entry in cache.items() if isinstance(entry, dict)}


def audit_scene_modules(scene_path: str | Path,
                        project_path: str | Path | None = None) -> dict:
    """Cross-check a scene's components against the project's engine.json.

    Returns::

        {
            "ok": bool,               # True iff no required modules are off
            "project_path": str,      # resolved project root we used
            "required": {module: [obj_idx, ...]},
            "enabled": [module_name, ...],   # modules currently ON
            "disabled": [module_name, ...],  # required-but-off (the actionable set)
            "actions": [str, ...],    # suggested cocos_set_engine_module calls
        }

    When ``project_path`` is None, walks up from the scene file to locate
    the enclosing ``package.json``. If there isn't one, raises
    ``FileNotFoundError`` with a hint — we can't know which engine.json
    to check otherwise.
    """
    if project_path is None:
        found = _find_project_from_scene(scene_path)
        if found is None:
            raise FileNotFoundError(
                f"couldn't locate the project root above {scene_path}. "
                "Pass project_path explicitly."
            )
        project_path = found
    else:
        project_path = Path(project_path).expanduser().resolve()

    required = _required_modules_in_scene(scene_path)
    enabled_map = _engine_modules_enabled(Path(project_path))
    enabled_names = sorted(name for name, on in enabled_map.items() if on)

    # physics-2d is satisfied if either physics-2d-box2d or physics-2d-builtin
    # is on AND the parent physics-2d is on. Cocos's Creator inspector enforces
    # the pairing; audit should match that — if only the backend sub-module is
    # on without the parent, the cache write is inconsistent but at runtime the
    # components still don't register.
    def _module_effectively_on(name: str) -> bool:
        if enabled_map.get(name):
            return True
        if name == "physics-2d":
            return bool(enabled_map.get("physics-2d-box2d")
                        or enabled_map.get("physics-2d-builtin"))
        return False

    disabled: list[str] = []
    for module in required:
        if not _module_effectively_on(module):
            disabled.append(module)
    disabled.sort()

    # Emit copy-pasteable next steps for the caller. Physics-2d defaults
    # to Box2D since that's what the RigidBody2D joint suite targets.
    actions: list[str] = []
    for module in disabled:
        if module == "physics-2d":
            actions.append(
                "cocos_set_engine_module(project_path, 'physics-2d-box2d', True) "
                "# enables both parent + backend"
            )
        else:
            actions.append(f"cocos_set_engine_module(project_path, '{module}', True)")
    if disabled:
        actions.append(
            "cocos_clean_project(project_path, 'library')  "
            "# module changes require re-import"
        )

    return {
        "ok": not disabled,
        "project_path": str(project_path),
        "required": {m: idxs for m, idxs in required.items()},
        "enabled": enabled_names,
        "disabled": disabled,
        "actions": actions,
    }

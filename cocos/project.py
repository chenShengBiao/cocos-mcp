"""Cocos Creator project management — install detection, init, asset add."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .meta_util import script_ts_meta, write_meta, new_sprite_frame_meta
from .uuid_util import new_uuid

# Where Cocos Dashboard installs Creator on each platform
INSTALL_ROOTS = {
    "darwin": [Path("/Applications/Cocos/Creator")],
    "win32": [Path("C:/CocosDashboard/Creator"), Path("C:/Program Files/Cocos/Creator")],
    "linux": [Path("/opt/Cocos/Creator")],
}


def list_creator_installs() -> list[dict]:
    """Return all locally installed Cocos Creator versions."""
    import sys
    roots = INSTALL_ROOTS.get(sys.platform, [Path("/Applications/Cocos/Creator")])
    out = []
    for root in roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            version = child.name
            if sys.platform == "darwin":
                exe = child / "CocosCreator.app/Contents/MacOS/CocosCreator"
                template_dir = child / "CocosCreator.app/Contents/Resources/templates"
            elif sys.platform == "win32":
                exe = child / "CocosCreator.exe"
                template_dir = child / "resources/templates"
            else:
                exe = child / "CocosCreator"
                template_dir = child / "resources/templates"
            if exe.exists():
                out.append({
                    "version": version,
                    "exe": str(exe),
                    "template_dir": str(template_dir) if template_dir.exists() else None,
                })
    return out


def find_creator(version_prefix: str | None = None) -> dict:
    """Find a specific or the latest installed Creator."""
    installs = list_creator_installs()
    if not installs:
        raise RuntimeError("no Cocos Creator install found locally")
    if version_prefix:
        installs = [i for i in installs if i["version"].startswith(version_prefix)]
        if not installs:
            raise RuntimeError(f"no Creator install matching {version_prefix!r}")
    # Sort by version (string compare works for x.y.z forms)
    installs.sort(key=lambda i: i["version"], reverse=True)
    return installs[0]


def init_project(dst_path: str | Path, creator_version: str | None = None,
                 template: str = "empty-2d", project_name: str | None = None) -> dict:
    """Copy a Creator template into `dst_path` and patch package.json.

    Returns paths to the new project + the Creator exe used.
    """
    creator = find_creator(creator_version)
    template_dir = Path(creator["template_dir"]) / template
    if not template_dir.exists():
        avail = [p.name for p in Path(creator["template_dir"]).iterdir() if p.is_dir()]
        raise FileNotFoundError(f"template {template!r} not found. Available: {avail}")

    dst = Path(dst_path).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)

    # Copy template contents (including dotfiles)
    for item in template_dir.iterdir():
        target = dst / item.name
        if target.exists():
            continue  # don't overwrite
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    # Patch package.json
    pkg_path = dst / "package.json"
    if pkg_path.exists():
        with open(pkg_path) as f:
            pkg = json.load(f)
    else:
        pkg = {}
    name = project_name or dst.name
    project_uuid = new_uuid()
    pkg.update({
        "creator": {"version": creator["version"]},
        "name": name,
        "type": "2d" if "2d" in template else "3d",
        "uuid": project_uuid,
        "version": pkg.get("version", "0.1.0"),
    })
    with open(pkg_path, "w") as f:
        json.dump(pkg, f, indent=2)

    # Create assets dirs
    for sub in ("scenes", "scripts", "textures", "prefabs", "resources"):
        (dst / "assets" / sub).mkdir(parents=True, exist_ok=True)

    return {
        "project_path": str(dst),
        "project_uuid": project_uuid,
        "creator_version": creator["version"],
        "creator_exe": creator["exe"],
        "template": template,
    }


def get_project_info(project_path: str | Path) -> dict:
    """Read package.json and a few other diagnostic facts."""
    p = Path(project_path).expanduser().resolve()
    info = {"project_path": str(p)}
    pkg_path = p / "package.json"
    if pkg_path.exists():
        with open(pkg_path) as f:
            info["package"] = json.load(f)
    info["assets_exists"] = (p / "assets").exists()
    info["library_built"] = (p / "library").exists()
    info["build_dir"] = str(p / "build") if (p / "build").exists() else None
    info["scenes"] = [str(s.relative_to(p)) for s in p.glob("assets/**/*.scene")]
    info["scripts"] = [str(s.relative_to(p)) for s in p.glob("assets/**/*.ts")]
    info["images"] = [str(s.relative_to(p)) for s in p.glob("assets/**/*.png")]
    return info


def add_script(project_path: str | Path, rel_path: str, source: str, uuid: str | None = None) -> dict:
    """Write a TypeScript script + its meta into the project."""
    p = Path(project_path).expanduser().resolve()
    rel = rel_path.lstrip("/")
    if not rel.startswith("assets/"):
        rel = f"assets/scripts/{rel}"
    if not rel.endswith(".ts"):
        rel = f"{rel}.ts"
    target = p / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    with open(target, "w") as f:
        f.write(source)

    meta = script_ts_meta(uuid=uuid)
    write_meta(target, meta)

    return {
        "path": str(target),
        "rel_path": rel,
        "uuid": meta["uuid"],
    }


def add_image(project_path: str | Path, src_png: str | Path, rel_path: str | None = None,
              uuid: str | None = None, as_resource: bool = False) -> dict:
    """Copy a PNG into project + write sprite-frame meta.

    Default location: assets/textures/. If as_resource=True, places it under
    assets/resources/ so it can be loaded at runtime via resources.load().
    """
    p = Path(project_path).expanduser().resolve()
    src = Path(src_png).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"source PNG not found: {src}")

    default_dir = "assets/resources" if as_resource else "assets/textures"
    if rel_path:
        rel = rel_path.lstrip("/")
        if not rel.startswith("assets/"):
            rel = f"{default_dir}/{rel}"
    else:
        rel = f"{default_dir}/{src.name}"

    if not rel.endswith(".png"):
        rel = f"{rel}.png"

    target = p / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)

    meta = new_sprite_frame_meta(target, name=target.stem, uuid=uuid)
    write_meta(target, meta)

    main_uuid = meta["uuid"]
    return {
        "path": str(target),
        "rel_path": rel,
        "main_uuid": main_uuid,
        "sprite_frame_uuid": f"{main_uuid}@f9941",
        "texture_uuid": f"{main_uuid}@6c48a",
    }


def list_assets(project_path: str | Path) -> dict:
    """List all assets and their UUIDs."""
    p = Path(project_path).expanduser().resolve()
    assets = {"scripts": [], "scenes": [], "images": [], "prefabs": []}

    def _read_uuid(meta_path: Path):
        try:
            with open(meta_path) as f:
                return json.load(f).get("uuid")
        except Exception:
            return None

    for ts in p.glob("assets/**/*.ts"):
        meta = ts.with_suffix(".ts.meta")
        if meta.exists():
            assets["scripts"].append({
                "rel": str(ts.relative_to(p)),
                "uuid": _read_uuid(meta),
            })

    for scn in p.glob("assets/**/*.scene"):
        meta = Path(f"{scn}.meta")
        if meta.exists():
            assets["scenes"].append({
                "rel": str(scn.relative_to(p)),
                "uuid": _read_uuid(meta),
            })

    for png in p.glob("assets/**/*.png"):
        meta = Path(f"{png}.meta")
        if meta.exists():
            with open(meta) as f:
                m = json.load(f)
            uuid = m.get("uuid")
            sub = m.get("subMetas", {})
            assets["images"].append({
                "rel": str(png.relative_to(p)),
                "main_uuid": uuid,
                "type": m.get("userData", {}).get("type", "texture"),
                "sprite_frame_uuid": f"{uuid}@f9941" if "f9941" in sub else None,
            })

    for pf in p.glob("assets/**/*.prefab"):
        meta = Path(f"{pf}.meta")
        if meta.exists():
            assets["prefabs"].append({
                "rel": str(pf.relative_to(p)),
                "uuid": _read_uuid(meta),
            })

    return assets


def add_audio_file(project_path: str | Path, src_path: str | Path,
                   rel_path: str | None = None, uuid: str | None = None) -> dict:
    """Copy an audio file (mp3/wav/ogg) into assets/resources/ + write meta.

    Places the file under assets/resources/ so it can be loaded at runtime
    via ``resources.load()``. Returns {path, rel_path, uuid}.
    """
    p = Path(project_path).expanduser().resolve()
    src = Path(src_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"source audio not found: {src}")

    if rel_path:
        rel = rel_path.lstrip("/")
        if not rel.startswith("assets/"):
            rel = f"assets/resources/{rel}"
    else:
        rel = f"assets/resources/{src.name}"

    target = p / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)

    audio_uuid = uuid or new_uuid()
    suffix = target.suffix.lower()  # e.g. ".mp3"
    meta = {
        "ver": "2.0.3",
        "importer": "audio-clip",
        "imported": True,
        "uuid": audio_uuid,
        "files": [".json", suffix],
        "subMetas": {},
        "userData": {
            "audioLoadMode": 0,
        },
    }
    write_meta(target, meta)

    return {
        "path": str(target),
        "rel_path": rel,
        "uuid": audio_uuid,
    }


def add_resource_file(project_path: str | Path, src_path: str | Path,
                      rel_path: str | None = None, uuid: str | None = None) -> dict:
    """Copy any file into assets/resources/ + write a minimal meta.

    Suitable for JSON data files, text assets, or other resources that
    need to be loadable at runtime via ``resources.load()``.
    Returns {path, rel_path, uuid}.
    """
    p = Path(project_path).expanduser().resolve()
    src = Path(src_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"source file not found: {src}")

    if rel_path:
        rel = rel_path.lstrip("/")
        if not rel.startswith("assets/"):
            rel = f"assets/resources/{rel}"
    else:
        rel = f"assets/resources/{src.name}"

    target = p / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)

    res_uuid = uuid or new_uuid()
    meta = {
        "ver": "1.0.0",
        "importer": "default",
        "imported": True,
        "uuid": res_uuid,
        "files": [],
        "subMetas": {},
        "userData": {},
    }
    write_meta(target, meta)

    return {
        "path": str(target),
        "rel_path": rel,
        "uuid": res_uuid,
    }


# ----------- AnimationClip -----------

def create_animation_clip(project_path: str | Path, clip_name: str,
                          duration: float = 1.0,
                          sample: int = 60,
                          tracks: list[dict] | None = None,
                          rel_dir: str | None = None,
                          uuid: str | None = None) -> dict:
    """Create a .anim AnimationClip file + meta.

    Args:
        clip_name: Name of the clip (e.g. "idle", "walk")
        duration: Clip duration in seconds
        sample: Frames per second
        tracks: List of track dicts. Each track:
            {
                "path": "NodeName",          # target node path (relative)
                "property": "position",       # "position" | "scale" | "rotation" | "color" | "opacity" | "active"
                "keyframes": [
                    {"time": 0.0, "value": [0, 0, 0]},
                    {"time": 0.5, "value": [100, 0, 0]},
                    {"time": 1.0, "value": [0, 0, 0]},
                ]
            }
            Values: position=[x,y,z], scale=[sx,sy,sz], rotation=[ez] (euler z degrees),
                    color=[r,g,b,a], opacity=0-255 (number), active=true/false

    Returns {path, rel_path, uuid}.
    """
    p = Path(project_path).expanduser().resolve()
    if rel_dir:
        base = rel_dir.lstrip("/")
        if not base.startswith("assets/"):
            base = f"assets/{base}"
    else:
        base = "assets/animations"

    dst_dir = p / base
    dst_dir.mkdir(parents=True, exist_ok=True)
    clip_path = dst_dir / f"{clip_name}.anim"

    clip_uuid = uuid or new_uuid()

    # Build Cocos Creator 3.x AnimationClip JSON
    # Cocos 3.x .anim is a JSON with specific structure
    anim_data = _build_anim_json(clip_name, duration, sample, tracks or [])

    with open(clip_path, "w") as f:
        json.dump(anim_data, f, indent=2)

    # Write meta
    meta = {
        "ver": "1.0.0",
        "importer": "animation-clip",
        "imported": True,
        "uuid": clip_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    }
    write_meta(clip_path, meta)

    return {
        "path": str(clip_path),
        "rel_path": str(clip_path.relative_to(p)),
        "uuid": clip_uuid,
    }


def _build_anim_json(name: str, duration: float, sample: int, tracks: list[dict]) -> list:
    """Build a Cocos Creator 3.x AnimationClip serialized JSON.

    The .anim file is a JSON array (same format as .scene/.prefab).
    """
    objects = []

    def push(obj):
        idx = len(objects)
        objects.append(obj)
        return idx

    # [0] cc.AnimationClip
    clip_idx = push({
        "__type__": "cc.AnimationClip",
        "_name": name,
        "_objFlags": 0,
        "_native": "",
        "sample": sample,
        "speed": 1,
        "wrapMode": 2,  # 2=Loop, 1=Normal, 0=Default
        "enableTrsBlending": False,
        "_duration": duration,
        "_hash": hash(name) & 0xFFFFFFFF,
        "_tracks": [],
        "_exoticAnimation": None,
        "_events": [],
    })

    # Build tracks
    track_refs = []
    for track in tracks:
        prop = track.get("property", "position")
        path = track.get("path", "")
        keyframes = track.get("keyframes", [])

        if prop == "position":
            t_idx = _build_vec3_track(objects, push, path, keyframes, "cc.animation.VectorTrack", 3)
        elif prop == "scale":
            t_idx = _build_vec3_track(objects, push, path, keyframes, "cc.animation.VectorTrack", 3)
        elif prop == "rotation":
            # Euler Z only for 2D
            t_idx = _build_float_track(objects, push, path, keyframes, "cc.animation.RealTrack")
        elif prop in ("opacity", "active"):
            t_idx = _build_float_track(objects, push, path, keyframes, "cc.animation.RealTrack")
        elif prop == "color":
            t_idx = _build_color_track(objects, push, path, keyframes)
        else:
            continue
        track_refs.append({"__id__": t_idx})

    objects[clip_idx]["_tracks"] = track_refs
    return objects


def _build_vec3_track(objects, push, path, keyframes, track_type, channels):
    """Build a VectorTrack with 2-3 channel curves."""
    # Simplified: store as a generic track with keyframe data
    # Cocos 3.x track format is complex; we use a simplified version
    # that the engine can still parse
    times = [kf["time"] for kf in keyframes]
    values = [kf["value"] for kf in keyframes]

    channels_data = []
    for ch in range(min(channels, 3)):
        curve_idx = push({
            "__type__": "cc.animation.RealCurve",
            "_times": times,
            "_values": [{"__type__": "cc.animation.RealKeyframeValue",
                         "interpolationMode": 2,  # LINEAR
                         "value": v[ch] if isinstance(v, (list, tuple)) and ch < len(v) else 0
                         } for v in values],
            "preExtrapolation": 1,
            "postExtrapolation": 1,
        })
        channels_data.append({"__id__": curve_idx})

    track_idx = push({
        "__type__": track_type,
        "_binding": {
            "__type__": "cc.animation.TrackBinding",
            "path": {
                "__type__": "cc.animation.TrackPath",
                "_paths": [
                    {"__type__": "cc.animation.HierarchyPath", "path": path},
                    {"__type__": "cc.animation.ComponentPath", "component": ""},
                    path.split("/")[-1] if "/" in path else "",
                ],
            },
        },
        "_channels": channels_data,
        "_nComponents": channels,
    })
    return track_idx


def _build_float_track(objects, push, path, keyframes, track_type):
    """Build a single-channel RealTrack."""
    times = [kf["time"] for kf in keyframes]
    values = [kf["value"] for kf in keyframes]

    curve_idx = push({
        "__type__": "cc.animation.RealCurve",
        "_times": times,
        "_values": [{"__type__": "cc.animation.RealKeyframeValue",
                     "interpolationMode": 2,
                     "value": v if isinstance(v, (int, float)) else (v[0] if isinstance(v, list) else 0)
                     } for v in values],
        "preExtrapolation": 1,
        "postExtrapolation": 1,
    })

    track_idx = push({
        "__type__": track_type,
        "_binding": {
            "__type__": "cc.animation.TrackBinding",
            "path": {
                "__type__": "cc.animation.TrackPath",
                "_paths": [
                    {"__type__": "cc.animation.HierarchyPath", "path": path},
                ],
            },
        },
        "_channel": {"__id__": curve_idx},
    })
    return track_idx


def _build_color_track(objects, push, path, keyframes):
    """Build a ColorTrack with 4 channel curves (r,g,b,a)."""
    times = [kf["time"] for kf in keyframes]
    values = [kf["value"] for kf in keyframes]

    channels_data = []
    for ch in range(4):
        curve_idx = push({
            "__type__": "cc.animation.RealCurve",
            "_times": times,
            "_values": [{"__type__": "cc.animation.RealKeyframeValue",
                         "interpolationMode": 2,
                         "value": v[ch] if isinstance(v, (list, tuple)) and ch < len(v) else 255
                         } for v in values],
            "preExtrapolation": 1,
            "postExtrapolation": 1,
        })
        channels_data.append({"__id__": curve_idx})

    track_idx = push({
        "__type__": "cc.animation.ColorTrack",
        "_binding": {
            "__type__": "cc.animation.TrackBinding",
            "path": {
                "__type__": "cc.animation.TrackPath",
                "_paths": [
                    {"__type__": "cc.animation.HierarchyPath", "path": path},
                ],
            },
        },
        "_channels": channels_data,
    })
    return track_idx


# ----------- Spine assets -----------

def add_spine_data(project_path: str | Path, spine_json_path: str | Path,
                   atlas_path: str | Path, texture_paths: list[str | Path] | None = None,
                   rel_dir: str | None = None, uuid: str | None = None) -> dict:
    """Import a Spine skeleton into the project.

    Copies the .json (skeleton data), .atlas, and texture PNG(s) into
    assets/. Writes meta files for each. Returns UUIDs needed for
    `add_spine()`.

    Args:
        spine_json_path: Path to the Spine .json skeleton data file
        atlas_path: Path to the .atlas file
        texture_paths: List of texture PNG paths (if None, looks for .png
                       next to the atlas file)
        rel_dir: Target directory relative to assets/ (default: "spine/<name>/")
    """
    p = Path(project_path).expanduser().resolve()
    spine_json = Path(spine_json_path).expanduser().resolve()
    atlas = Path(atlas_path).expanduser().resolve()

    if not spine_json.exists():
        raise FileNotFoundError(f"Spine JSON not found: {spine_json}")
    if not atlas.exists():
        raise FileNotFoundError(f"Atlas not found: {atlas}")

    name = spine_json.stem
    if rel_dir:
        base = rel_dir.lstrip("/")
        if not base.startswith("assets/"):
            base = f"assets/{base}"
    else:
        base = f"assets/spine/{name}"

    dst_dir = p / base
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Copy spine JSON
    spine_uuid = uuid or new_uuid()
    dst_json = dst_dir / spine_json.name
    shutil.copy2(spine_json, dst_json)
    write_meta(dst_json, {
        "ver": "1.2.3",
        "importer": "spine-data",
        "imported": True,
        "uuid": spine_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    })

    # Copy atlas
    atlas_uuid = new_uuid()
    dst_atlas = dst_dir / atlas.name
    shutil.copy2(atlas, dst_atlas)
    write_meta(dst_atlas, {
        "ver": "1.0.5",
        "importer": "spine-atlas",
        "imported": True,
        "uuid": atlas_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    })

    # Copy textures
    tex_uuids = []
    if texture_paths is None:
        texture_paths = list(atlas.parent.glob("*.png"))
    for tex in texture_paths:
        tex = Path(tex).expanduser().resolve()
        if not tex.exists():
            continue
        tex_uuid = new_uuid()
        dst_tex = dst_dir / tex.name
        shutil.copy2(tex, dst_tex)
        from .meta_util import new_sprite_frame_meta
        meta = new_sprite_frame_meta(dst_tex, uuid=tex_uuid)
        write_meta(dst_tex, meta)
        tex_uuids.append({"path": str(dst_tex), "uuid": tex_uuid})

    return {
        "skeleton_data_uuid": spine_uuid,
        "atlas_uuid": atlas_uuid,
        "textures": tex_uuids,
        "dir": str(dst_dir),
    }


# ----------- DragonBones assets -----------

def add_dragonbones_data(project_path: str | Path, db_json_path: str | Path,
                         atlas_json_path: str | Path, texture_paths: list[str | Path] | None = None,
                         rel_dir: str | None = None, uuid: str | None = None) -> dict:
    """Import DragonBones skeleton data into the project.

    Copies the _ske.json, _tex.json, and _tex.png files.
    Returns UUIDs for `add_dragonbones()`.
    """
    p = Path(project_path).expanduser().resolve()
    db_json = Path(db_json_path).expanduser().resolve()
    atlas_json = Path(atlas_json_path).expanduser().resolve()

    name = db_json.stem.replace("_ske", "")
    if rel_dir:
        base = rel_dir.lstrip("/")
        if not base.startswith("assets/"):
            base = f"assets/{base}"
    else:
        base = f"assets/dragonbones/{name}"

    dst_dir = p / base
    dst_dir.mkdir(parents=True, exist_ok=True)

    # DragonBones skeleton JSON
    db_uuid = uuid or new_uuid()
    dst_db = dst_dir / db_json.name
    shutil.copy2(db_json, dst_db)
    write_meta(dst_db, {
        "ver": "1.0.2",
        "importer": "dragonbones",
        "imported": True,
        "uuid": db_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    })

    # Atlas JSON
    atlas_uuid = new_uuid()
    dst_atlas = dst_dir / atlas_json.name
    shutil.copy2(atlas_json, dst_atlas)
    write_meta(dst_atlas, {
        "ver": "1.0.1",
        "importer": "dragonbones-atlas",
        "imported": True,
        "uuid": atlas_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    })

    # Textures
    tex_uuids = []
    if texture_paths is None:
        texture_paths = list(atlas_json.parent.glob("*_tex.png"))
    for tex in texture_paths:
        tex = Path(tex).expanduser().resolve()
        if not tex.exists():
            continue
        tex_uuid = new_uuid()
        dst_tex = dst_dir / tex.name
        shutil.copy2(tex, dst_tex)
        from .meta_util import new_sprite_frame_meta
        meta = new_sprite_frame_meta(dst_tex, uuid=tex_uuid)
        write_meta(dst_tex, meta)
        tex_uuids.append({"path": str(dst_tex), "uuid": tex_uuid})

    return {
        "dragon_asset_uuid": db_uuid,
        "dragon_atlas_uuid": atlas_uuid,
        "textures": tex_uuids,
        "dir": str(dst_dir),
    }


# ----------- TiledMap assets -----------

def add_tiled_map_asset(project_path: str | Path, tmx_path: str | Path,
                        tsx_paths: list[str | Path] | None = None,
                        texture_paths: list[str | Path] | None = None,
                        rel_dir: str | None = None, uuid: str | None = None) -> dict:
    """Import a TiledMap (.tmx) and its tilesets into the project.

    Copies the .tmx, any .tsx files, and tileset PNG textures.
    Returns the TMX asset UUID for `add_tiled_map()`.

    Args:
        tmx_path: Path to the .tmx map file
        tsx_paths: List of .tsx tileset files (if None, auto-detects from tmx dir)
        texture_paths: List of tileset PNG textures (if None, auto-detects)
        rel_dir: Target dir relative to assets/ (default: "tiledmap/<name>/")
    """
    p = Path(project_path).expanduser().resolve()
    tmx = Path(tmx_path).expanduser().resolve()
    if not tmx.exists():
        raise FileNotFoundError(f"TMX not found: {tmx}")

    name = tmx.stem
    if rel_dir:
        base = rel_dir.lstrip("/")
        if not base.startswith("assets/"):
            base = f"assets/{base}"
    else:
        base = f"assets/tiledmap/{name}"

    dst_dir = p / base
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Copy TMX
    tmx_uuid = uuid or new_uuid()
    dst_tmx = dst_dir / tmx.name
    shutil.copy2(tmx, dst_tmx)
    write_meta(dst_tmx, {
        "ver": "1.0.4",
        "importer": "tiled-map",
        "imported": True,
        "uuid": tmx_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    })

    # Copy TSX files
    tsx_uuids = []
    if tsx_paths is None:
        tsx_paths = list(tmx.parent.glob("*.tsx"))
    for tsx in tsx_paths:
        tsx = Path(tsx).expanduser().resolve()
        if not tsx.exists():
            continue
        tsx_uuid = new_uuid()
        dst_tsx = dst_dir / tsx.name
        shutil.copy2(tsx, dst_tsx)
        write_meta(dst_tsx, {
            "ver": "1.0.0",
            "importer": "default",
            "imported": True,
            "uuid": tsx_uuid,
            "files": [],
            "subMetas": {},
            "userData": {},
        })
        tsx_uuids.append({"path": str(dst_tsx), "uuid": tsx_uuid})

    # Copy tileset textures
    tex_uuids = []
    if texture_paths is None:
        texture_paths = list(tmx.parent.glob("*.png"))
    for tex in texture_paths:
        tex = Path(tex).expanduser().resolve()
        if not tex.exists():
            continue
        tex_uuid = new_uuid()
        dst_tex = dst_dir / tex.name
        shutil.copy2(tex, dst_tex)
        from .meta_util import new_sprite_frame_meta
        meta = new_sprite_frame_meta(dst_tex, uuid=tex_uuid)
        write_meta(dst_tex, meta)
        tex_uuids.append({"path": str(dst_tex), "uuid": tex_uuid})

    return {
        "tmx_uuid": tmx_uuid,
        "tsx_files": tsx_uuids,
        "textures": tex_uuids,
        "dir": str(dst_dir),
    }


# ----------- SpriteAtlas -----------

def create_sprite_atlas(project_path: str | Path, atlas_name: str,
                        png_paths: list[str | Path],
                        rel_dir: str | None = None,
                        uuid: str | None = None,
                        max_width: int = 2048, max_height: int = 2048) -> dict:
    """Create a SpriteAtlas (.plist-style) by collecting multiple PNGs.

    Cocos Creator 3.x uses AutoAtlas (.pac file) rather than traditional
    .plist atlases. This creates an AutoAtlas config that bundles the
    specified PNGs into a single texture at build time.

    Steps:
      1. Copy all PNGs into a dedicated folder (assets/atlas/<atlas_name>/)
      2. Write sprite-frame meta for each PNG
      3. Create an AutoAtlas config (.pac) in the same folder

    Returns {dir, atlas_uuid, images: [{path, uuid, sprite_frame_uuid}]}
    """
    p = Path(project_path).expanduser().resolve()
    if rel_dir:
        base = rel_dir.lstrip("/")
        if not base.startswith("assets/"):
            base = f"assets/{base}"
    else:
        base = f"assets/atlas/{atlas_name}"

    dst_dir = p / base
    dst_dir.mkdir(parents=True, exist_ok=True)

    atlas_uuid = uuid or new_uuid()
    images = []

    # Copy each PNG + write sprite-frame meta
    for png in png_paths:
        src = Path(png).expanduser().resolve()
        if not src.exists():
            continue
        dst = dst_dir / src.name
        shutil.copy2(src, dst)
        from .meta_util import new_sprite_frame_meta
        img_uuid = new_uuid()
        meta = new_sprite_frame_meta(dst, uuid=img_uuid)
        write_meta(dst, meta)
        images.append({
            "path": str(dst),
            "uuid": img_uuid,
            "sprite_frame_uuid": f"{img_uuid}@f9941",
        })

    # Create AutoAtlas .pac file
    pac_path = dst_dir / f"{atlas_name}.pac"
    pac_data = {
        "__type__": "cc.SpriteAtlas",
        "_name": atlas_name,
        "maxWidth": max_width,
        "maxHeight": max_height,
        "padding": 2,
        "allowRotation": True,
        "forceSquared": False,
        "powerOfTwo": True,
        "algorithm": "MaxRect",
        "format": "png",
        "quality": 80,
        "contourBleed": True,
        "paddingBleed": True,
        "filterUnused": False,
    }
    with open(pac_path, "w") as f:
        json.dump(pac_data, f, indent=2)

    # Write .pac meta
    write_meta(pac_path, {
        "ver": "1.0.7",
        "importer": "auto-atlas",
        "imported": True,
        "uuid": atlas_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    })

    return {
        "dir": str(dst_dir),
        "atlas_uuid": atlas_uuid,
        "pac_path": str(pac_path),
        "images": images,
    }


# ----------- gen-asset bridge -----------

def generate_and_import_image(
    project_path: str | Path,
    prompt: str,
    name: str,
    style: str = "icon",
    width: int = 1024,
    height: int = 1024,
    provider: str = "zhipu",
    transparent: bool = True,
    as_resource: bool = False,
) -> dict:
    """Generate a game asset via AI, make it transparent, and import into project.

    Requires gen-asset skill installed at ~/.claude/skills/gen-asset/.
    Uses 智谱 CogView-3-Flash (free) by default, or Pollinations Flux.

    Args:
        prompt: Image description (English recommended for better quality)
        name: Output filename (without extension)
        style: icon/pixel/character/tile/ui/portrait/item/scene/none
        transparent: Whether to remove white background (skip for scene/tile)
        as_resource: Put in assets/resources/ for runtime loading

    Returns {path, uuid, sprite_frame_uuid, generated_png, transparent_png}
    """
    import subprocess, glob

    gen_asset_dir = Path.home() / ".claude/skills/gen-asset"
    gen_py = gen_asset_dir / "gen.py"
    make_trans_py = gen_asset_dir / "make_transparent.py"

    if not gen_py.exists():
        raise FileNotFoundError(
            f"gen-asset skill not found at {gen_asset_dir}. "
            "Install it first: see ~/.claude/skills/gen-asset/"
        )

    p = Path(project_path).expanduser().resolve()
    tmp_dir = Path("/tmp/cocos-mcp-gen")
    tmp_dir.mkdir(exist_ok=True)

    # 1. Generate image
    cmd = [
        sys.executable, str(gen_py), prompt,
        "--style", style,
        "--width", str(width),
        "--height", str(height),
        "--provider", provider,
        "--out", str(tmp_dir),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"gen.py failed: {result.stderr[-500:]}")

    # Find the generated PNG (newest file in tmp_dir)
    pngs = sorted(tmp_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not pngs:
        raise RuntimeError("gen.py produced no PNG output")
    generated_png = pngs[0]

    # 2. Make transparent (if requested and not scene/tile)
    transparent_png = generated_png
    if transparent and style not in ("scene", "tile"):
        result2 = subprocess.run(
            [sys.executable, str(make_trans_py), str(generated_png)],
            capture_output=True, text=True, timeout=60,
        )
        # Output is <name>-transparent.png
        trans_path = generated_png.with_name(
            generated_png.stem + "-transparent.png"
        )
        if trans_path.exists():
            transparent_png = trans_path

    # 3. Import into project
    final_name = f"{name}.png"
    import_result = add_image(
        str(p), str(transparent_png),
        rel_path=final_name,
        as_resource=as_resource,
    )

    return {
        **import_result,
        "generated_png": str(generated_png),
        "transparent_png": str(transparent_png),
    }

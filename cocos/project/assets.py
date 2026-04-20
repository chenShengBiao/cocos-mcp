"""Project-level asset IO: script/image/audio/generic-resource import + listing.

These functions are the stateless building blocks that the MCP tools
(``cocos_add_script``, ``cocos_add_image``, ``cocos_list_assets``, ...)
sit on top of. None of them invoke the Cocos Creator CLI — they just
maintain the on-disk ``assets/`` + ``.meta`` sidecar layout that Creator
expects. A project becomes "importable" into Creator purely by having
the right files laid out with the right meta shapes.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ..meta_util import new_sprite_frame_meta, script_ts_meta, write_meta
from ..uuid_util import new_uuid


def get_project_info(project_path: str | Path) -> dict:
    """Read package.json and a few other diagnostic facts."""
    p = Path(project_path).expanduser().resolve()
    # Heterogeneous values (str / bool / list / None) — typed as Any so mypy
    # doesn't infer dict[str, str] from the first key and reject the rest.
    info: dict[str, Any] = {"project_path": str(p)}
    pkg_path = p / "package.json"
    if pkg_path.exists():
        with open(pkg_path) as f:
            info["package"] = json.load(f)
    info["assets_exists"] = (p / "assets").exists()
    info["library_built"] = (p / "library").exists()
    info["build_dir"] = str(p / "build") if (p / "build").exists() else None

    # Single walk of assets/, dispatching by suffix — avoids three separate
    # rglob scans of the same tree (noticeable on projects with many files).
    scenes: list[str] = []
    scripts: list[str] = []
    images: list[str] = []
    assets_dir = p / "assets"
    if assets_dir.exists():
        for f in assets_dir.rglob("*"):
            if not f.is_file():
                continue
            suffix = f.suffix.lower()
            if suffix == ".scene":
                scenes.append(str(f.relative_to(p)))
            elif suffix == ".ts":
                scripts.append(str(f.relative_to(p)))
            elif suffix == ".png":
                images.append(str(f.relative_to(p)))
    info["scenes"] = scenes
    info["scripts"] = scripts
    info["images"] = images
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
    assets: dict[str, list[dict]] = {"scripts": [], "scenes": [], "images": [], "prefabs": []}
    assets_dir = p / "assets"
    if not assets_dir.exists():
        return assets

    def _read_meta(meta_path: Path) -> dict | None:
        # Narrow exception list: only swallow file/JSON corruption, not
        # programming bugs (KeyError on a typo, TypeError, etc.) which
        # should still surface during development.
        try:
            with open(meta_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    # Single walk of assets/; dispatch by suffix. Previously this made four
    # separate rglob scans of the same tree.
    for f in assets_dir.rglob("*"):
        if not f.is_file():
            continue
        suffix = f.suffix.lower()
        if suffix == ".ts":
            meta_path = f.with_suffix(".ts.meta")
            if meta_path.exists():
                meta = _read_meta(meta_path)
                assets["scripts"].append({
                    "rel": str(f.relative_to(p)),
                    "uuid": meta.get("uuid") if meta else None,
                })
        elif suffix == ".scene":
            meta_path = Path(f"{f}.meta")
            if meta_path.exists():
                meta = _read_meta(meta_path)
                assets["scenes"].append({
                    "rel": str(f.relative_to(p)),
                    "uuid": meta.get("uuid") if meta else None,
                })
        elif suffix == ".png":
            meta_path = Path(f"{f}.meta")
            if meta_path.exists():
                m = _read_meta(meta_path) or {}
                uuid = m.get("uuid")
                sub = m.get("subMetas", {})
                assets["images"].append({
                    "rel": str(f.relative_to(p)),
                    "main_uuid": uuid,
                    "type": m.get("userData", {}).get("type", "texture"),
                    "sprite_frame_uuid": f"{uuid}@f9941" if "f9941" in sub else None,
                })
        elif suffix == ".prefab":
            meta_path = Path(f"{f}.meta")
            if meta_path.exists():
                meta = _read_meta(meta_path)
                assets["prefabs"].append({
                    "rel": str(f.relative_to(p)),
                    "uuid": meta.get("uuid") if meta else None,
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

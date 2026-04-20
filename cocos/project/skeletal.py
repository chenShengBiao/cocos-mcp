"""Skeletal animation asset import — Spine and DragonBones.

Both share the same shape: one data JSON + one atlas (JSON or .atlas) +
one or more texture PNGs. The pair of importers here just wires the
right meta sidecars so Creator recognizes the assets.
"""
from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from ..meta_util import new_sprite_frame_meta, write_meta
from ..uuid_util import new_uuid


def add_spine_data(project_path: str | Path, spine_json_path: str | Path,
                   atlas_path: str | Path,
                   texture_paths: Sequence[str | Path] | None = None,
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
        meta = new_sprite_frame_meta(dst_tex, uuid=tex_uuid)
        write_meta(dst_tex, meta)
        tex_uuids.append({"path": str(dst_tex), "uuid": tex_uuid})

    return {
        "skeleton_data_uuid": spine_uuid,
        "atlas_uuid": atlas_uuid,
        "textures": tex_uuids,
        "dir": str(dst_dir),
    }


def add_dragonbones_data(project_path: str | Path, db_json_path: str | Path,
                         atlas_json_path: str | Path,
                         texture_paths: Sequence[str | Path] | None = None,
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
        meta = new_sprite_frame_meta(dst_tex, uuid=tex_uuid)
        write_meta(dst_tex, meta)
        tex_uuids.append({"path": str(dst_tex), "uuid": tex_uuid})

    return {
        "dragon_asset_uuid": db_uuid,
        "dragon_atlas_uuid": atlas_uuid,
        "textures": tex_uuids,
        "dir": str(dst_dir),
    }

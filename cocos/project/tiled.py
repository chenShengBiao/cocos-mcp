"""TiledMap (.tmx) asset import."""
from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from ..meta_util import new_sprite_frame_meta, write_meta
from ..uuid_util import new_uuid


def add_tiled_map_asset(project_path: str | Path, tmx_path: str | Path,
                        tsx_paths: Sequence[str | Path] | None = None,
                        texture_paths: Sequence[str | Path] | None = None,
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
        meta = new_sprite_frame_meta(dst_tex, uuid=tex_uuid)
        write_meta(dst_tex, meta)
        tex_uuids.append({"path": str(dst_tex), "uuid": tex_uuid})

    return {
        "tmx_uuid": tmx_uuid,
        "tsx_files": tsx_uuids,
        "textures": tex_uuids,
        "dir": str(dst_dir),
    }

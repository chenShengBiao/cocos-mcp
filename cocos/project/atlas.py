"""SpriteAtlas (AutoAtlas .pac) creation for packing multiple PNGs at build time."""
from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path

from ..meta_util import new_sprite_frame_meta, write_meta
from ..uuid_util import new_uuid


def create_sprite_atlas(project_path: str | Path, atlas_name: str,
                        png_paths: Sequence[str | Path],
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

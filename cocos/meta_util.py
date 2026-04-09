"""Meta file helpers for Cocos Creator assets.

Cocos Creator pairs every asset with a sibling `<file>.meta` JSON file
that pins a stable UUID and (for images) declares sub-resources like
texture / sprite-frame.

Two key facts learned the hard way:

  * The CLI auto-generates `texture` type meta when it imports a fresh PNG
    via `--build`. To use it from a `cc.Sprite`, you must add the
    `f9941` (sprite-frame) sub-resource and update `userData.type`.
  * Sub-resource ids `6c48a` (texture) and `f9941` (sprite-frame) are
    constants — Cocos Creator uses the same magic strings everywhere.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from .uuid_util import new_uuid

TEXTURE_SUB_ID = "6c48a"
SPRITE_FRAME_SUB_ID = "f9941"


# ----------- generic helpers -----------

def read_meta(asset_path: str | Path) -> dict | None:
    p = Path(f"{asset_path}.meta")
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def write_meta(asset_path: str | Path, meta: dict) -> None:
    p = Path(f"{asset_path}.meta")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(meta, f, indent=2)


# ----------- script meta -----------

def script_ts_meta(uuid: str | None = None) -> dict:
    return {
        "ver": "4.0.24",
        "importer": "typescript",
        "imported": True,
        "uuid": uuid or new_uuid(),
        "files": [],
        "subMetas": {},
        "userData": {},
    }


# ----------- scene meta -----------

def scene_meta(uuid: str | None = None) -> dict:
    return {
        "ver": "1.1.50",
        "importer": "scene",
        "imported": True,
        "uuid": uuid or new_uuid(),
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    }


# ----------- prefab meta -----------

def prefab_meta(uuid: str | None = None, sync_node_name: str = "") -> dict:
    return {
        "ver": "1.1.50",
        "importer": "prefab",
        "imported": True,
        "uuid": uuid or new_uuid(),
        "files": [".json"],
        "subMetas": {},
        "userData": {"syncNodeName": sync_node_name} if sync_node_name else {},
    }


# ----------- image meta -----------

def _texture_sub(main_uuid: str, name: str) -> dict:
    return {
        "importer": "texture",
        "uuid": f"{main_uuid}@{TEXTURE_SUB_ID}",
        "displayName": name,
        "id": TEXTURE_SUB_ID,
        "name": "texture",
        "ver": "1.0.22",
        "imported": True,
        "files": [".json"],
        "subMetas": {},
        "userData": {
            "wrapModeS": "clamp-to-edge",
            "wrapModeT": "clamp-to-edge",
            "minfilter": "linear",
            "magfilter": "linear",
            "mipfilter": "none",
            "anisotropy": 0,
            "isUuid": True,
            "imageUuidOrDatabaseUri": main_uuid,
            "visible": False,
        },
    }


def _sprite_frame_sub(main_uuid: str, name: str, w: int, h: int) -> dict:
    return {
        "importer": "sprite-frame",
        "uuid": f"{main_uuid}@{SPRITE_FRAME_SUB_ID}",
        "displayName": name,
        "id": SPRITE_FRAME_SUB_ID,
        "name": "spriteFrame",
        "ver": "1.0.12",
        "imported": True,
        "files": [".json"],
        "subMetas": {},
        "userData": {
            "trimType": "none",
            "trimThreshold": 1,
            "rotated": False,
            "offsetX": 0,
            "offsetY": 0,
            "trimX": 0,
            "trimY": 0,
            "width": w,
            "height": h,
            "rawWidth": w,
            "rawHeight": h,
            "borderTop": 0,
            "borderBottom": 0,
            "borderLeft": 0,
            "borderRight": 0,
            "isUuid": True,
            "imageUuidOrDatabaseUri": f"{main_uuid}@{TEXTURE_SUB_ID}",
            "atlasUuid": "",
            "packable": True,
            "vertices": {
                "rawPosition": [-w / 2, -h / 2, 0, w / 2, -h / 2, 0, -w / 2, h / 2, 0, w / 2, h / 2, 0],
                "triangles": [],
                "uv": [0, h, w, h, 0, 0, w, 0],
                "nuv": [0, 1, 1, 1, 0, 0, 1, 0],
                "minPos": [-w / 2, -h / 2, 0],
                "maxPos": [w / 2, h / 2, 0],
                "indexes": [0, 1, 2, 2, 1, 3],
            },
            "pixelsToUnit": 100,
            "pivotX": 0.5,
            "pivotY": 0.5,
            "meshType": 0,
        },
    }


def new_sprite_frame_meta(png_path: str | Path, name: str | None = None, uuid: str | None = None) -> dict:
    """Create a complete sprite-frame meta for a PNG."""
    png_path = Path(png_path)
    img = Image.open(png_path)
    w, h = img.size
    main_uuid = uuid or new_uuid()
    display_name = name or png_path.stem
    return {
        "ver": "1.0.27",
        "importer": "image",
        "imported": True,
        "uuid": main_uuid,
        "files": [".json", ".png"],
        "subMetas": {
            TEXTURE_SUB_ID: _texture_sub(main_uuid, display_name),
            SPRITE_FRAME_SUB_ID: _sprite_frame_sub(main_uuid, display_name, w, h),
        },
        "userData": {
            "type": "sprite-frame",
            "hasAlpha": img.mode in ("RGBA", "LA"),
            "redirect": f"{main_uuid}@{SPRITE_FRAME_SUB_ID}",
            "fixAlphaTransparencyArtifacts": False,
        },
    }


def upgrade_texture_to_sprite_frame(meta_path: str | Path) -> dict:
    """Add sprite-frame sub-resource to a texture-only meta (idempotent).

    Cocos Creator's CLI build auto-generates `type: texture` metas with only
    a `6c48a` (texture) sub. To reference these from `cc.Sprite._spriteFrame`,
    you must add the `f9941` (sprite-frame) sub.
    """
    meta_path = Path(meta_path)
    with open(meta_path) as f:
        meta = json.load(f)

    if SPRITE_FRAME_SUB_ID in meta.get("subMetas", {}):
        return meta  # already upgraded

    if TEXTURE_SUB_ID not in meta.get("subMetas", {}):
        raise ValueError(f"meta has no texture sub-resource: {meta_path}")

    main_uuid = meta["uuid"]
    name = meta["subMetas"][TEXTURE_SUB_ID].get("displayName", meta_path.stem.replace(".png", ""))

    png_path = Path(str(meta_path).removesuffix(".meta"))
    if not png_path.exists():
        raise FileNotFoundError(f"PNG not found alongside meta: {png_path}")
    w, h = Image.open(png_path).size

    meta["subMetas"][SPRITE_FRAME_SUB_ID] = _sprite_frame_sub(main_uuid, name, w, h)
    meta["userData"]["type"] = "sprite-frame"
    meta["userData"]["redirect"] = f"{main_uuid}@{SPRITE_FRAME_SUB_ID}"

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def get_sprite_frame_uuid(meta_path: str | Path) -> str:
    """Return the @f9941 sub-resource UUID for a sprite-frame meta."""
    with open(meta_path) as f:
        meta = json.load(f)
    main = meta["uuid"]
    if SPRITE_FRAME_SUB_ID not in meta.get("subMetas", {}):
        raise ValueError(f"meta is not a sprite-frame: {meta_path}")
    return f"{main}@{SPRITE_FRAME_SUB_ID}"

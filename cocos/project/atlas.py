"""SpriteAtlas (AutoAtlas ``.pac``) + runtime DynamicAtlas helpers.

Cocos Creator 3.x has two distinct atlas mechanisms:

1. **AutoAtlas** — build-time packing. Drop a ``<name>.pac`` file into
   a folder plus the PNGs you want packed; ``cocos_build`` scans the
   folder and merges every sprite-frame PNG into a single texture + a
   ``cc.SpriteAtlas`` asset. The ``.pac`` file itself is a one-liner
   (``{"__type__": "cc.SpriteAtlas"}``) — **all packing config lives
   in the ``.pac.meta`` sidecar's ``userData``** (maxWidth, padding,
   algorithm, power-of-two, format/quality, filter-unused, etc.).
   Previous versions of this module wrote those config knobs into the
   ``.pac`` body, used an outdated meta ``"ver": "1.0.7"``, and left
   ``userData: {}``. Creator 3.8's importer silently rejects that
   shape — the scenes said "SpriteAtlas" but the build produced no
   packed texture. Fixed here against the 3.8 engine's
   ``editor/assets/default_file_content/auto-atlas`` defaults.

2. **DynamicAtlas** — runtime packing via
   ``cocos.internal.dynamicAtlasManager``. At run time, small sprite
   frames under ``maxFrameSize`` are opportunistically blitted into a
   shared atlas texture to reduce draw calls. This is a single flag
   (``enabled = true``), toggled from a script that runs once at boot.
   ``enable_dynamic_atlas`` writes that script + scaffolds registering
   it on a scene node — see the bottom of this file.
"""
from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path

from ..meta_util import new_sprite_frame_meta, script_ts_meta, write_meta
from ..uuid_util import new_uuid


# Default userData for .pac.meta. Mirrors the values Cocos Creator 3.8
# writes when you right-click → Create → AutoAtlas. Callers who want
# a square / power-of-two atlas or tighter padding override via kwargs.
_DEFAULT_AUTO_ATLAS_USER_DATA: dict = {
    "maxWidth": 1024,
    "maxHeight": 1024,
    "padding": 2,
    "allowRotation": True,
    "forceSquared": False,
    "powerOfTwo": False,
    "algorithm": "MaxRects",  # Cocos uses "MaxRects" (plural); "MaxRect" is ignored.
    "format": "png",
    "quality": 80,
    "contourBleed": True,
    "paddingBleed": True,
    "filterUnused": True,
    "removeTextureInBundle": True,
    "removeImageInBundle": True,
    "removeSpriteAtlasInBundle": True,
    "compressSettings": {},
    "textureSetting": {
        "wrapModeS": "repeat",
        "wrapModeT": "repeat",
        "minfilter": "linear",
        "magfilter": "linear",
        "mipfilter": "none",
        "anisotropy": 0,
    },
}


def create_sprite_atlas(project_path: str | Path, atlas_name: str,
                        png_paths: Sequence[str | Path] | None = None,
                        rel_dir: str | None = None,
                        uuid: str | None = None,
                        max_width: int = 1024, max_height: int = 1024,
                        padding: int = 2,
                        power_of_two: bool = False,
                        force_squared: bool = False,
                        filter_unused: bool = True,
                        algorithm: str = "MaxRects",
                        quality: int = 80) -> dict:
    """Create a Cocos 3.8 AutoAtlas bundle.

    Drops a ``<atlas_name>.pac`` marker into a folder (default
    ``assets/atlas/<atlas_name>/``) plus a correctly-shaped
    ``.pac.meta``. From that point on, **any sprite-frame PNG in the
    same folder** is automatically packed into a single atlas texture
    at ``cocos_build`` time — no need to re-enumerate them.

    ``png_paths`` is optional and only a convenience: if you hand over
    source PNGs they get copied into the atlas folder and sprite-frame
    metas written for each. For PNGs already in the project (e.g. added
    via ``cocos_add_image(rel_path="assets/atlas/pipes/foo.png")``) no
    copy is needed — they're picked up by the build automatically.

    **Atlas config** (maxWidth, padding, algorithm…) lives in the
    ``.pac.meta`` ``userData`` block; the ``.pac`` body is the single-
    line marker ``{"__type__": "cc.SpriteAtlas"}``. Tuning happens via
    kwargs, which override the 3.8 engine defaults. Default ``quality``
    (80) matches Creator's "lossy" PNG preset — set ``quality=100`` for
    lossless if you care (the atlas format stays PNG either way).

    Parameters:

    * ``atlas_name``        — display name + output filename stem.
    * ``png_paths``         — optional list of source PNGs to copy in.
    * ``rel_dir``           — folder relative to project root; defaults
                              to ``assets/atlas/<atlas_name>``.
    * ``uuid``              — override the atlas's UUID (fresh otherwise).
    * ``max_width`` /       — atlas texture size cap. 1024 is Cocos's
      ``max_height``          default; raise to 2048 if you have lots
                              of large frames.
    * ``padding``           — pixels between frames (bleed-safe).
    * ``power_of_two``      — force ^2 output size; required by some
                              legacy GPUs but usually wasteful.
    * ``force_squared``     — force 1:1 aspect. Usually leave off.
    * ``filter_unused``     — drop sprite frames that no scene/prefab
                              references. Saves APK size; default on.
    * ``algorithm``         — packing algorithm. Cocos 3.8 supports
                              ``"MaxRects"`` and ``"Basic"``.
    * ``quality``           — 0-100 encode quality.

    Returns::

        {
          "dir":          str,   # absolute atlas folder
          "atlas_uuid":   str,   # cc.SpriteAtlas UUID
          "pac_path":     str,   # absolute .pac marker path
          "images":       [{path, uuid, sprite_frame_uuid}, ...],
          "atlas_dir_rel": str,  # relative to project root — drop more PNGs here later
        }
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
    images: list[dict] = []

    # Copy each PNG + write sprite-frame meta (only for PNGs handed in;
    # any PNG already in the folder is picked up by the build anyway).
    if png_paths:
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

    # The .pac file is just a marker — Cocos 3.8 reads ALL packing
    # config from the sidecar .meta's userData, not from the .pac body.
    # Writing extra fields into the body doesn't break parsing but
    # doesn't take effect either; keep it minimal to match Creator's
    # own output.
    pac_path = dst_dir / f"{atlas_name}.pac"
    with open(pac_path, "w") as f:
        json.dump({"__type__": "cc.SpriteAtlas"}, f, indent=2)

    # Compose userData from the 3.8 defaults + caller overrides.
    user_data = dict(_DEFAULT_AUTO_ATLAS_USER_DATA)
    user_data.update({
        "maxWidth": max_width,
        "maxHeight": max_height,
        "padding": padding,
        "powerOfTwo": power_of_two,
        "forceSquared": force_squared,
        "filterUnused": filter_unused,
        "algorithm": algorithm,
        "quality": quality,
    })

    write_meta(pac_path, {
        "ver": "1.0.8",  # Cocos 3.8 editor version; 1.0.7 silently rejected
        "importer": "auto-atlas",
        "imported": True,
        "uuid": atlas_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": user_data,
    })

    return {
        "dir": str(dst_dir),
        "atlas_uuid": atlas_uuid,
        "pac_path": str(pac_path),
        "atlas_dir_rel": base,
        "images": images,
    }


# =======================================================================
# Dynamic atlas — runtime draw-call reduction
# =======================================================================
#
# DynamicAtlas is orthogonal to AutoAtlas: it's a single runtime flag
# (cocos.internal.dynamicAtlasManager.enabled = true) that tells the
# renderer to opportunistically batch small sprite frames into shared
# GPU textures as they're used. The flag defaults to false for new
# projects. enable_dynamic_atlas writes a tiny .ts script + hands back
# both UUIDs so the caller can attach it to a persistent GameManager
# node — same workflow as the scaffold tools.

_DYNAMIC_ATLAS_TEMPLATE = """// Auto-generated by cocos-mcp enable_dynamic_atlas.
// Enables the runtime dynamic atlas so small sprite frames are
// batched into shared textures at draw time. Attach this component
// to any persistent node loaded at scene start (e.g. a GameManager).
//
// Runtime API after attach::
//   DynamicAtlasBooter.I.refresh()     // re-build the atlas pool
//   DynamicAtlasBooter.I.disable()     // turn it off at runtime
//
// Notes
//   - The flag is global; one attach per game is enough.
//   - Frames larger than `maxFrameSize` px are NOT batched (default 512).
//   - Incompatible with some custom materials — toggle off if you see
//     sampling artifacts on meshes that use non-standard shaders.

import {{ _decorator, Component, dynamicAtlasManager }} from 'cc';
const {{ ccclass, property }} = _decorator;

@ccclass('{class_name}')
export class {class_name} extends Component {{
    public static I: {class_name} | null = null;

    @property({{ tooltip: 'Max per-frame size (px) eligible for batching.' }})
    maxFrameSize: number = {max_frame_size};

    onLoad() {{
        {class_name}.I = this;
        dynamicAtlasManager.enabled = true;
        dynamicAtlasManager.maxFrameSize = this.maxFrameSize;
    }}

    refresh() {{
        dynamicAtlasManager.reset();
    }}

    disable() {{
        dynamicAtlasManager.enabled = false;
    }}
}}
"""


def enable_dynamic_atlas(project_path: str | Path,
                        rel_path: str = "DynamicAtlasBooter.ts",
                        max_frame_size: int = 512,
                        class_name: str = "DynamicAtlasBooter",
                        uuid: str | None = None) -> dict:
    """Generate a boot script that flips ``dynamicAtlasManager.enabled``.

    Cocos 3.8 ships a runtime dynamic atlas — small sprite frames get
    batched into shared GPU textures automatically, cutting draw calls
    on heavy UI screens (menus, HUDs) typically by 3-10×. It's off by
    default. This helper writes a one-purpose component that sets the
    flag on ``onLoad`` and hands back both UUIDs so the caller can
    attach it to a persistent scene node in the next step::

        r = cocos_enable_dynamic_atlas(project)
        cocos_add_script(scene, game_manager_node, r["uuid_compressed"])

    Parameters:

    * ``rel_path``        — defaults to ``DynamicAtlasBooter.ts`` under
                            ``assets/scripts/``. Prefix-aware like
                            ``cocos_add_script``.
    * ``max_frame_size``  — engine threshold (px). Frames larger than
                            this are skipped. 512 matches the Cocos
                            default.
    * ``class_name``      — TypeScript class name. Exposed on a static
                            ``.I`` singleton after mount.
    * ``uuid``            — override the asset UUID (fresh otherwise).

    Returns ``{path, rel_path, uuid_standard, uuid_compressed}`` —
    same shape as the scaffold tools.
    """
    from ..uuid_util import compress_uuid
    from . import assets as assets_mod

    source = _DYNAMIC_ATLAS_TEMPLATE.format(
        class_name=class_name,
        max_frame_size=max_frame_size,
    )
    res = assets_mod.add_script(project_path, rel_path, source, uuid=uuid)
    return {
        "path": res["path"],
        "rel_path": res["rel_path"],
        "uuid_standard": res["uuid"],
        "uuid_compressed": compress_uuid(res["uuid"]),
    }

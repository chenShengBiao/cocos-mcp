"""Cocos Creator project management — install detection, asset import, build settings.

This was a single 1099-line module; split into submodules for maintainability:

* ``installs``     — Creator install detection + ``init_project`` + ``find_creator``
* ``assets``       — script / image / audio / resource file import + listing + project info
* ``animation``    — ``create_animation_clip`` + internal track builders
* ``skeletal``     — Spine + DragonBones data import
* ``tiled``        — TiledMap (.tmx) import
* ``atlas``        — SpriteAtlas (.pac) creation
* ``gen_image``    — AI-generated asset import wrapper

The public surface is re-exported here so ``from cocos import project as cp;
cp.list_assets(...)`` continues to work verbatim — and so tests that patch
``cp.list_creator_installs`` keep taking effect (see ``installs.py`` module
docstring for the late-binding trick that makes this work).
"""
from __future__ import annotations

from .animation import (
    create_animation_clip,
)
from .assets import (
    add_audio_file,
    add_image,
    add_resource_file,
    add_script,
    get_project_info,
    list_assets,
)
from .atlas import create_sprite_atlas
from .gen_image import generate_and_import_image
from .installs import (
    INSTALL_ROOTS,
    _list_creator_installs_cached,
    find_creator,
    init_project,
    invalidate_creator_installs_cache,
    list_creator_installs,
)
from .skeletal import (
    add_dragonbones_data,
    add_spine_data,
)
from .tiled import add_tiled_map_asset

__all__ = [
    "INSTALL_ROOTS",
    "add_audio_file",
    "add_dragonbones_data",
    "add_image",
    "add_resource_file",
    "add_script",
    "add_spine_data",
    "add_tiled_map_asset",
    "create_animation_clip",
    "create_sprite_atlas",
    "find_creator",
    "generate_and_import_image",
    "get_project_info",
    "init_project",
    "invalidate_creator_installs_cache",
    "list_assets",
    "list_creator_installs",
]

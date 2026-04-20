"""Cocos Creator project management — install detection, asset import, build settings.

This was a single 1099-line module; split into submodules for maintainability:

* ``installs``          — Creator install detection + ``init_project`` + ``find_creator``
* ``assets``            — script / image / audio / resource file import + listing + project info
* ``animation``         — ``create_animation_clip`` + internal track builders
* ``skeletal``          — Spine + DragonBones data import
* ``tiled``             — TiledMap (.tmx) import
* ``atlas``             — SpriteAtlas (.pac) creation
* ``gen_image``         — AI-generated asset import wrapper
* ``physics_material``  — ``cc.PhysicsMaterial`` (.pmat) asset creation

The public surface is re-exported here so ``from cocos import project as cp;
cp.list_assets(...)`` continues to work verbatim — and so tests that patch
``cp.list_creator_installs`` keep taking effect (see ``installs.py`` module
docstring for the late-binding trick that makes this work).
"""
from __future__ import annotations

from .animation import create_animation_clip
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
from .physics_material import create_physics_material
from .post_build_patches import (
    apply_patches as apply_post_build_patches,
    list_patches as list_post_build_patches,
    register_patches as register_post_build_patches,
    remove_patches as remove_post_build_patches,
)
from .skeletal import (
    add_dragonbones_data,
    add_spine_data,
)
from .tiled import add_tiled_map_asset
from .ui_tokens import (
    BUILTIN_THEMES,
    COLOR_NAMES,
    RADIUS_NAMES,
    SIZE_NAMES,
    SPACING_NAMES,
    derive_theme_from_seed,
    get_ui_tokens,
    hex_to_rgba,
    list_builtin_themes,
    resolve_color,
    resolve_radius,
    resolve_size,
    resolve_spacing,
    set_ui_theme,
)

__all__ = [
    "INSTALL_ROOTS",
    "add_audio_file",
    "add_dragonbones_data",
    "add_image",
    "add_resource_file",
    "add_script",
    "add_spine_data",
    "add_tiled_map_asset",
    "apply_post_build_patches",
    "create_animation_clip",
    "create_physics_material",
    "create_sprite_atlas",
    "find_creator",
    "generate_and_import_image",
    "get_project_info",
    "init_project",
    "invalidate_creator_installs_cache",
    "list_assets",
    "list_creator_installs",
    "list_post_build_patches",
    "register_post_build_patches",
    "remove_post_build_patches",
    # UI design tokens
    "BUILTIN_THEMES",
    "COLOR_NAMES",
    "SIZE_NAMES",
    "SPACING_NAMES",
    "RADIUS_NAMES",
    "set_ui_theme",
    "get_ui_tokens",
    "list_builtin_themes",
    "hex_to_rgba",
    "derive_theme_from_seed",
    "resolve_color",
    "resolve_size",
    "resolve_spacing",
    "resolve_radius",
]

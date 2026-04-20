"""UUID utilities, project init, asset import, and the constants reference table."""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import meta_util as mu
from cocos import project as cp
from cocos import uuid_util as uu

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- UUID utilities ----------------

    @mcp.tool()
    def cocos_new_uuid() -> str:
        """Generate a fresh standard UUID4 (36-char dashed lowercase hex).

        Used as the main UUID for new scripts, scenes, prefabs, and images.
        """
        return uu.new_uuid()

    @mcp.tool()
    def cocos_compress_uuid(uuid: str) -> str:
        """Compress a 36-char UUID to Cocos Creator's 23-char short form.

        Required when referencing a custom TS script class as a component
        `__type__` in a scene/prefab JSON. Example:
          '5372d6f5-721e-43f6-b004-d30da1c8a9a0' -> '5372db1ch5D9rAE0w2hyKmg'
        """
        return uu.compress_uuid(uuid)

    @mcp.tool()
    def cocos_decompress_uuid(short_uuid: str) -> str:
        """Reverse cocos_compress_uuid: 23-char short -> 36-char dashed."""
        return uu.decompress_uuid(short_uuid)

    # ---------------- Project: detect / init / inspect ----------------

    @mcp.tool()
    def cocos_list_creator_installs() -> list[dict]:
        """List every locally installed Cocos Creator version.

        Returns a list of {version, exe, template_dir} dicts. Looks under
        /Applications/Cocos/Creator on macOS, C:/CocosDashboard/Creator on
        Windows, /opt/Cocos/Creator on Linux.
        """
        return cp.list_creator_installs()

    @mcp.tool()
    def cocos_init_project(dst_path: str, creator_version: str | None = None,
                           template: str = "empty-2d", project_name: str | None = None) -> dict:
        """Initialize a new Cocos Creator project from a template.

        Copies a built-in template (default empty-2d) into `dst_path`,
        patches `package.json` with a fresh project UUID and the right
        creator version, and creates standard `assets/` subdirectories.

        Use `cocos_list_creator_installs` first to see available versions.
        """
        return cp.init_project(dst_path, creator_version, template, project_name)

    @mcp.tool()
    def cocos_get_project_info(project_path: str) -> dict:
        """Read package.json + list assets / scenes / scripts in the project."""
        return cp.get_project_info(project_path)

    @mcp.tool()
    def cocos_list_assets(project_path: str) -> dict:
        """List all assets in the project grouped by type, with their UUIDs.

        Returns {scripts: [...], scenes: [...], images: [...], prefabs: [...]}.
        Each entry has at minimum {rel, uuid}; images additionally include
        `sprite_frame_uuid` if the meta is upgraded.
        """
        return cp.list_assets(project_path)

    # ---------------- Asset management: scripts and images ----------------

    @mcp.tool()
    def cocos_add_script(project_path: str, rel_path: str, source: str) -> dict:
        """Write a TypeScript script + its meta into the project.

        `rel_path` can be either:
          - bare name like 'GameManager' -> writes assets/scripts/GameManager.ts
          - full path like 'assets/scripts/sub/Foo.ts'

        Returns {path, rel_path, uuid}. The uuid is the standard 36-char form;
        use cocos_compress_uuid to get the 23-char form needed in scene files.
        """
        return cp.add_script(project_path, rel_path, source)

    @mcp.tool()
    def cocos_add_image(project_path: str, src_png: str, rel_path: str | None = None,
                        as_resource: bool = False) -> dict:
        """Copy a PNG into the project and write a complete sprite-frame meta.

        Default: assets/textures/. Set as_resource=True to put it under
        assets/resources/ (needed for runtime loading via resources.load()).

        Returns {path, rel_path, main_uuid, sprite_frame_uuid, texture_uuid}.
        """
        return cp.add_image(project_path, src_png, rel_path, as_resource=as_resource)

    @mcp.tool()
    def cocos_upgrade_image_meta(meta_path: str) -> dict:
        """Upgrade a texture-only PNG meta to include a sprite-frame sub.

        Cocos Creator's CLI `--build` auto-generates `type: texture` metas
        when it imports a fresh PNG. To reference such a PNG from
        `cc.Sprite`, run this tool to add the `f9941` (sprite-frame) sub.
        Idempotent — does nothing if the sub already exists.

        Returns the updated meta dict.
        """
        return mu.upgrade_texture_to_sprite_frame(meta_path)

    @mcp.tool()
    def cocos_get_sprite_frame_uuid(meta_path: str) -> str:
        """Return the `<uuid>@f9941` sprite-frame sub-uuid for a PNG meta."""
        return mu.get_sprite_frame_uuid(meta_path)

    @mcp.tool()
    def cocos_set_sprite_frame_border(meta_path: str, top: int = 0, bottom: int = 0,
                                      left: int = 0, right: int = 0) -> dict:
        """Set 9-slice border on an existing sprite-frame meta in pixels.

        Required before using a PNG with cc.Sprite type=SLICED (rounded buttons,
        UI panels, dialog backgrounds — anything that should keep crisp corners
        while stretching the middle).

        Idempotent. The meta must already be sprite-frame type
        (run `cocos_upgrade_image_meta` first if it's still texture-only).
        """
        return mu.set_sprite_frame_border(meta_path, top, bottom, left, right)

    # ---------------- Constants reference table ----------------

    @mcp.tool()
    def cocos_constants() -> dict:
        """Return commonly used Cocos Creator constants.

        Saves you from looking up layer bitmasks, blend factors, alignment
        enum values, etc.
        """
        return {
            "layers": {
                "UI_2D": 33554432,    # bit 25
                "DEFAULT": 1073741824,  # bit 30 (used by Camera)
                "IGNORE_RAYCAST": 524288,  # bit 19
            },
            "blend_factors": {
                "ZERO": 0, "ONE": 1, "SRC_ALPHA": 2, "ONE_MINUS_SRC_ALPHA": 4,
                "DST_ALPHA": 8, "ONE_MINUS_DST_ALPHA": 16,
            },
            "label_align": {
                "LEFT": 0, "CENTER": 1, "RIGHT": 2,
                "TOP": 0, "MIDDLE": 1, "BOTTOM": 2,
            },
            "label_overflow": {
                "NONE": 0, "CLAMP": 1, "SHRINK": 2, "RESIZE_HEIGHT": 3,
            },
            "label_cache_mode": {
                "NONE": 0, "BITMAP": 1, "CHAR": 2,
            },
            "sprite_type": {
                "SIMPLE": 0, "SLICED": 1, "TILED": 2, "FILLED": 3,
            },
            "sprite_size_mode": {
                "CUSTOM": 0, "TRIMMED": 1, "RAW": 2,
            },
            "sprite_fill_type": {
                "HORIZONTAL": 0, "VERTICAL": 1, "RADIAL": 2,
            },
            "rigidbody2d_type": {
                "STATIC": 0, "KINEMATIC": 1, "DYNAMIC": 2,
            },
            "button_transition": {
                "NONE": 0, "COLOR": 1, "SCALE": 2, "SPRITE": 3,
            },
            "layout_type": {
                "NONE": 0, "HORIZONTAL": 1, "VERTICAL": 2, "GRID": 3,
            },
            "mask_type": {
                "RECT": 0, "ELLIPSE": 1, "GRAPHICS_STENCIL": 2, "SPRITE_STENCIL": 3,
            },
            "widget_align_mode": {
                "ONCE": 0, "ON_WINDOW_RESIZE": 1, "ALWAYS": 2,
            },
            "widget_align_flags": {
                "TOP": 1, "MIDDLE": 2, "BOTTOM": 4,
                "LEFT": 8, "CENTER": 16, "RIGHT": 32,
                "ALL": 45,  # TOP|BOTTOM|LEFT|RIGHT
            },
            "scene_globals_indices_in_empty_scene": {
                "comment": "These indices are stable in scenes created via cocos_create_scene",
                "scene_asset": 0,
                "scene": 1,
                "canvas": 2,
                "ui_camera_node": 3,
                "camera_component": 4,
                "canvas_uitransform": 5,
                "canvas_component": 6,
                "canvas_widget": 7,
                "scene_globals": 8,
                "ambient_info": 9,
                "skybox_info": 10,
                "shadows_info": 11,
                "prefab_info": 12,
            },
        }

    # ---------------- UI design tokens ----------------

    @mcp.tool()
    def cocos_set_ui_theme(project_path: str,
                           theme: str | None = None,
                           custom: dict | None = None) -> dict:
        """Pin a UI theme so every subsequent ``cocos_add_label`` /
        ``cocos_add_button`` / ``cocos_add_sprite`` call with
        ``color_preset=…`` / ``size_preset=…`` resolves through the
        same design tokens — produces a visually consistent game.

        Built-in theme names: ``dark_game``, ``light_minimal``,
        ``neon_arcade``, ``pastel_cozy``, ``corporate``. Pass a
        ``custom`` dict (``{color, font_size, spacing, radius}``) for
        something bespoke — missing preset names fall through to
        ``dark_game`` defaults so no lookup ever fails.

        Preset vocabulary every theme MUST provide:
          color: primary / secondary / bg / surface / text / text_dim /
                 success / warn / danger / border (10)
          font_size: title / heading / body / caption (4)
          spacing:   xs / sm / md / lg / xl (5)
          radius:    sm / md / lg / pill (4)

        Calling with no args pins ``dark_game``.
        """
        return cp.set_ui_theme(project_path, theme, custom)

    @mcp.tool()
    def cocos_get_ui_tokens(project_path: str) -> dict:
        """Return the project's active UI theme (fully resolved).

        Always returns a complete theme — un-themed projects get the
        ``dark_game`` default with ``source='fallback'``. Source is
        ``'registry'`` when the project has explicitly pinned a theme.
        """
        return cp.get_ui_tokens(project_path)

    @mcp.tool()
    def cocos_list_builtin_themes() -> dict:
        """Return all five bundled UI themes verbatim.

        Useful for previewing the palette before pinning one, or as a
        starting point for a ``custom=`` override passed to
        ``cocos_set_ui_theme``.
        """
        return cp.list_builtin_themes()

    @mcp.tool()
    def cocos_derive_theme_from_seed(seed_hex: str, mode: str = "dark") -> dict:
        """Generate a coherent UI palette from one brand color.

        Given ``seed_hex`` (the game's primary/brand color) and a ``mode``
        ("dark" or "light"), computes a full color set via HSL math:
          - secondary = complementary hue
          - bg / surface = seed hue at low saturation (subtle brand tint)
          - text / text_dim = high-contrast against bg
          - border = mid-lightness neutral
          - success/warn/danger stay at fixed green/amber/red (severity
            readability trumps brand consistency)

        Returns a ``{color: {...}}`` dict ready to pass through to
        ``cocos_set_ui_theme(project, custom=<this>)``. The caller may
        also merge in font_size / spacing / radius overrides before
        passing.

        Typical use::

            palette = cocos_derive_theme_from_seed("#6366f1", mode="dark")
            cocos_set_ui_theme("/game", custom=palette)
        """
        return cp.derive_theme_from_seed(seed_hex, mode)

    @mcp.tool()
    def cocos_hex_to_rgba(hex_color: str, alpha: int = 255) -> dict:
        """Convert ``#rrggbb`` / ``#rgb`` / ``#rrggbbaa`` to RGBA ints.

        Returns ``{r, g, b, a}`` suitable for any tool that takes
        ``color_r``/``color_g``/``color_b``/``color_a`` params.
        Lets the caller paste CSS / design-tool hex codes without
        hand-translating to int quadruples (a common source of off-by-one
        color bugs).
        """
        r, g, b, a = cp.hex_to_rgba(hex_color, alpha=alpha)
        return {"r": r, "g": g, "b": b, "a": a}

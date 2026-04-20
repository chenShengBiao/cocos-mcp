"""Scene + node + generic-component + script-attach + prefab + batch tools."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from cocos import scene_builder as sb

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- Scene + node ----------------

    @mcp.tool()
    def cocos_create_scene(project_path: str, scene_name: str = "Game",
                           canvas_width: int = 960, canvas_height: int = 640,
                           clear_color_r: int = 135, clear_color_g: int = 206,
                           clear_color_b: int = 235) -> dict:
        """Create a minimal empty 2D scene + meta in assets/scenes/.

        Includes Canvas + UICamera (cc.Camera) + cc.Canvas + Widget +
        SceneGlobals (Ambient/Skybox/Shadows) + PrefabInfo. The Camera's
        `clearColor` is set so a solid sky-blue background is visible
        even before any sprite is added.

        Returns canonical IDs:
          {scene_path, scene_uuid, scene_node_id, canvas_node_id,
           ui_camera_node_id, camera_component_id, canvas_component_id}

        These IDs are array-index references into the scene's JSON;
        use them as `parent_id` / `node_id` in subsequent tool calls.
        """
        p = Path(project_path).expanduser().resolve()
        scene_path = p / "assets" / "scenes" / f"{scene_name}.scene"
        return sb.create_empty_scene(
            scene_path, canvas_width=canvas_width, canvas_height=canvas_height,
            clear_color=(clear_color_r, clear_color_g, clear_color_b, 255),
        )

    @mcp.tool()
    def cocos_create_node(scene_path: str, parent_id: int, name: str,
                          pos_x: float = 0, pos_y: float = 0, pos_z: float = 0,
                          scale: float = 1, layer: int = 33554432, active: bool = True) -> int:
        """Append a new cc.Node under `parent_id`, return its array index.

        `layer` defaults to UI_2D (33554432). Use 1073741824 for the camera node.
        The new node has no components yet — call `cocos_add_uitransform`,
        `cocos_add_sprite` etc. to attach them.
        """
        return sb.add_node(
            scene_path, parent_id, name,
            lpos=(pos_x, pos_y, pos_z), lscale=(scale, scale, 1),
            layer=layer, active=active,
        )

    # ---------------- Base components ----------------

    @mcp.tool()
    def cocos_add_uitransform(scene_path: str, node_id: int, width: float, height: float,
                              anchor_x: float = 0.5, anchor_y: float = 0.5) -> int:
        """Attach a cc.UITransform to a node. Required for any UI rendering."""
        return sb.add_uitransform(scene_path, node_id, width, height, anchor_x, anchor_y)

    @mcp.tool()
    def cocos_add_sprite(scene_path: str, node_id: int, sprite_frame_uuid: str | None = None,
                         size_mode: int = 0,
                         color_r: int = 255, color_g: int = 255, color_b: int = 255, color_a: int = 255,
                         color_preset: str | None = None) -> int:
        """Attach a cc.Sprite to a node.

        `sprite_frame_uuid` is the `<uuid>@f9941` form returned by
        `cocos_add_image` or `cocos_get_sprite_frame_uuid`.
        `size_mode`: 0=CUSTOM (use UITransform's contentSize), 1=TRIMMED, 2=RAW.
        `color_preset`: pick from the project's UI theme (e.g. "primary",
        "surface") to tint the sprite — overrides the explicit RGBA args.
        """
        return sb.add_sprite(scene_path, node_id, sprite_frame_uuid, size_mode,
                             (color_r, color_g, color_b, color_a),
                             color_preset=color_preset)

    @mcp.tool()
    def cocos_add_label(scene_path: str, node_id: int, text: str, font_size: int = 40,
                        color_r: int = 255, color_g: int = 255, color_b: int = 255, color_a: int = 255,
                        h_align: int = 1, v_align: int = 1,
                        overflow: int = 0, enable_wrap: bool = False, line_height: int = 0,
                        enable_outline: bool = True, outline_width: int = 3,
                        cache_mode: int = 0,
                        color_preset: str | None = None,
                        size_preset: str | None = None,
                        outline_color_preset: str | None = None) -> int:
        """Attach cc.Label. overflow: 0=NONE 1=CLAMP 2=SHRINK 3=RESIZE_HEIGHT.
        cache_mode: 0=NONE 1=BITMAP 2=CHAR. CLAMP truncates, SHRINK auto-shrinks font.

        Design-token presets (override the equivalent explicit arg):
          - ``color_preset``: e.g. ``"text"``, ``"primary"``, ``"danger"``
          - ``size_preset``: ``"title"`` | ``"heading"`` | ``"body"`` | ``"caption"``
          - ``outline_color_preset``: e.g. ``"bg"`` for dark outline on light
        Set the theme once via ``cocos_set_ui_theme``; un-themed projects
        fall back to ``dark_game`` defaults so presets always resolve.
        """
        return sb.add_label(scene_path, node_id, text, font_size,
                            (color_r, color_g, color_b, color_a), h_align, v_align,
                            overflow, enable_wrap, line_height, enable_outline,
                            (0, 0, 0, 255), outline_width, cache_mode,
                            color_preset=color_preset, size_preset=size_preset,
                            outline_color_preset=outline_color_preset)

    @mcp.tool()
    def cocos_add_graphics(scene_path: str, node_id: int) -> int:
        """Attach a cc.Graphics to a node (for runtime vector drawing)."""
        return sb.add_graphics(scene_path, node_id)

    @mcp.tool()
    def cocos_add_widget(scene_path: str, node_id: int, align_flags: int = 45,
                         target_id: int | None = None) -> int:
        """Attach a cc.Widget for screen-anchor layout. align_flags is a bitmask."""
        return sb.add_widget(scene_path, node_id, align_flags, target_id)

    # ---------------- Generic component ----------------

    @mcp.tool()
    def cocos_add_component(scene_path: str, node_id: int, type_name: str,
                            props: dict | None = None) -> int:
        """Attach any cc component by its full type name (e.g. 'cc.RigidBody2D').

        `props` values are auto-wrapped: list[3]->Vec3, int->__id__ ref, etc.
        For resource refs pass {"__uuid__": "<uuid>"}.
        """
        return sb.add_component(scene_path, node_id, type_name, props)

    # ---------------- Script binding & properties ----------------

    @mcp.tool()
    def cocos_attach_script(scene_path: str, node_id: int, script_uuid_compressed: str,
                            props: dict | None = None) -> int:
        """Attach a custom TypeScript script component to a node.

        `script_uuid_compressed` is the 23-char short form (run
        `cocos_compress_uuid` on the .ts.meta uuid).

        `props` lets you set @property fields. Pass int values for
        node/component refs (they'll be wrapped as {"__id__": N}).
        Pass strings/numbers/bools for plain values.
        """
        return sb.add_script(scene_path, node_id, script_uuid_compressed, props)

    @mcp.tool()
    def cocos_link_property(scene_path: str, component_id: int, prop_name: str,
                            target_id: int | None) -> str:
        """Set a @property on a component to reference another node/component.

        Pass `target_id=None` to clear the reference.
        """
        sb.link_property(scene_path, component_id, prop_name, target_id)
        return f"linked {component_id}.{prop_name} -> {target_id}"

    @mcp.tool()
    def cocos_set_property(scene_path: str, object_id: int, prop_name: str, value: Any) -> str:
        """Set a literal (non-reference) property on any scene object.

        Use this for things like `_string`, `_fontSize`, `_color`, etc.
        For node/component references, use `cocos_link_property` instead.
        """
        sb.set_property(scene_path, object_id, prop_name, value)
        return f"set {object_id}.{prop_name}"

    @mcp.tool()
    def cocos_set_uuid_property(scene_path: str, object_id: int, prop_name: str,
                                uuid: str) -> str:
        """Set a property to a __uuid__ resource ref (SpriteFrame, AudioClip, etc.)."""
        sb.set_uuid_property(scene_path, object_id, prop_name, uuid)
        return f"set {object_id}.{prop_name} -> uuid:{uuid[:12]}..."

    # ---------------- Node mutation ----------------

    @mcp.tool()
    def cocos_set_node_position(scene_path: str, node_id: int, x: float, y: float, z: float = 0) -> str:
        """Set a node's local position (x, y, z). z defaults to 0 for 2D scenes."""
        sb.set_node_position(scene_path, node_id, x, y, z)
        return f"node {node_id} -> ({x},{y},{z})"

    @mcp.tool()
    def cocos_set_node_active(scene_path: str, node_id: int, active: bool) -> str:
        """Toggle a node's _active flag (True = visible/ticking, False = disabled)."""
        sb.set_node_active(scene_path, node_id, active)
        return f"node {node_id} active={active}"

    @mcp.tool()
    def cocos_set_node_scale(scene_path: str, node_id: int,
                             sx: float, sy: float, sz: float = 1) -> str:
        """Set a node's local scale."""
        sb.set_node_scale(scene_path, node_id, sx, sy, sz)
        return f"node {node_id} scale=({sx},{sy},{sz})"

    @mcp.tool()
    def cocos_set_node_rotation(scene_path: str, node_id: int, angle_z: float) -> str:
        """Set 2D rotation (euler Z) in degrees."""
        sb.set_node_rotation(scene_path, node_id, angle_z)
        return f"node {node_id} rotation={angle_z}"

    @mcp.tool()
    def cocos_set_node_layer(scene_path: str, node_id: int, layer: int) -> str:
        """Set a node's layer bitmask. Common: UI_2D=33554432, DEFAULT=1073741824."""
        sb.set_node_layer(scene_path, node_id, layer)
        return f"node {node_id} layer={layer}"

    @mcp.tool()
    def cocos_move_node(scene_path: str, node_id: int, new_parent_id: int,
                        sibling_index: int = -1) -> str:
        """Re-parent a node. sibling_index=-1 appends as last child."""
        sb.move_node(scene_path, node_id, new_parent_id, sibling_index)
        return f"node {node_id} moved to parent {new_parent_id}"

    @mcp.tool()
    def cocos_delete_node(scene_path: str, node_id: int) -> str:
        """Soft-delete a node (disconnect from parent, deactivate). Indices stay stable."""
        sb.delete_node(scene_path, node_id)
        return f"node {node_id} deleted"

    @mcp.tool()
    def cocos_duplicate_node(scene_path: str, node_id: int,
                             new_name: str | None = None) -> int:
        """Shallow-copy a node (no children/components). Returns new node index."""
        return sb.duplicate_node(scene_path, node_id, new_name)

    # ---------------- Scene introspection ----------------

    @mcp.tool()
    def cocos_find_node_by_name(scene_path: str, name: str) -> int | None:
        """Find the first node with the given name. Returns its array index, or None."""
        return sb.find_node_by_name(scene_path, name)

    @mcp.tool()
    def cocos_list_scene_nodes(scene_path: str) -> list[dict]:
        """List every cc.Node in the scene with its id, name, parent, components, children."""
        return sb.list_nodes(scene_path)

    @mcp.tool()
    def cocos_validate_scene(scene_path: str) -> dict:
        """Sanity-check a scene file: ref ranges, type tags, parent linkage.

        Returns {valid: bool, object_count: int, issues: [...]}. Run this
        after building a scene to catch dangling __id__ references before
        invoking `cocos_build`.

        NOTE: structural-only. To check whether the scene's components
        match the project's enabled engine modules (the "build succeeds
        but RigidBody2D doesn't work" class of bugs), also call
        `cocos_audit_scene_modules`.
        """
        return sb.validate_scene(scene_path)

    @mcp.tool()
    def cocos_lint_ui(scene_path: str) -> dict:
        """Non-structural UI quality check (complement to cocos_validate_scene).

        Flags issues that build + load cleanly but produce bad UX:
          - Button touch target below 44×44 (iOS HIG / Material 48dp min)
          - Label overflow=NONE + wrap off in a box that likely clips the text
          - UI component on a node with layer != UI_2D (UICamera won't render it)

        Returns {ok, scene_path, warnings:[{rule, node_id, node_name, message}]}.
        All warnings are non-fatal; the caller decides what to fix.
        """
        return sb.lint_ui(scene_path)

    @mcp.tool()
    def cocos_audit_scene_modules(scene_path: str,
                                  project_path: str | None = None) -> dict:
        """Cross-check scene components against the project's engine.json.

        Catches the single highest-frequency "build succeeded, game broken
        at runtime" failure: using a component (RigidBody2D, Spine,
        VideoPlayer, ...) whose engine module is currently disabled.
        Build produces artifacts, the scene loads, but the components
        silently do nothing.

        ``project_path=None`` → walks up from the scene file looking for
        package.json. Pass explicitly when the scene lives outside the
        project (prefab library, template copy).

        Returns {ok, project_path, required, enabled, disabled, actions}.
        When ok=False, actions lists copy-pasteable next steps
        (cocos_set_engine_module calls + the library clean that
        module changes need).
        """
        return sb.audit_scene_modules(scene_path, project_path)

    @mcp.tool()
    def cocos_get_object_count(scene_path: str) -> int:
        """Return the total number of objects in the scene/prefab JSON array."""
        return sb.get_object_count(scene_path)

    @mcp.tool()
    def cocos_get_object(scene_path: str, object_id: int) -> dict:
        """Return the raw JSON dict of a scene object (for debugging/inspection)."""
        return sb.get_object(scene_path, object_id)

    # ---------------- Prefab ----------------

    @mcp.tool()
    def cocos_create_prefab(project_path: str, prefab_name: str, root_name: str | None = None) -> dict:
        """Create an empty .prefab in assets/prefabs/ with a single root node."""
        p = Path(project_path).expanduser().resolve()
        prefab_path = p / "assets" / "prefabs" / f"{prefab_name}.prefab"
        return sb.create_prefab(prefab_path, root_name=root_name or prefab_name)

    @mcp.tool()
    def cocos_instantiate_prefab(scene_path: str, parent_id: int, prefab_path: str,
                                 name: str | None = None,
                                 pos_x: float | None = None,
                                 pos_y: float | None = None,
                                 pos_z: float | None = None,
                                 scale: float | None = None) -> int:
        """Drop a .prefab file into the scene as a child node — returns root id.

        Reads the .prefab JSON, deep-copies its node tree (root + children +
        components), shifts every internal __id__ reference, gives every cloned
        object a fresh _id, refreshes each cc.PrefabInfo.fileId so multiple
        instances of the same prefab don't alias, and parents the new root
        under `parent_id`.

        Treats the prefab as **unlinked** (a one-shot copy). If you later edit
        the .prefab, instances already dropped into the scene will NOT update —
        re-instantiate to pick up the changes.

        Pass any of name / pos_x / pos_y / pos_z / scale to override the root's
        defaults (otherwise the prefab's own values stay).
        """
        lpos = None
        if pos_x is not None or pos_y is not None or pos_z is not None:
            lpos = (pos_x or 0, pos_y or 0, pos_z or 0)
        lscale = None if scale is None else (scale, scale, scale)
        return sb.instantiate_prefab(scene_path, parent_id, prefab_path,
                                     name=name, lpos=lpos, lscale=lscale)

    # ---------------- Scene globals: ambient / skybox / shadows ----------------

    @mcp.tool()
    def cocos_set_ambient(scene_path: str,
                          sky_color_r: float | None = None, sky_color_g: float | None = None,
                          sky_color_b: float | None = None, sky_color_a: float | None = None,
                          sky_illum: float | None = None,
                          ground_r: float | None = None, ground_g: float | None = None,
                          ground_b: float | None = None, ground_a: float | None = None) -> dict:
        """Configure ambient lighting on the scene's cc.AmbientInfo.

        Colors are floats 0..1 (NOT 0..255 — sky/ground colors in Cocos are
        normalized like material PBR inputs). Pass None to leave unchanged.
        sky_illum is in lux, default ~20000. The scene must have been created
        via cocos_create_scene (which auto-attaches AmbientInfo).
        """
        sky_color = None
        if any(c is not None for c in (sky_color_r, sky_color_g, sky_color_b, sky_color_a)):
            sky_color = (sky_color_r or 0, sky_color_g or 0,
                         sky_color_b or 0, sky_color_a or 0)
        ground = None
        if any(c is not None for c in (ground_r, ground_g, ground_b, ground_a)):
            ground = (ground_r or 0, ground_g or 0, ground_b or 0, ground_a or 0)
        return sb.set_ambient(scene_path, sky_color=sky_color, sky_illum=sky_illum,
                              ground_albedo=ground)

    @mcp.tool()
    def cocos_set_skybox(scene_path: str,
                         enabled: bool | None = None,
                         envmap_uuid: str | None = None,
                         use_hdr: bool | None = None,
                         env_lighting_type: int | None = None) -> dict:
        """Configure the scene's cc.SkyboxInfo.

        env_lighting_type: 0=HEMISPHERE_DIFFUSE (cheap default), 1=AUTOGEN_HEMISPHERE_DIFFUSE,
        2=DIFFUSEMAP_WITH_REFLECTION (PBR, needs envmap).

        envmap_uuid points at a cc.TextureCube asset. Pass empty string ""
        to clear. Pass None to leave fields unchanged.
        """
        return sb.set_skybox(scene_path, enabled=enabled, envmap_uuid=envmap_uuid,
                             use_hdr=use_hdr, env_lighting_type=env_lighting_type)

    @mcp.tool()
    def cocos_set_shadows(scene_path: str,
                          enabled: bool | None = None,
                          normal_x: float | None = None, normal_y: float | None = None,
                          normal_z: float | None = None,
                          distance: float | None = None,
                          color_r: int | None = None, color_g: int | None = None,
                          color_b: int | None = None, color_a: int | None = None) -> dict:
        """Configure planar shadows on the scene's cc.ShadowsInfo.

        normal: ground plane normal, defaults to (0, 1, 0) for flat ground.
        distance: signed offset along normal from world origin.
        color: shadow color, ints 0..255.

        Pass None on any axis/channel to leave it unchanged. Enabling planar
        shadows also typically requires at least one DirectionalLight in the scene.
        """
        normal = None
        if any(c is not None for c in (normal_x, normal_y, normal_z)):
            normal = (normal_x or 0, normal_y or 1, normal_z or 0)
        color = None
        if any(c is not None for c in (color_r, color_g, color_b, color_a)):
            color = (color_r or 0, color_g or 0, color_b or 0, color_a or 76)
        return sb.set_shadows(scene_path, enabled=enabled, normal=normal,
                              distance=distance, color=color)

    @mcp.tool()
    def cocos_set_fog(scene_path: str,
                      enabled: bool | None = None,
                      fog_type: int | None = None,
                      color_r: int | None = None, color_g: int | None = None,
                      color_b: int | None = None, color_a: int | None = None,
                      density: float | None = None,
                      start: float | None = None,
                      end: float | None = None,
                      atten: float | None = None,
                      top: float | None = None,
                      fog_range: float | None = None,
                      accurate: bool | None = None) -> dict:
        """Configure volumetric fog on the scene's cc.FogInfo.

        Fourth scene-global alongside ambient/skybox/shadows. Lazy-creates
        a cc.FogInfo + links it from cc.SceneGlobals if the scene doesn't
        have one yet (scenes built before this tool existed won't).

        fog_type: 0=LINEAR (use start+end), 1=EXP (density), 2=EXP_SQUARED,
        3=LAYERED (top+range). Atmospheric settings are inter-dependent —
        LINEAR ignores density, EXP/EXP_SQUARED ignore start/end.
        """
        color = None
        if any(c is not None for c in (color_r, color_g, color_b, color_a)):
            color = (color_r or 200, color_g or 200, color_b or 200, color_a or 255)
        return sb.set_fog(scene_path, enabled=enabled, fog_type=fog_type,
                          color=color, density=density, start=start, end=end,
                          atten=atten, top=top, fog_range=fog_range,
                          accurate=accurate)

    # ---------------- Scene batch mode ----------------

    @mcp.tool()
    def cocos_batch_scene_ops(scene_path: str, operations: list[dict]) -> dict:
        """PREFERRED for ≥3 sequential mutations on the same scene.

        Execute multiple scene operations in a single file read/write cycle.
        ~80× faster than calling individual ``cocos_add_*`` / ``cocos_set_*``
        tools when building more than a handful of nodes/components on the
        same scene; the file is parsed once, mutated in memory, and
        serialized once at the end.

        Rule of thumb: if you would otherwise call ``cocos_add_*``,
        ``cocos_attach_*``, ``cocos_set_*``, or ``cocos_link_*`` three or
        more times in a row on the same scene, use this tool instead. Pass
        all the ops in one call; use ``"$N"`` back-references for ids that
        earlier ops produced.

        Each operation is a dict with an 'op' key and operation-specific
        params. Returns {object_count, ops_executed, results: [...]}.

        Supported ops:
          Structural:
            - {"op": "add_node", "parent_id": N, "name": "...", "pos_x": ..., ...}
            - {"op": "attach_script", "node_id": N, "script_uuid_compressed": "...", "props": {...}}
            - {"op": "link_property", "component_id": N, "prop_name": "...", "target_id": M}
            - {"op": "set_property", "object_id": N, "prop_name": "...", "value": ...}
            - {"op": "set_uuid_property", "object_id": N, "prop_name": "...", "uuid": "..."}
            - {"op": "set_position", "node_id": N, "x": X, "y": Y, "z": Z}
            - {"op": "set_scale", "node_id": N, "sx": ..., "sy": ..., "sz": ...}
            - {"op": "set_rotation", "node_id": N, "angle_z": deg}
            - {"op": "set_layer", "node_id": N, "layer": L}
            - {"op": "set_active", "node_id": N, "active": true/false}

          Components:
            - {"op": "add_uitransform", "node_id": N, "width": W, "height": H, "anchor_x": ..., "anchor_y": ...}
            - {"op": "add_widget", "node_id": N, "align_flags": 45, "target_id": M?}
            - {"op": "add_sprite", "node_id": N, "sprite_frame_uuid": "...", "size_mode": 0}
            - {"op": "add_label", "node_id": N, "text": "...", "font_size": 40, "color_r"...}
            - {"op": "add_graphics", "node_id": N}
            - {"op": "add_camera", "node_id": N, "ortho_height": ..., "clear_color_r"...}
            - {"op": "add_mask", "node_id": N, "mask_type": 0, "inverted": false, "segments": 64}
            - {"op": "add_richtext", "node_id": N, "text": "<b>Hi</b>", "font_size": 40, ...}
            - {"op": "add_button", "node_id": N, "transition": 2, "zoom_scale": 1.1}
            - {"op": "add_layout", "node_id": N, "layout_type": 1, "spacing_x": ..., ...}
            - {"op": "add_progress_bar", "node_id": N, "mode": 0, "total_length": 100, "progress": 1.0, "bar_sprite_id": M?}
            - {"op": "add_audio_source", "node_id": N, "clip_uuid": "...", "volume": 1.0, "loop": false, "play_on_awake": false}
            - {"op": "add_animation", "node_id": N, "default_clip_uuid": "...", "clip_uuids": [...], "play_on_load": true}
            - {"op": "add_rigidbody2d", "node_id": N, "body_type": 2, ...}
            - {"op": "add_box_collider2d", "node_id": N, "width": W, ...}
            - {"op": "add_circle_collider2d", "node_id": N, "radius": R, ...}
            - {"op": "add_component", "node_id": N, "type_name": "cc.X", "props": {...}}

        Node/component IDs returned by prior ops can be referenced as "$N"
        where N is the 0-based op index. Example:
          [{"op": "add_node", "parent_id": 2, "name": "Bird"},
           {"op": "add_uitransform", "node_id": "$0", "width": 50, "height": 50}]
        """
        return sb.batch_ops(scene_path, operations)

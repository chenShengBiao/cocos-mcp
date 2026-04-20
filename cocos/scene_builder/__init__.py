"""Cocos Creator scene/prefab JSON builder.

Scene/prefab files are JSON arrays where each element is a serialized
object. References between objects use ``{"__id__": <index>}``.

Design choice: every operation reads the file, mutates, writes back. MCP
tools are stateless and the on-disk file is always the single source of
truth — no in-memory session to lose. Indices are stable as long as we
only append; tools never reorder or delete entries from the array.

This module used to be a single 1811-line file; it has been split by
domain for maintainability:

* ``scene_builder``           — this file; core scene lifecycle, node
                                 and basic-component mutators, validation,
                                 generic ``add_component``
* ``scene_builder.physics``   — RigidBody2D, colliders, nine ``Joint2D``
                                 variants
* ``scene_builder.ui``        — Button, Layout, ProgressBar, ScrollView,
                                 Toggle, EditBox, Slider, Mask, RichText,
                                 sprite variants, UIOpacity, SafeArea,
                                 PageView, ToggleContainer, MotionStreak,
                                 ``make_event_handler`` / ``make_click_event``
* ``scene_builder.media``     — AudioSource, Animation, ParticleSystem2D,
                                 Camera, Spine, DragonBones, TiledMap,
                                 VideoPlayer, and the scene-globals setters
                                 (set_ambient / set_skybox / set_shadows)
* ``scene_builder.prefab``    — create_prefab + instantiate_prefab
* ``scene_builder.batch``     — ``batch_ops`` bulk mutator
* ``scene_builder._helpers``  — primitive value factories + scene IO
                                 (``_load_scene`` / ``_save_scene``) +
                                 the session-level scene cache

The public surface is re-exported here so ``from cocos import scene_builder
as sb; sb.add_button(...)`` works regardless of which submodule the
function lives in.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..meta_util import scene_meta
from ..types import SceneCreateResult, ValidationResult
from ..uuid_util import new_uuid
from ._helpers import (
    LAYER_DEFAULT,
    LAYER_UI_2D,
    _attach_component,
    _auto_wrap_value,
    _color,
    _ensure_uitransform,
    _has_uitransform,
    _load_scene,
    _make_ambient_info,
    _make_camera,
    _make_canvas,
    _make_graphics,
    _make_label,
    _make_node,
    _make_script_component,
    _make_shadows_info,
    _make_skybox_info,
    _make_sprite,
    _make_uitransform,
    _make_widget,
    _nid,
    _quat,
    _rect,
    _ref,
    _save_scene,
    _size,
    _UI_RENDER_TYPES,
    _vec2,
    _vec3,
    _vec4,
    _wrap_props,
    invalidate_scene_cache,
)
from .batch import batch_ops

# Re-exports from submodules — late, pragmatic imports at the bottom so
# that each submodule can lazily ``from cocos.scene_builder import
# add_component`` without a load-time cycle.
from .media import (
    _find_global_info,
    add_animation,
    add_audio_source,
    add_camera,
    add_dragonbones,
    add_particle_system_2d,
    add_spine,
    add_tiled_layer,
    add_tiled_map,
    add_video_player,
    set_ambient,
    set_shadows,
    set_skybox,
)
from .physics import (
    _attach_joint,
    _make_joint2d_base,
    add_box_collider2d,
    add_circle_collider2d,
    add_distance_joint2d,
    add_hinge_joint2d,
    add_motor_joint2d,
    add_mouse_joint2d,
    add_polygon_collider2d,
    add_relative_joint2d,
    add_rigidbody2d,
    add_slider_joint2d,
    add_spring_joint2d,
    add_weld_joint2d,
    add_wheel_joint2d,
)
from .prefab import (
    _shift_id_refs,
    create_prefab,
    instantiate_prefab,
)
from .ui import (
    _serialize_events,
    add_block_input_events,
    add_button,
    add_editbox,
    add_filled_sprite,
    add_layout,
    add_mask,
    add_motion_streak,
    add_page_view,
    add_progress_bar,
    add_richtext,
    add_safe_area,
    add_scroll_view,
    add_slider,
    add_sliced_sprite,
    add_tiled_sprite,
    add_toggle,
    add_toggle_container,
    add_ui_opacity,
    make_click_event,
    make_event_handler,
)

__all__ = ["batch_ops", "invalidate_scene_cache"]

# ----------- scene lifecycle -----------

def create_empty_scene(scene_path: str | Path, scene_uuid: str | None = None,
                       canvas_width: int = 960, canvas_height: int = 640,
                       clear_color: tuple = (135, 206, 235, 255)) -> SceneCreateResult:
    """Create a minimal empty 2D scene with Canvas + UICamera + SceneGlobals.

    Returns a dict with the canonical node/component ids the caller needs:
      - scene_uuid
      - canvas_node_id
      - ui_camera_node_id
      - camera_component_id
      - canvas_component_id
      - scene_node_id (always 1)
    """
    scene_path = Path(scene_path)
    scene_path.parent.mkdir(parents=True, exist_ok=True)

    if scene_uuid is None:
        scene_uuid = new_uuid()

    objects: list = []

    def push(obj):
        idx = len(objects)
        objects.append(obj)
        return idx

    # [0] cc.SceneAsset
    asset_idx = push({
        "__type__": "cc.SceneAsset",
        "_name": "",
        "_objFlags": 0,
        "_native": "",
        "scene": None,  # Will point to the scene node at [1]
    })

    # [1] cc.Scene
    scene_obj = {
        "__type__": "cc.Scene",
        "_name": scene_path.stem,
        "_objFlags": 0,
        "_parent": None,
        "_children": [],
        "_active": True,
        "_components": [],
        "_prefab": None,
        "_lpos": _vec3(),
        "_lrot": _quat(),
        "_lscale": _vec3(1, 1, 1),
        "_layer": LAYER_UI_2D,
        "_euler": _vec3(),
        "autoReleaseAssets": False,
        "_globals": None,  # Will fill later
        "_id": _nid("scn"),
    }
    s_idx = push(scene_obj)
    objects[asset_idx]["scene"] = _ref(s_idx)

    # [2] Canvas cc.Node (UI layer)
    canvas_idx = push(_make_node("Canvas", s_idx))
    objects[s_idx]["_children"].append(_ref(canvas_idx))

    # [3] UICamera cc.Node (inside Canvas)
    uicam_idx = push(_make_node("UICamera", canvas_idx))
    objects[canvas_idx]["_children"].append(_ref(uicam_idx))

    # [4] cc.Camera on UICamera
    cam_cmp_idx = push(_make_camera(uicam_idx, ortho_height=canvas_height // 2, clear_color=clear_color))
    objects[uicam_idx]["_components"].append(_ref(cam_cmp_idx))

    # [5] cc.UITransform on Canvas (MUST be added BEFORE cc.Canvas so engine processes it first)
    canvas_uit_idx = push(_make_uitransform(canvas_idx, canvas_width, canvas_height))
    objects[canvas_idx]["_components"].append(_ref(canvas_uit_idx))

    # [6] cc.Canvas on Canvas (references the camera)
    canvas_cmp_idx = push(_make_canvas(canvas_idx, cam_cmp_idx))
    objects[canvas_idx]["_components"].append(_ref(canvas_cmp_idx))

    # [7] cc.Widget on Canvas (full-screen)
    canvas_widget_idx = push(_make_widget(canvas_idx))
    objects[canvas_idx]["_components"].append(_ref(canvas_widget_idx))

    # [8] cc.SceneGlobals
    globals_idx = push({
        "__type__": "cc.SceneGlobals",
        "ambient": None,
        "_skybox": None,
        "shadows": None,
    })
    objects[s_idx]["_globals"] = _ref(globals_idx)

    # [9] AmbientInfo
    ambient_idx = push(_make_ambient_info())
    objects[globals_idx]["ambient"] = _ref(ambient_idx)

    # [10] SkyboxInfo
    skybox_idx = push(_make_skybox_info())
    objects[globals_idx]["_skybox"] = _ref(skybox_idx)

    # [11] ShadowsInfo
    shadows_idx = push(_make_shadows_info())
    objects[globals_idx]["shadows"] = _ref(shadows_idx)

    # [12] PrefabInfo
    prefab_idx = push({
        "__type__": "cc.PrefabInfo",
        "fileId": scene_uuid,
    })
    objects[s_idx]["_prefab"] = _ref(prefab_idx)

    _save_scene(scene_path, objects)

    # also write meta sidecar
    from ..meta_util import write_meta
    write_meta(scene_path, scene_meta(uuid=scene_uuid))

    return {
        "scene_path": str(scene_path),
        "scene_uuid": scene_uuid,
        "scene_node_id": s_idx,
        "canvas_node_id": canvas_idx,
        "ui_camera_node_id": uicam_idx,
        "camera_component_id": cam_cmp_idx,
        "canvas_component_id": canvas_cmp_idx,
    }


# ----------- node + basic component mutators -----------

def add_node(scene_path: str | Path, parent_id: int, name: str,
             lpos=(0, 0, 0), lscale=(1, 1, 1), layer: int = LAYER_UI_2D, active: bool = True,
             sibling_index: int = -1) -> int:
    """Add a node. sibling_index=-1 appends (top of render order); 0=first child (bottom)."""
    s = _load_scene(scene_path)
    if parent_id < 0 or parent_id >= len(s):
        raise IndexError(f"parent_id {parent_id} out of range")
    parent = s[parent_id]
    if parent.get("__type__") not in ("cc.Node", "cc.Scene"):
        raise ValueError(f"parent {parent_id} is not a Node/Scene (got {parent.get('__type__')})")

    node = _make_node(name, parent_id, lpos=tuple(lpos), lscale=tuple(lscale), layer=layer, active=active)
    s.append(node)
    new_id = len(s) - 1
    children = parent.setdefault("_children", [])
    if sibling_index < 0 or sibling_index >= len(children):
        children.append(_ref(new_id))
    else:
        children.insert(sibling_index, _ref(new_id))
    _save_scene(scene_path, s)
    return new_id


def add_uitransform(scene_path: str | Path, node_id: int, width: float, height: float,
                    anchor_x: float = 0.5, anchor_y: float = 0.5) -> int:
    s = _load_scene(scene_path)
    cid = _attach_component(s, node_id, _make_uitransform(node_id, width, height, anchor_x, anchor_y))
    _save_scene(scene_path, s)
    return cid


def add_sprite(scene_path: str | Path, node_id: int, sprite_frame_uuid: str | None = None,
               size_mode: int = 0, color: tuple = (255, 255, 255, 255)) -> int:
    s = _load_scene(scene_path)
    cid = _attach_component(s, node_id, _make_sprite(node_id, sprite_frame_uuid, size_mode, color))
    _save_scene(scene_path, s)
    return cid


def add_label(scene_path: str | Path, node_id: int, text: str, font_size: int = 40,
              color: tuple = (255, 255, 255, 255), h_align: int = 1, v_align: int = 1,
              overflow: int = 0, enable_wrap: bool = False, line_height: int = 0,
              enable_outline: bool = True, outline_color: tuple = (0, 0, 0, 255),
              outline_width: int = 3, cache_mode: int = 0) -> int:
    """overflow: 0=NONE, 1=CLAMP, 2=SHRINK, 3=RESIZE_HEIGHT.
    cache_mode: 0=NONE, 1=BITMAP, 2=CHAR."""
    s = _load_scene(scene_path)
    cid = _attach_component(s, node_id, _make_label(
        node_id, text, font_size, color, h_align, v_align,
        overflow, enable_wrap, line_height, enable_outline, outline_color, outline_width, cache_mode))
    _save_scene(scene_path, s)
    return cid


def add_graphics(scene_path: str | Path, node_id: int) -> int:
    s = _load_scene(scene_path)
    cid = _attach_component(s, node_id, _make_graphics(node_id))
    _save_scene(scene_path, s)
    return cid


def add_widget(scene_path: str | Path, node_id: int, align_flags: int = 45,
               target_id: int | None = None) -> int:
    s = _load_scene(scene_path)
    cid = _attach_component(s, node_id, _make_widget(node_id, align_flags, target_id))
    _save_scene(scene_path, s)
    return cid


def add_script(scene_path: str | Path, node_id: int, script_uuid_compressed: str,
               props: dict | None = None) -> int:
    """Attach a custom TS script component to a node.

    `script_uuid_compressed` is the 23-char short form (use compress_uuid()
    on the script's .ts.meta uuid).

    `props` values are passed as-is. To reference a node/component, pass
    ``{"__id__": N}`` explicitly. To reference a resource (Prefab, SpriteFrame),
    pass ``{"__uuid__": "xxx"}``. Plain int/float/string/bool are kept as
    literal values.

    Example::

        add_script(scene, node, short_uuid, props={
            "scoreLabel": {"__id__": label_cmp_id},  # ref to component
            "birdNode": {"__id__": bird_node_id},     # ref to node
            "playerId": 1,                             # literal int (NOT a ref!)
            "speed": 100.0,                            # literal float
            "prefab": {"__uuid__": prefab_uuid},       # resource ref
        })
    """
    s = _load_scene(scene_path)
    # No auto-wrapping — all values passed as-is to avoid the int→ref footgun
    # (e.g. playerId: 1 should NOT become {"__id__": 1})
    cid = _attach_component(s, node_id, _make_script_component(script_uuid_compressed, node_id, props))
    _save_scene(scene_path, s)
    return cid


def link_property(scene_path: str | Path, component_id: int, prop_name: str, target_id: int | None) -> None:
    """Set a @property on a component to reference another node/component.

    Pass `target_id=None` to clear the reference.
    """
    s = _load_scene(scene_path)
    if component_id < 0 or component_id >= len(s):
        raise IndexError(f"component_id {component_id} out of range")
    s[component_id][prop_name] = _ref(target_id) if target_id is not None else None
    _save_scene(scene_path, s)


def set_property(scene_path: str | Path, object_id: int, prop_name: str, value: Any) -> None:
    """Set a literal (non-reference) property on any object in the scene."""
    s = _load_scene(scene_path)
    s[object_id][prop_name] = value
    _save_scene(scene_path, s)


def set_node_position(scene_path: str | Path, node_id: int, x: float, y: float, z: float = 0) -> None:
    s = _load_scene(scene_path)
    s[node_id]["_lpos"] = _vec3(x, y, z)
    _save_scene(scene_path, s)


def set_node_active(scene_path: str | Path, node_id: int, active: bool) -> None:
    s = _load_scene(scene_path)
    s[node_id]["_active"] = active
    _save_scene(scene_path, s)


def find_node_by_name(scene_path: str | Path, name: str) -> int | None:
    s = _load_scene(scene_path)
    for i, o in enumerate(s):
        if o.get("__type__") == "cc.Node" and o.get("_name") == name:
            return i
    return None


def list_nodes(scene_path: str | Path) -> list[dict]:
    s = _load_scene(scene_path)
    out = []
    for i, o in enumerate(s):
        if o.get("__type__") == "cc.Node":
            parent_ref = o.get("_parent")
            parent_id = parent_ref["__id__"] if parent_ref else None
            out.append({
                "id": i,
                "name": o.get("_name"),
                "parent_id": parent_id,
                "active": o.get("_active", True),
                "components": [c["__id__"] for c in o.get("_components", [])],
                "children": [c["__id__"] for c in o.get("_children", [])],
            })
    return out


# ----------- validation -----------

def validate_scene(scene_path: str | Path) -> ValidationResult:
    """Sanity-check a scene file: ref ranges, type tags, parent linkage,
    Canvas-Camera binding, and UI node ancestry."""
    s = _load_scene(scene_path)
    issues = []
    n = len(s)

    # --- 1. Check all __id__ refs are in range and have __type__ ---
    def walk_refs(obj, path=""):
        if isinstance(obj, dict):
            if "__id__" in obj and isinstance(obj["__id__"], int):
                rid = obj["__id__"]
                if rid < 0 or rid >= n:
                    issues.append(f"{path}: __id__ {rid} out of range [0,{n})")
                else:
                    target = s[rid]
                    if not isinstance(target, dict) or "__type__" not in target:
                        issues.append(f"{path}: __id__ {rid} target lacks __type__")
            for k, v in obj.items():
                walk_refs(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk_refs(v, f"{path}[{i}]")

    for i, o in enumerate(s):
        if not isinstance(o, dict):
            issues.append(f"[{i}]: not a dict")
            continue
        if "__type__" not in o:
            issues.append(f"[{i}]: missing __type__")
        walk_refs(o, f"[{i}]")

    # --- 2. Canvas must have a valid Camera ref ---
    for i, o in enumerate(s):
        if not isinstance(o, dict):
            continue
        if o.get("__type__") == "cc.Canvas":
            cam_ref = o.get("_cameraComponent")
            if cam_ref is None or not isinstance(cam_ref, dict):
                issues.append(f"[{i}] cc.Canvas: _cameraComponent is null (will crash on touch)")
            elif "__id__" in cam_ref:
                cid = cam_ref["__id__"]
                if cid < 0 or cid >= n:
                    issues.append(f"[{i}] cc.Canvas: _cameraComponent __id__ {cid} out of range")
                elif s[cid].get("__type__") != "cc.Camera":
                    issues.append(f"[{i}] cc.Canvas: _cameraComponent points to {s[cid].get('__type__')} not cc.Camera")

    # --- 3. UI nodes (with UITransform) should be under a Canvas ---
    canvas_node_ids = set()
    for o in s:
        if isinstance(o, dict) and o.get("__type__") == "cc.Canvas":
            node_ref = o.get("node")
            if node_ref and "__id__" in node_ref:
                canvas_node_ids.add(node_ref["__id__"])

    def _is_under_canvas(node_id: int, visited: set | None = None) -> bool:
        if visited is None:
            visited = set()
        if node_id in visited:
            return False
        visited.add(node_id)
        if node_id in canvas_node_ids:
            return True
        node = s[node_id] if 0 <= node_id < n else None
        if not node or not isinstance(node, dict):
            return False
        parent_ref = node.get("_parent")
        if parent_ref and isinstance(parent_ref, dict) and "__id__" in parent_ref:
            return _is_under_canvas(parent_ref["__id__"], visited)
        return False

    for i, o in enumerate(s):
        if not isinstance(o, dict) or o.get("__type__") != "cc.UITransform":
            continue
        node_ref = o.get("node")
        if not node_ref or "__id__" not in node_ref:
            continue
        node_id = node_ref["__id__"]
        if not _is_under_canvas(node_id):
            node_name = s[node_id].get("_name", "?") if 0 <= node_id < n else "?"
            issues.append(f"[{i}] UITransform on node '{node_name}'(#{node_id}) is NOT under any Canvas (will crash on touch)")

    # --- 4. Check for bare int values in component ref fields ---
    ref_field_map = {
        "cc.Button": ["target"],
        "cc.Toggle": ["target"],
        "cc.Canvas": ["_cameraComponent"],
        "cc.ProgressBar": ["_N$barSprite"],
        "cc.ScrollView": ["content"],
    }
    for i, o in enumerate(s):
        if not isinstance(o, dict):
            continue
        typ = o.get("__type__", "")
        if typ in ref_field_map:
            for field in ref_field_map[typ]:
                val = o.get(field)
                if isinstance(val, int):
                    issues.append(f"[{i}] {typ}.{field} is bare int {val} (should be {{__id__: {val}}})")

    return {
        "valid": len(issues) == 0,
        "object_count": n,
        "issues": issues[:50],
    }


# ----------- generic add_component -----------

def add_component(scene_path: str | Path, node_id: int, type_name: str,
                  props: dict | None = None) -> int:
    """Attach *any* cc component by its full type name.

    Example::

        add_component(scene, node, "cc.RigidBody2D", {
            "type": 2,        # Dynamic=2, Static=0, Kinematic=1
            "gravityScale": 1.0,
        })

    Props are merged as-is (NO auto-wrapping). For node/component references,
    pass ``{"__id__": N}`` explicitly. For resource refs, pass
    ``{"__uuid__": "<uuid>"}``. This avoids the footgun where ``type: 2``
    gets misinterpreted as a node ref.

    If you need int→ref heuristic wrapping, use ``cocos_attach_script`` instead
    (which is designed for @property references).
    """
    s = _load_scene(scene_path)
    obj: dict[str, Any] = {
        "__type__": type_name,
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_id),
        "_enabled": True,
        "__prefab": None,
        "_id": _nid("cmp"),
    }
    if props:
        obj.update(props)
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


# ----------- node mutation tools -----------

def set_node_scale(scene_path: str | Path, node_id: int, sx: float, sy: float, sz: float = 1) -> None:
    s = _load_scene(scene_path)
    s[node_id]["_lscale"] = _vec3(sx, sy, sz)
    _save_scene(scene_path, s)


def set_node_rotation(scene_path: str | Path, node_id: int, angle_z: float) -> None:
    """Set 2D rotation (euler z) in degrees."""
    s = _load_scene(scene_path)
    s[node_id]["_euler"] = _vec3(0, 0, angle_z)
    import math
    rad = math.radians(angle_z / 2)
    s[node_id]["_lrot"] = _quat(0, 0, math.sin(rad), math.cos(rad))
    _save_scene(scene_path, s)


def move_node(scene_path: str | Path, node_id: int, new_parent_id: int,
              sibling_index: int = -1) -> None:
    """Re-parent a node."""
    s = _load_scene(scene_path)
    node = s[node_id]
    if node.get("__type__") != "cc.Node":
        raise ValueError(f"node_id {node_id} is not a cc.Node")
    old_parent_ref = node.get("_parent")
    if old_parent_ref:
        old_parent = s[old_parent_ref["__id__"]]
        old_parent["_children"] = [c for c in old_parent.get("_children", []) if c.get("__id__") != node_id]
    node["_parent"] = _ref(new_parent_id)
    new_parent = s[new_parent_id]
    children = new_parent.setdefault("_children", [])
    if sibling_index < 0 or sibling_index >= len(children):
        children.append(_ref(node_id))
    else:
        children.insert(sibling_index, _ref(node_id))
    _save_scene(scene_path, s)


def delete_node(scene_path: str | Path, node_id: int) -> None:
    """Soft-delete: remove from parent's _children and set _active=False.

    We don't physically remove the entry from the array (that would break
    all __id__ indices). Instead we disconnect it from the tree.
    """
    s = _load_scene(scene_path)
    node = s[node_id]
    if node.get("__type__") != "cc.Node":
        raise ValueError(f"node_id {node_id} is not a cc.Node")
    parent_ref = node.get("_parent")
    if parent_ref:
        parent = s[parent_ref["__id__"]]
        parent["_children"] = [c for c in parent.get("_children", []) if c.get("__id__") != node_id]
    node["_active"] = False
    node["_parent"] = None
    node["_children"] = []
    _save_scene(scene_path, s)


def duplicate_node(scene_path: str | Path, node_id: int, new_name: str | None = None) -> int:
    """Shallow-copy a node (no children or components are duplicated)."""
    s = _load_scene(scene_path)
    src = s[node_id]
    if src.get("__type__") != "cc.Node":
        raise ValueError(f"node_id {node_id} is not a cc.Node")
    import copy
    dup = copy.deepcopy(src)
    if new_name:
        dup["_name"] = new_name
    dup["_id"] = _nid("dup")
    dup["_children"] = []
    dup["_components"] = []
    s.append(dup)
    new_id = len(s) - 1
    parent_ref = dup.get("_parent")
    if parent_ref:
        parent = s[parent_ref["__id__"]]
        parent.setdefault("_children", []).append(_ref(new_id))
    _save_scene(scene_path, s)
    return new_id


def set_uuid_property(scene_path: str | Path, object_id: int, prop_name: str, uuid: str) -> None:
    """Set a property to a __uuid__ resource reference (for SpriteFrame, AudioClip, Prefab, etc.)."""
    s = _load_scene(scene_path)
    s[object_id][prop_name] = {"__uuid__": uuid}
    _save_scene(scene_path, s)


def set_node_layer(scene_path: str | Path, node_id: int, layer: int) -> None:
    s = _load_scene(scene_path)
    s[node_id]["_layer"] = layer
    _save_scene(scene_path, s)


def get_object_count(scene_path: str | Path) -> int:
    return len(_load_scene(scene_path))


def get_object(scene_path: str | Path, object_id: int) -> dict:
    """Return the raw dict of a scene object (for debugging)."""
    s = _load_scene(scene_path)
    if object_id < 0 or object_id >= len(s):
        raise IndexError(f"object_id {object_id} out of range")
    return s[object_id]

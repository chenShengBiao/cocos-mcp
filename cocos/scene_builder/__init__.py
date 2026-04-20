"""Cocos Creator scene/prefab JSON builder.

Scene/prefab files are JSON arrays where each element is a serialized
object. References between objects use `{"__id__": <index>}`.

Design choice: every operation **reads the file, mutates, writes back**.
This way the MCP tools are stateless and the on-disk file is always the
single source of truth — no in-memory session to lose.

Indices are stable as long as we only append. Tools never reorder or
delete entries from the array.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..meta_util import prefab_meta, scene_meta
from ..types import BatchOpsResult, SceneCreateResult, ValidationResult
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
from .batch import batch_ops  # re-exported as sb.batch_ops

__all__ = ["batch_ops", "invalidate_scene_cache"]  # extended below as we go

# ----------- public API -----------

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

    # [0] SceneAsset
    sa_idx = push({
        "__type__": "cc.SceneAsset",
        "_name": scene_path.stem,
        "_objFlags": 0,
        "_native": "",
        "scene": None,
        "asyncLoadAssets": False,
    })

    # [1] Scene
    s_idx = push({
        "__type__": "cc.Scene",
        "_name": scene_path.stem,
        "_objFlags": 0,
        "_parent": None,
        "_children": [],
        "_active": True,
        "_components": [],
        "_prefab": None,
        "autoReleaseAssets": False,
        "_globals": None,
        "_id": scene_uuid,
    })
    objects[sa_idx]["scene"] = _ref(s_idx)

    # [2] Canvas node
    canvas_idx = push(_make_node("Canvas", s_idx, lpos=(canvas_width / 2, canvas_height / 2, 0)))
    objects[s_idx]["_children"].append(_ref(canvas_idx))

    # [3] UICamera node
    uicam_idx = push(_make_node("UICamera", canvas_idx, lpos=(0, 0, 1000), layer=LAYER_DEFAULT))
    objects[canvas_idx]["_children"].append(_ref(uicam_idx))

    # [4] cc.Camera component
    cam_cmp_idx = push(_make_camera(uicam_idx, ortho_height=canvas_height / 2, clear_color=clear_color))
    objects[uicam_idx]["_components"].append(_ref(cam_cmp_idx))

    # [5] Canvas UITransform
    canvas_uit_idx = push(_make_uitransform(canvas_idx, canvas_width, canvas_height))
    objects[canvas_idx]["_components"].append(_ref(canvas_uit_idx))

    # [6] cc.Canvas
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


# ---- mutation helpers (each = load → mutate → save) ----

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


# ----------- prefab support -----------

def create_prefab(prefab_path: str | Path, root_name: str = "Root", prefab_uuid: str | None = None) -> dict:
    """Create an empty .prefab file with one root node."""
    prefab_path = Path(prefab_path)
    prefab_path.parent.mkdir(parents=True, exist_ok=True)
    if prefab_uuid is None:
        prefab_uuid = new_uuid()

    objects: list[dict] = []

    def push(obj):
        idx = len(objects)
        objects.append(obj)
        return idx

    # [0] cc.Prefab
    p_idx = push({
        "__type__": "cc.Prefab",
        "_name": root_name,
        "_objFlags": 0,
        "_native": "",
        "data": None,
        "optimizationPolicy": 0,
        "asyncLoadAssets": False,
        "persistent": False,
    })

    # [1] Root cc.Node
    root_idx = push(_make_node(root_name, None))
    objects[p_idx]["data"] = _ref(root_idx)
    # 注意 prefab 节点的 _prefab 是 PrefabInfo 引用，会在最后填
    objects[root_idx]["_prefab"] = None  # placeholder

    # [N] PrefabInfo
    pi_idx = push({
        "__type__": "cc.PrefabInfo",
        "fileId": prefab_uuid,
    })
    objects[root_idx]["_prefab"] = _ref(pi_idx)

    _save_scene(prefab_path, objects)

    from ..meta_util import write_meta
    write_meta(prefab_path, prefab_meta(uuid=prefab_uuid, sync_node_name=root_name))

    return {
        "prefab_path": str(prefab_path),
        "prefab_uuid": prefab_uuid,
        "root_node_id": root_idx,
    }


# ================================================================
#  P0 extensions: generic component, physics, UI, audio, animation
# ================================================================

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


# ----------- physics helpers -----------

def add_rigidbody2d(scene_path: str | Path, node_id: int,
                    body_type: int = 2, gravity_scale: float = 1.0,
                    linear_damping: float = 0.0, angular_damping: float = 0.0,
                    fixed_rotation: bool = False, bullet: bool = False,
                    awake_on_load: bool = True) -> int:
    """Attach cc.RigidBody2D. body_type: 0=Static, 1=Kinematic, 2=Dynamic."""
    return add_component(scene_path, node_id, "cc.RigidBody2D", {
        "enabledContactListener": True,
        "bullet": bullet,
        "type": body_type,
        "allowSleep": True,
        "gravityScale": gravity_scale,
        "linearDamping": linear_damping,
        "angularDamping": angular_damping,
        "linearVelocity": [0.0, 0.0],
        "angularVelocity": 0.0,
        "fixedRotation": fixed_rotation,
        "awakeOnLoad": awake_on_load,
    })


def add_box_collider2d(scene_path: str | Path, node_id: int,
                       width: float = 100, height: float = 100,
                       offset_x: float = 0, offset_y: float = 0,
                       density: float = 1.0, friction: float = 0.2,
                       restitution: float = 0.0, is_sensor: bool = False,
                       tag: int = 0) -> int:
    """Attach cc.BoxCollider2D."""
    return add_component(scene_path, node_id, "cc.BoxCollider2D", {
        "tag": tag,
        "_density": density,
        "_sensor": is_sensor,
        "_friction": friction,
        "_restitution": restitution,
        "_size": [width, height],
        "_offset": [offset_x, offset_y],
    })


def add_circle_collider2d(scene_path: str | Path, node_id: int,
                          radius: float = 50,
                          offset_x: float = 0, offset_y: float = 0,
                          density: float = 1.0, friction: float = 0.2,
                          restitution: float = 0.0, is_sensor: bool = False,
                          tag: int = 0) -> int:
    """Attach cc.CircleCollider2D."""
    return add_component(scene_path, node_id, "cc.CircleCollider2D", {
        "tag": tag,
        "_density": density,
        "_sensor": is_sensor,
        "_friction": friction,
        "_restitution": restitution,
        "_radius": radius,
        "_offset": [offset_x, offset_y],
    })


def add_polygon_collider2d(scene_path: str | Path, node_id: int,
                           points: list[list[float]] | None = None,
                           density: float = 1.0, friction: float = 0.2,
                           restitution: float = 0.0, is_sensor: bool = False,
                           tag: int = 0) -> int:
    """Attach cc.PolygonCollider2D. `points` is a list of [x,y] vertex pairs."""
    pts = points or [[-50, -50], [50, -50], [50, 50], [-50, 50]]
    return add_component(scene_path, node_id, "cc.PolygonCollider2D", {
        "tag": tag,
        "_density": density,
        "_sensor": is_sensor,
        "_friction": friction,
        "_restitution": restitution,
        "_points": pts,
    })


# ----------- UI helpers -----------

def make_event_handler(target_node_id: int, component_name: str, handler: str,
                       custom_data: str = "") -> dict:
    """Build a serialized cc.EventHandler for any component event binding.

    Works with: ScrollView.scrollEvents, Toggle.checkEvents,
    Slider.slideEvents, EditBox.editingDidBegan/editingReturn, etc.

    Same format as cc.ClickEvent but uses cc.EventHandler type.
    """
    return {
        "__type__": "cc.EventHandler",
        "target": _ref(target_node_id),
        "_componentId": "",
        "component": component_name,
        "handler": handler,
        "customEventData": custom_data,
    }


def make_click_event(target_node_id: int, component_name: str, handler: str,
                     custom_data: str = "") -> dict:
    """Build a serialized cc.ClickEvent for Button.clickEvents.

    Args:
        target_node_id: The node that holds the script component (array index)
        component_name: The @ccclass name (e.g. "GameManager")
        handler: The method name to call (e.g. "onStartClick")
        custom_data: Optional string passed to the handler

    Example::

        evt = make_click_event(gm_node_id, "GameManager", "onStartClick")
        add_button(scene, btn_node, click_events=[evt])
    """
    return {
        "__type__": "cc.ClickEvent",
        "target": _ref(target_node_id),
        "_componentId": "",
        "component": component_name,
        "handler": handler,
        "customEventData": custom_data,
    }


def add_button(scene_path: str | Path, node_id: int,
               transition: int = 2, zoom_scale: float = 1.1,
               normal_color: tuple = (255, 255, 255, 255),
               hover_color: tuple = (211, 211, 211, 255),
               pressed_color: tuple = (150, 150, 150, 255),
               disabled_color: tuple = (124, 124, 124, 255),
               click_events: list[dict] | None = None) -> int:
    """Attach cc.Button. transition: 0=NONE, 1=COLOR, 2=SCALE, 3=SPRITE.

    Use ``make_click_event()`` to build entries for ``click_events``.
    """
    s = _load_scene(scene_path)
    # Build click events — they are inline objects in the scene array
    serialized_events = []
    if click_events:
        for evt in click_events:
            s.append(evt)
            serialized_events.append(_ref(len(s) - 1))

    obj = {
        "__type__": "cc.Button",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("btn"),
        "target": _ref(node_id),  # target = self node (required for SCALE transition)
        "transition": transition,
        "zoomScale": zoom_scale,
        "_N$normalColor": _color(*normal_color),
        "_N$hoverColor": _color(*hover_color),
        "pressedColor": _color(*pressed_color),
        "_N$disabledColor": _color(*disabled_color),
        "duration": 0.1,
        "_interactable": True,
        "clickEvents": serialized_events,
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_layout(scene_path: str | Path, node_id: int,
               layout_type: int = 1, spacing_x: float = 0, spacing_y: float = 0,
               padding_top: float = 0, padding_bottom: float = 0,
               padding_left: float = 0, padding_right: float = 0,
               resize_mode: int = 1,
               h_direction: int = 0, v_direction: int = 1) -> int:
    """Attach cc.Layout. layout_type: 0=NONE, 1=HORIZONTAL, 2=VERTICAL, 3=GRID."""
    return add_component(scene_path, node_id, "cc.Layout", {
        "_layoutType": layout_type,
        "_resizeMode": resize_mode,
        "_N$spacingX": spacing_x,
        "_N$spacingY": spacing_y,
        "_N$paddingTop": padding_top,
        "_N$paddingBottom": padding_bottom,
        "_N$paddingLeft": padding_left,
        "_N$paddingRight": padding_right,
        "_N$horizontalDirection": h_direction,
        "_N$verticalDirection": v_direction,
    })


def add_progress_bar(scene_path: str | Path, node_id: int,
                     bar_sprite_id: int | None = None,
                     mode: int = 0, total_length: float = 100,
                     progress: float = 1.0, reverse: bool = False) -> int:
    """Attach cc.ProgressBar. mode: 0=HORIZONTAL, 1=VERTICAL, 2=FILLED."""
    props: dict[str, Any] = {
        "mode": mode,
        "totalLength": total_length,
        "progress": progress,
        "reverse": reverse,
    }
    if bar_sprite_id is not None:
        props["_N$barSprite"] = _ref(bar_sprite_id)
    return add_component(scene_path, node_id, "cc.ProgressBar", props)


def _serialize_events(s: list, events: list[dict] | None) -> list:
    """Serialize event handler dicts into scene array, return list of refs."""
    if not events:
        return []
    refs = []
    for evt in events:
        s.append(evt)
        refs.append(_ref(len(s) - 1))
    return refs


def add_scroll_view(scene_path: str | Path, node_id: int,
                    content_id: int | None = None,
                    horizontal: bool = False, vertical: bool = True,
                    inertia: bool = True, brake: float = 0.75,
                    elastic: bool = True, bounce_duration: float = 0.23,
                    scroll_events: list[dict] | None = None) -> int:
    """Attach cc.ScrollView. scroll_events: list from make_event_handler()."""
    s = _load_scene(scene_path)
    ser_events = _serialize_events(s, scroll_events)
    obj: dict[str, Any] = {
        "__type__": "cc.ScrollView",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("scv"),
        "horizontal": horizontal,
        "vertical": vertical,
        "inertia": inertia,
        "brake": brake,
        "elastic": elastic,
        "bounceDuration": bounce_duration,
        "scrollEvents": ser_events,
    }
    if content_id is not None:
        obj["content"] = _ref(content_id)
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_toggle(scene_path: str | Path, node_id: int,
               is_checked: bool = False, transition: int = 2,
               check_events: list[dict] | None = None) -> int:
    """Attach cc.Toggle. check_events: list from make_event_handler()."""
    s = _load_scene(scene_path)
    ser_events = _serialize_events(s, check_events)
    obj = {
        "__type__": "cc.Toggle",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("tgl"),
        "target": _ref(node_id),
        "isChecked": is_checked,
        "transition": transition,
        "_interactable": True,
        "checkEvents": ser_events,
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_editbox(scene_path: str | Path, node_id: int,
                placeholder: str = "Enter text...",
                max_length: int = -1, input_mode: int = 6,
                return_type: int = 0,
                editing_did_began: list[dict] | None = None,
                editing_did_ended: list[dict] | None = None,
                editing_return: list[dict] | None = None,
                text_changed: list[dict] | None = None) -> int:
    """Attach cc.EditBox. All event params accept lists from make_event_handler()."""
    s = _load_scene(scene_path)
    obj = {
        "__type__": "cc.EditBox",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("edb"),
        "placeholder": placeholder,
        "maxLength": max_length,
        "inputMode": input_mode,
        "returnType": return_type,
        "_string": "",
        "editingDidBegan": _serialize_events(s, editing_did_began),
        "editingDidEnded": _serialize_events(s, editing_did_ended),
        "editingReturn": _serialize_events(s, editing_return),
        "textChanged": _serialize_events(s, text_changed),
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_slider(scene_path: str | Path, node_id: int,
               direction: int = 0, progress: float = 0.5,
               slide_events: list[dict] | None = None) -> int:
    """Attach cc.Slider. slide_events: list from make_event_handler()."""
    s = _load_scene(scene_path)
    ser_events = _serialize_events(s, slide_events)
    obj = {
        "__type__": "cc.Slider",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("sld"),
        "direction": direction,
        "progress": progress,
        "slideEvents": ser_events,
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


# ----------- audio -----------

def add_audio_source(scene_path: str | Path, node_id: int,
                     clip_uuid: str | None = None,
                     play_on_awake: bool = False, loop: bool = False,
                     volume: float = 1.0) -> int:
    """Attach cc.AudioSource."""
    props: dict[str, Any] = {
        "playOnAwake": play_on_awake,
        "loop": loop,
        "volume": volume,
    }
    if clip_uuid:
        props["_clip"] = {"__uuid__": clip_uuid}
    return add_component(scene_path, node_id, "cc.AudioSource", props)


# ----------- animation -----------

def add_animation(scene_path: str | Path, node_id: int,
                  default_clip_uuid: str | None = None,
                  play_on_load: bool = True,
                  clip_uuids: list[str] | None = None) -> int:
    """Attach cc.Animation."""
    props: dict[str, Any] = {
        "playOnLoad": play_on_load,
        "_clips": [],
    }
    if default_clip_uuid:
        props["_defaultClip"] = {"__uuid__": default_clip_uuid}
    if clip_uuids:
        props["_clips"] = [{"__uuid__": u} for u in clip_uuids]
    return add_component(scene_path, node_id, "cc.Animation", props)


# ----------- particle -----------

def add_particle_system_2d(scene_path: str | Path, node_id: int,
                           duration: float = -1, emission_rate: float = 10,
                           life: float = 1, life_var: float = 0,
                           total_particles: int = 150,
                           start_color: tuple = (255, 255, 255, 255),
                           end_color: tuple = (255, 255, 255, 0),
                           angle: float = 90, angle_var: float = 360,
                           speed: float = 180, speed_var: float = 50,
                           gravity_x: float = 0, gravity_y: float = 0,
                           start_size: float = 50, start_size_var: float = 0,
                           end_size: float = 0, end_size_var: float = 0,
                           emitter_mode: int = 0) -> int:
    """Attach cc.ParticleSystem2D."""
    return add_component(scene_path, node_id, "cc.ParticleSystem2D", {
        "duration": duration,
        "emissionRate": emission_rate,
        "life": life,
        "lifeVar": life_var,
        "totalParticles": total_particles,
        "_startColor": list(start_color),
        "_endColor": list(end_color),
        "angle": angle,
        "angleVar": angle_var,
        "speed": speed,
        "speedVar": speed_var,
        "gravity": [gravity_x, gravity_y],
        "startSize": start_size,
        "startSizeVar": start_size_var,
        "endSize": end_size,
        "endSizeVar": end_size_var,
        "emitterMode": emitter_mode,
        "positionType": 0,
    })


# ----------- camera -----------

def add_camera(scene_path: str | Path, node_id: int,
               projection: int = 0, priority: int = 0,
               ortho_height: float = 320, fov: float = 45,
               near: float = 1, far: float = 2000,
               clear_color: tuple = (0, 0, 0, 255),
               clear_flags: int = 7,
               visibility: int = 41943040) -> int:
    """Attach cc.Camera. projection: 0=ORTHO, 1=PERSPECTIVE.

    Use this for secondary cameras (minimap, split-screen). The default
    camera created by cocos_create_scene has priority=1073741824.
    """
    return add_component(scene_path, node_id, "cc.Camera", {
        "_projection": projection,
        "_priority": priority,
        "_fov": fov,
        "_fovAxis": 0,
        "_orthoHeight": ortho_height,
        "_near": near,
        "_far": far,
        "_color": _color(*clear_color),
        "_depth": 1,
        "_stencil": 0,
        "_clearFlags": clear_flags,
        "_rect": _rect(0, 0, 1, 1),
        "_aperture": 19,
        "_shutter": 7,
        "_iso": 0,
        "_screenScale": 1,
        "_visibility": visibility,
        "_targetTexture": None,
        "_cameraType": -1,
        "_trackingType": 0,
    })


# ----------- mask -----------

def add_mask(scene_path: str | Path, node_id: int,
             mask_type: int = 0, inverted: bool = False,
             segments: int = 64) -> int:
    """Attach cc.Mask. mask_type: 0=RECT, 1=ELLIPSE, 2=GRAPHICS_STENCIL, 3=SPRITE_STENCIL."""
    return add_component(scene_path, node_id, "cc.Mask", {
        "_type": mask_type,
        "_inverted": inverted,
        "_segments": segments,
    })


# ----------- rich text -----------

def add_richtext(scene_path: str | Path, node_id: int,
                 text: str = "<b>Hello</b>",
                 font_size: int = 40,
                 max_width: float = 0,
                 line_height: float = 40,
                 horizontal_align: int = 0) -> int:
    """Attach cc.RichText. Supports <b>, <i>, <color>, <size>, <img> tags."""
    return add_component(scene_path, node_id, "cc.RichText", {
        "_lineHeight": line_height,
        "string": text,
        "fontSize": font_size,
        "maxWidth": max_width,
        "horizontalAlign": horizontal_align,
        "handleTouchEvent": True,
    })


# ----------- 9-slice sprite helper -----------

def add_sliced_sprite(scene_path: str | Path, node_id: int,
                      sprite_frame_uuid: str | None = None,
                      color: tuple = (255, 255, 255, 255)) -> int:
    """Attach cc.Sprite with type=SLICED (9-slice).

    The sprite stretches the center while keeping corners fixed.
    Set border sizes in the spriteFrame meta's borderTop/Bottom/Left/Right.
    """
    s = _load_scene(scene_path)
    obj = _make_sprite(node_id, sprite_frame_uuid, size_mode=0, color=color)
    obj["_type"] = 1  # SLICED
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


# ----------- tiled sprite helper -----------

def add_tiled_sprite(scene_path: str | Path, node_id: int,
                     sprite_frame_uuid: str | None = None,
                     color: tuple = (255, 255, 255, 255)) -> int:
    """Attach cc.Sprite with type=TILED (repeating pattern)."""
    s = _load_scene(scene_path)
    obj = _make_sprite(node_id, sprite_frame_uuid, size_mode=0, color=color)
    obj["_type"] = 2  # TILED
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


# ================================================================
#  Spine / DragonBones skeletal animation
# ================================================================

def add_spine(scene_path: str | Path, node_id: int,
              skeleton_data_uuid: str | None = None,
              default_skin: str = "default",
              default_animation: str = "",
              loop: bool = True,
              premultiplied_alpha: bool = True,
              time_scale: float = 1.0) -> int:
    """Attach sp.Skeleton (Spine skeletal animation component).

    `skeleton_data_uuid` is the UUID of the .json spine data asset.
    Set via cocos_add_spine_data() or cocos_set_uuid_property() later.
    """
    props: dict[str, Any] = {
        "defaultSkin": default_skin,
        "defaultAnimation": default_animation,
        "loop": loop,
        "premultipliedAlpha": premultiplied_alpha,
        "timeScale": time_scale,
        "_preCacheMode": 0,
        "_cacheMode": 0,
    }
    if skeleton_data_uuid:
        props["_N$skeletonData"] = {"__uuid__": skeleton_data_uuid}
    return add_component(scene_path, node_id, "sp.Skeleton", props)


def add_dragonbones(scene_path: str | Path, node_id: int,
                    dragon_asset_uuid: str | None = None,
                    dragon_atlas_asset_uuid: str | None = None,
                    armature_name: str = "",
                    animation_name: str = "",
                    play_times: int = -1,
                    time_scale: float = 1.0) -> int:
    """Attach dragonBones.ArmatureDisplay (DragonBones skeletal animation).

    `dragon_asset_uuid` is the UUID of the DragonBones JSON data.
    `dragon_atlas_asset_uuid` is the UUID of the texture atlas JSON.
    """
    props: dict[str, Any] = {
        "_armatureName": armature_name,
        "_animationName": animation_name,
        "playTimes": play_times,
        "timeScale": time_scale,
    }
    if dragon_asset_uuid:
        props["_N$dragonAsset"] = {"__uuid__": dragon_asset_uuid}
    if dragon_atlas_asset_uuid:
        props["_N$dragonAtlasAsset"] = {"__uuid__": dragon_atlas_asset_uuid}
    return add_component(scene_path, node_id, "dragonBones.ArmatureDisplay", props)


# ================================================================
#  TiledMap
# ================================================================

def add_tiled_map(scene_path: str | Path, node_id: int,
                  tmx_asset_uuid: str | None = None) -> int:
    """Attach cc.TiledMap component.

    `tmx_asset_uuid` is the UUID of the .tmx TiledMap asset.
    Import the .tmx file via cocos_add_tiled_map_asset() first.
    """
    props: dict[str, Any] = {}
    if tmx_asset_uuid:
        props["_tmxAsset"] = {"__uuid__": tmx_asset_uuid}
    return add_component(scene_path, node_id, "cc.TiledMap", props)


def add_tiled_layer(scene_path: str | Path, node_id: int,
                    layer_name: str = "") -> int:
    """Attach cc.TiledLayer. Usually auto-created by TiledMap, but can be
    added manually for custom layer control."""
    return add_component(scene_path, node_id, "cc.TiledLayer", {
        "_layerName": layer_name,
    })


def add_filled_sprite(scene_path: str | Path, node_id: int,
                      sprite_frame_uuid: str | None = None,
                      fill_type: int = 0, fill_center: tuple = (0.5, 0.5),
                      fill_start: float = 0, fill_range: float = 1.0,
                      color: tuple = (255, 255, 255, 255)) -> int:
    """Attach cc.Sprite with type=FILLED (radial/horizontal/vertical fill).

    fill_type: 0=HORIZONTAL, 1=VERTICAL, 2=RADIAL
    fill_start: 0~1 fill starting position
    fill_range: 0~1 fill amount (useful for cooldown timers)
    fill_center: center point for RADIAL fill
    """
    s = _load_scene(scene_path)
    obj = _make_sprite(node_id, sprite_frame_uuid, size_mode=0, color=color)
    obj["_type"] = 3  # FILLED
    obj["_fillType"] = fill_type
    obj["_fillCenter"] = _vec2(*fill_center)
    obj["_fillStart"] = fill_start
    obj["_fillRange"] = fill_range
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


# ----------- UIOpacity (淡入淡出动画必备) -----------

def add_ui_opacity(scene_path: str | Path, node_id: int, opacity: int = 255) -> int:
    """Attach cc.UIOpacity. Controls node transparency (0=invisible, 255=opaque).

    Essential for fade-in/out animations via tween:
      tween(node.getComponent(UIOpacity)).to(0.5, {opacity: 0}).start()
    """
    return add_component(scene_path, node_id, "cc.UIOpacity", {
        "opacity": opacity,
    })


# ----------- BlockInputEvents (弹窗遮罩层必备) -----------

def add_block_input_events(scene_path: str | Path, node_id: int) -> int:
    """Attach cc.BlockInputEvents. Prevents touch/mouse events from passing through.

    Put this on a fullscreen overlay node to block clicks on nodes behind it.
    Typical use: modal dialog backdrop, loading screen.
    """
    return add_component(scene_path, node_id, "cc.BlockInputEvents", {})


# ----------- SafeArea (刘海屏/异形屏适配) -----------

def add_safe_area(scene_path: str | Path, node_id: int) -> int:
    """Attach cc.SafeArea. Auto-adjusts node to fit within the device safe area.

    Essential for mobile games on iPhone (notch) / Android (cutout).
    Usually placed on the root UI node.
    """
    return add_component(scene_path, node_id, "cc.SafeArea", {})


# ----------- PageView -----------

def add_page_view(scene_path: str | Path, node_id: int,
                  content_id: int | None = None,
                  direction: int = 0,
                  scroll_threshold: float = 0.5,
                  page_turning_speed: float = 0.3,
                  indicator_id: int | None = None,
                  auto_page_turning_threshold: float = 100) -> int:
    """Attach cc.PageView (swipeable page container).

    direction: 0=Horizontal, 1=Vertical.
    Used for: tutorials, card galleries, level select screens.
    """
    props: dict = {
        "direction": direction,
        "scrollThreshold": scroll_threshold,
        "pageTurningSpeed": page_turning_speed,
        "autoPageTurningThreshold": auto_page_turning_threshold,
        "inertia": True,
        "elastic": True,
        "bounceDuration": 0.23,
    }
    if content_id is not None:
        props["content"] = {"__id__": content_id}
    if indicator_id is not None:
        props["indicator"] = {"__id__": indicator_id}
    return add_component(scene_path, node_id, "cc.PageView", props)


# ----------- ToggleContainer -----------

def add_toggle_container(scene_path: str | Path, node_id: int,
                         allow_switch_off: bool = False) -> int:
    """Attach cc.ToggleContainer (radio button group).

    Child Toggle nodes are mutually exclusive — only one can be checked at a time.
    Set allow_switch_off=True to allow all unchecked.
    """
    return add_component(scene_path, node_id, "cc.ToggleContainer", {
        "allowSwitchOff": allow_switch_off,
    })


# ----------- MotionStreak -----------

def add_motion_streak(scene_path: str | Path, node_id: int,
                      fade_time: float = 1.0,
                      min_seg: float = 1,
                      stroke: float = 64,
                      color: tuple = (255, 255, 255, 255),
                      fast_mode: bool = False) -> int:
    """Attach cc.MotionStreak (trail/streak effect behind moving objects).

    Used for: sword trails, shooting stars, finger swipe effects.
    """
    return add_component(scene_path, node_id, "cc.MotionStreak", {
        "_fadeTime": fade_time,
        "_minSeg": min_seg,
        "_stroke": stroke,
        "_color": _color(*color),
        "_fastMode": fast_mode,
    })


# ================================================================
#  Scene-globals setters: ambient, skybox, shadows
# ================================================================
#
# Every scene built via create_empty_scene has a SceneGlobals object that
# holds three sub-objects: AmbientInfo, SkyboxInfo, ShadowsInfo. To configure
# lighting after creation you mutate those sub-objects in place — but their
# array indices aren't fixed in user-edited scenes, so we look them up by
# component __type__ rather than hard-coding a position.

def _find_global_info(s: list, type_name: str) -> int | None:
    """Locate a singleton scene-globals component (cc.AmbientInfo etc.) by type."""
    for i, obj in enumerate(s):
        if isinstance(obj, dict) and obj.get("__type__") == type_name:
            return i
    return None


def set_ambient(scene_path: str | Path,
                sky_color: tuple | None = None,
                sky_illum: float | None = None,
                ground_albedo: tuple | None = None) -> dict:
    """Set ambient lighting on the scene's cc.AmbientInfo.

    Each arg is optional — pass None to leave that field unchanged.
      sky_color, ground_albedo: (r, g, b, a) floats 0-1 (NOT 0-255).
      sky_illum: lux value, default 20000 in a fresh scene.

    Returns the updated AmbientInfo dict.
    """
    s = _load_scene(scene_path)
    idx = _find_global_info(s, "cc.AmbientInfo")
    if idx is None:
        raise ValueError("scene has no cc.AmbientInfo (was it created via create_empty_scene?)")
    info = s[idx]
    if sky_color is not None:
        info["_skyColor"] = _vec4(*sky_color)
        info["_skyColorLDR"] = _vec4(*sky_color)
        info["_skyColorHDR"] = _vec4(*sky_color)
    if sky_illum is not None:
        info["_skyIllum"] = sky_illum
        info["_skyIllumHDR"] = sky_illum
    if ground_albedo is not None:
        info["_groundAlbedo"] = _vec4(*ground_albedo)
        info["_groundAlbedoLDR"] = _vec4(*ground_albedo)
        info["_groundAlbedoHDR"] = _vec4(*ground_albedo)
    _save_scene(scene_path, s)
    return info


def set_skybox(scene_path: str | Path,
               enabled: bool | None = None,
               envmap_uuid: str | None = None,
               use_hdr: bool | None = None,
               env_lighting_type: int | None = None) -> dict:
    """Set skybox on the scene's cc.SkyboxInfo.

      env_lighting_type: 0=HEMISPHERE_DIFFUSE, 1=AUTOGEN_HEMISPHERE_DIFFUSE, 2=DIFFUSEMAP_WITH_REFLECTION.
      envmap_uuid: cc.TextureCube uuid; pass empty string "" to clear.

    Each arg is optional. Returns the updated SkyboxInfo dict.
    """
    s = _load_scene(scene_path)
    idx = _find_global_info(s, "cc.SkyboxInfo")
    if idx is None:
        raise ValueError("scene has no cc.SkyboxInfo")
    info = s[idx]
    if enabled is not None:
        info["_enabled"] = enabled
    if envmap_uuid is not None:
        ref = {"__uuid__": envmap_uuid, "__expectedType__": "cc.TextureCube"} if envmap_uuid else None
        info["_envmap"] = ref
        info["_envmapHDR"] = ref
        info["_envmapLDR"] = ref
    if use_hdr is not None:
        info["_useHDR"] = use_hdr
    if env_lighting_type is not None:
        info["_envLightingType"] = env_lighting_type
    _save_scene(scene_path, s)
    return info


def set_shadows(scene_path: str | Path,
                enabled: bool | None = None,
                normal: tuple | None = None,
                distance: float | None = None,
                color: tuple | None = None) -> dict:
    """Set planar shadows on the scene's cc.ShadowsInfo.

      normal: (x, y, z) shadow plane normal, default (0, 1, 0) for ground.
      distance: signed offset along normal from origin.
      color: (r, g, b, a) ints 0-255.

    Each arg is optional. Returns the updated ShadowsInfo dict.
    """
    s = _load_scene(scene_path)
    idx = _find_global_info(s, "cc.ShadowsInfo")
    if idx is None:
        raise ValueError("scene has no cc.ShadowsInfo")
    info = s[idx]
    if enabled is not None:
        info["_enabled"] = enabled
    if normal is not None:
        info["_normal"] = _vec3(*normal)
    if distance is not None:
        info["_distance"] = distance
    if color is not None:
        info["_shadowColor"] = _color(*color)
    _save_scene(scene_path, s)
    return info


# ================================================================
#  2D physics joints (cc.*Joint2D)
# ================================================================
#
# All cc.*Joint2D components share a base set of fields:
#   - node:           ref to the node carrying the joint (and its RigidBody2D)
#   - _connectedBody: ref to the OTHER body's RigidBody2D component (optional;
#                     None means joint anchors to the world)
#   - _collideConnected: whether the two bodies still collide with each other
# Each joint then layers its own anchor / motor / limit / spring fields.
# Both nodes must already have a cc.RigidBody2D attached.

def _make_joint2d_base(node_idx: int, type_name: str, prefix: str,
                       connected_body_id: int | None,
                       collide_connected: bool) -> dict:
    """Common joint object skeleton."""
    return {
        "__type__": type_name,
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_connectedBody": _ref(connected_body_id) if connected_body_id is not None else None,
        "_collideConnected": collide_connected,
        "_id": _nid(prefix),
    }


def _attach_joint(scene_path, node_id: int, joint_obj: dict) -> int:
    s = _load_scene(scene_path)
    cid = _attach_component(s, node_id, joint_obj)
    _save_scene(scene_path, s)
    return cid


def add_distance_joint2d(scene_path: str | Path, node_id: int,
                         connected_body_id: int | None = None,
                         anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                         distance: float = 1.0, auto_calc_distance: bool = True,
                         frequency: float = 0.0, damping_ratio: float = 0.0,
                         collide_connected: bool = False) -> int:
    """Attach cc.DistanceJoint2D — keeps two bodies a fixed distance apart."""
    obj = _make_joint2d_base(node_id, "cc.DistanceJoint2D", "dj2", connected_body_id, collide_connected)
    obj.update({
        "_anchor": _vec2(*anchor),
        "_connectedAnchor": _vec2(*connected_anchor),
        "_distance": distance,
        "_autoCalcDistance": auto_calc_distance,
        "_frequency": frequency,
        "_dampingRatio": damping_ratio,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_hinge_joint2d(scene_path: str | Path, node_id: int,
                      connected_body_id: int | None = None,
                      anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                      enable_motor: bool = False, motor_speed: float = 0.0,
                      max_motor_torque: float = 1000.0,
                      enable_limit: bool = False,
                      lower_angle: float = 0.0, upper_angle: float = 0.0,
                      collide_connected: bool = False) -> int:
    """Attach cc.HingeJoint2D — rotates around a shared anchor (door, wheel)."""
    obj = _make_joint2d_base(node_id, "cc.HingeJoint2D", "hj2", connected_body_id, collide_connected)
    obj.update({
        "_anchor": _vec2(*anchor),
        "_connectedAnchor": _vec2(*connected_anchor),
        "_enableMotor": enable_motor,
        "_motorSpeed": motor_speed,
        "_maxMotorTorque": max_motor_torque,
        "_enableLimit": enable_limit,
        "_lowerAngle": lower_angle,
        "_upperAngle": upper_angle,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_spring_joint2d(scene_path: str | Path, node_id: int,
                       connected_body_id: int | None = None,
                       anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                       distance: float = 1.0, auto_calc_distance: bool = True,
                       frequency: float = 5.0, damping_ratio: float = 0.7,
                       collide_connected: bool = False) -> int:
    """Attach cc.SpringJoint2D — soft-springy distance constraint (suspension, ropes)."""
    obj = _make_joint2d_base(node_id, "cc.SpringJoint2D", "sj2", connected_body_id, collide_connected)
    obj.update({
        "_anchor": _vec2(*anchor),
        "_connectedAnchor": _vec2(*connected_anchor),
        "_distance": distance,
        "_autoCalcDistance": auto_calc_distance,
        "_frequency": frequency,
        "_dampingRatio": damping_ratio,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_mouse_joint2d(scene_path: str | Path, node_id: int,
                      max_force: float = 1000.0,
                      frequency: float = 5.0, damping_ratio: float = 0.7,
                      target: tuple = (0, 0)) -> int:
    """Attach cc.MouseJoint2D — drag-to-target constraint, used for picking up bodies."""
    # MouseJoint doesn't use connectedBody/collideConnected; build skeleton manually.
    obj = {
        "__type__": "cc.MouseJoint2D",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("mj2"),
        "_maxForce": max_force,
        "_frequency": frequency,
        "_dampingRatio": damping_ratio,
        "_target": _vec2(*target),
    }
    return _attach_joint(scene_path, node_id, obj)


def add_slider_joint2d(scene_path: str | Path, node_id: int,
                       connected_body_id: int | None = None,
                       anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                       angle: float = 0.0,
                       enable_motor: bool = False, motor_speed: float = 0.0,
                       max_motor_force: float = 1000.0,
                       enable_limit: bool = False,
                       lower_limit: float = 0.0, upper_limit: float = 0.0,
                       collide_connected: bool = False) -> int:
    """Attach cc.SliderJoint2D — translates along an axis (elevator rails, pistons)."""
    obj = _make_joint2d_base(node_id, "cc.SliderJoint2D", "sl2", connected_body_id, collide_connected)
    obj.update({
        "_anchor": _vec2(*anchor),
        "_connectedAnchor": _vec2(*connected_anchor),
        "_angle": angle,
        "_enableMotor": enable_motor,
        "_motorSpeed": motor_speed,
        "_maxMotorForce": max_motor_force,
        "_enableLimit": enable_limit,
        "_lowerLimit": lower_limit,
        "_upperLimit": upper_limit,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_wheel_joint2d(scene_path: str | Path, node_id: int,
                      connected_body_id: int | None = None,
                      anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                      angle: float = 90.0,
                      enable_motor: bool = False, motor_speed: float = 0.0,
                      max_motor_torque: float = 1000.0,
                      frequency: float = 5.0, damping_ratio: float = 0.7,
                      collide_connected: bool = False) -> int:
    """Attach cc.WheelJoint2D — wheel + axle for vehicles (combines slide + spring + motor)."""
    obj = _make_joint2d_base(node_id, "cc.WheelJoint2D", "wj2", connected_body_id, collide_connected)
    obj.update({
        "_anchor": _vec2(*anchor),
        "_connectedAnchor": _vec2(*connected_anchor),
        "_angle": angle,
        "_enableMotor": enable_motor,
        "_motorSpeed": motor_speed,
        "_maxMotorTorque": max_motor_torque,
        "_frequency": frequency,
        "_dampingRatio": damping_ratio,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_weld_joint2d(scene_path: str | Path, node_id: int,
                     connected_body_id: int | None = None,
                     anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                     angle: float = 0.0,
                     frequency: float = 5.0, damping_ratio: float = 0.7,
                     collide_connected: bool = False) -> int:
    """Attach cc.WeldJoint2D — rigidly fuses two bodies (breakable structures)."""
    obj = _make_joint2d_base(node_id, "cc.WeldJoint2D", "wd2", connected_body_id, collide_connected)
    obj.update({
        "_anchor": _vec2(*anchor),
        "_connectedAnchor": _vec2(*connected_anchor),
        "_angle": angle,
        "_frequency": frequency,
        "_dampingRatio": damping_ratio,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_relative_joint2d(scene_path: str | Path, node_id: int,
                         connected_body_id: int | None = None,
                         max_force: float = 1000.0, max_torque: float = 1000.0,
                         correction_factor: float = 0.3,
                         auto_calc_offset: bool = True,
                         linear_offset: tuple = (0, 0), angular_offset: float = 0.0,
                         collide_connected: bool = False) -> int:
    """Attach cc.RelativeJoint2D — keeps a relative position+angle, useful for 'attach' effects."""
    obj = _make_joint2d_base(node_id, "cc.RelativeJoint2D", "rj2", connected_body_id, collide_connected)
    obj.update({
        "_maxForce": max_force,
        "_maxTorque": max_torque,
        "_correctionFactor": correction_factor,
        "_autoCalcOffset": auto_calc_offset,
        "_linearOffset": _vec2(*linear_offset),
        "_angularOffset": angular_offset,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_motor_joint2d(scene_path: str | Path, node_id: int,
                      connected_body_id: int | None = None,
                      max_force: float = 1000.0, max_torque: float = 1000.0,
                      correction_factor: float = 0.3,
                      linear_offset: tuple = (0, 0), angular_offset: float = 0.0,
                      collide_connected: bool = False) -> int:
    """Attach cc.MotorJoint2D — drives one body to follow another's position+angle."""
    obj = _make_joint2d_base(node_id, "cc.MotorJoint2D", "mt2", connected_body_id, collide_connected)
    obj.update({
        "_maxForce": max_force,
        "_maxTorque": max_torque,
        "_correctionFactor": correction_factor,
        "_linearOffset": _vec2(*linear_offset),
        "_angularOffset": angular_offset,
    })
    return _attach_joint(scene_path, node_id, obj)


# ================================================================
#  cc.VideoPlayer
# ================================================================

def add_video_player(scene_path: str | Path, node_id: int,
                     resource_type: int = 1,
                     remote_url: str = "",
                     clip_uuid: str | None = None,
                     play_on_awake: bool = True,
                     volume: float = 1.0,
                     mute: bool = False,
                     loop: bool = False,
                     keep_aspect_ratio: bool = True,
                     full_screen_on_awake: bool = False,
                     stay_on_bottom: bool = False) -> int:
    """Attach cc.VideoPlayer — plays mp4 from a local cc.VideoClip asset or a remote URL.

    resource_type: 0=REMOTE (use remote_url), 1=LOCAL (use clip_uuid).

    Common uses: cinematic intro, in-game cutscenes, rewarded video ads.
    Note: WeChat mini-game uses a native overlay; stay_on_bottom + the
    full screen flag affect platform-specific rendering behavior.
    """
    return add_component(scene_path, node_id, "cc.VideoPlayer", {
        "_resourceType": resource_type,
        "_remoteURL": remote_url,
        "_clip": {"__uuid__": clip_uuid, "__expectedType__": "cc.VideoClip"} if clip_uuid else None,
        "_playOnAwake": play_on_awake,
        "_volume": volume,
        "_mute": mute,
        "_loop": loop,
        "_keepAspectRatio": keep_aspect_ratio,
        "_fullScreenOnAwake": full_screen_on_awake,
        "_stayOnBottom": stay_on_bottom,
    })


# ================================================================
#  Prefab instantiation: drop a .prefab into a scene as live nodes
# ================================================================
#
# A .prefab file is a JSON array shaped like:
#   [0] cc.Prefab         ← asset wrapper, holds optimization policy
#   [1] cc.Node (root)    ← the real root node
#   [2] cc.PrefabInfo     ← fileId metadata for the root
#   [3..N] children/components, all referencing each other via __id__
#
# Instantiating means:
#   * skip the [0] cc.Prefab wrapper (it's asset metadata, not a scene object)
#   * deep-copy [1..N] and append to the target scene array
#   * shift every __id__ reference inside the cloned region by
#     (scene_len_before_append - 1)   ← -1 because [0] is dropped
#   * re-mint _id strings (avoid collisions with existing scene _ids)
#   * give each cc.PrefabInfo a fresh fileId so multiple instances don't alias
#   * point the cloned root's _parent at the user-supplied parent_id
#   * append the cloned root's new index to parent._children
#
# Limitations of this minimal implementation:
#   * Treats prefabs as "unlinked" — edits to the source .prefab won't
#     propagate. Cocos's true linked-instance model uses CompPrefabInfo +
#     instance overrides; supporting it is a separate (much larger) feature.
#   * Doesn't validate that nested prefabs are themselves resolvable.

def _shift_id_refs(obj, delta: int) -> None:
    """In-place: add `delta` to every {"__id__": N} integer reference."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "__id__" and isinstance(v, int):
                obj[k] = v + delta
            else:
                _shift_id_refs(v, delta)
    elif isinstance(obj, list):
        for item in obj:
            _shift_id_refs(item, delta)


def instantiate_prefab(scene_path: str | Path, parent_id: int,
                       prefab_path: str | Path,
                       name: str | None = None,
                       lpos: tuple | None = None,
                       lscale: tuple | None = None) -> int:
    """Drop a .prefab file into a scene as a child of parent_id.

    Returns the new root node's array index in the scene.

    Parameters:
      scene_path: target .scene file
      parent_id: array index of the cc.Node to parent the instance under
      prefab_path: source .prefab file (read-only)
      name: optional override for the root node's _name
      lpos: optional (x, y, z) overriding root local position
      lscale: optional (x, y, z) overriding root local scale

    The cloned subtree gets fresh _id values and PrefabInfo.fileId values
    so multiple instantiations of the same prefab don't collide.
    """
    s = _load_scene(scene_path)
    if parent_id < 0 or parent_id >= len(s) or s[parent_id].get("__type__") != "cc.Node":
        raise ValueError(f"parent_id {parent_id} is not a cc.Node in this scene")

    with open(prefab_path) as f:
        p_data = json.load(f)
    if not p_data or p_data[0].get("__type__") != "cc.Prefab":
        raise ValueError(f"{prefab_path} is not a valid prefab (missing cc.Prefab head)")

    # [0] is the asset wrapper — drop it. The remaining [1..N] become real scene objects.
    cloned = json.loads(json.dumps(p_data[1:]))  # deep copy

    # Old prefab index i (1..N) maps to new scene index (i - 1 + len(s)).
    # i.e. delta = len(s) - 1.
    delta = len(s) - 1
    for obj in cloned:
        _shift_id_refs(obj, delta)

    # Refresh _id (uniqueness within scene) and PrefabInfo.fileId (uniqueness across instances)
    for obj in cloned:
        if not isinstance(obj, dict):
            continue
        if "_id" in obj:
            obj["_id"] = _nid("ins")
        if obj.get("__type__") == "cc.PrefabInfo":
            obj["fileId"] = new_uuid()

    # Reparent root: prefab[1] is now cloned[0], lives at index len(s)
    root_new_idx = len(s)
    root = cloned[0]
    if root.get("__type__") != "cc.Node":
        raise ValueError(f"prefab root at [1] is {root.get('__type__')}, expected cc.Node")
    root["_parent"] = _ref(parent_id)
    if name is not None:
        root["_name"] = name
    if lpos is not None:
        root["_lpos"] = _vec3(*lpos)
    if lscale is not None:
        root["_lscale"] = _vec3(*lscale)

    s.extend(cloned)
    s[parent_id].setdefault("_children", []).append(_ref(root_new_idx))

    _save_scene(scene_path, s)
    return root_new_idx

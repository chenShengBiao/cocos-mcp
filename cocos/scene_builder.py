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

from .meta_util import scene_meta, prefab_meta
from .uuid_util import new_uuid

# Cocos Creator built-in layer bitmasks (from default layer config)
LAYER_UI_2D = 33554432  # bit 25
LAYER_DEFAULT = 1073741824  # bit 30 (used by Camera)


# ----------- primitive value helpers -----------

def _vec3(x: float = 0, y: float = 0, z: float = 0) -> dict:
    return {"__type__": "cc.Vec3", "x": x, "y": y, "z": z}


def _quat(x: float = 0, y: float = 0, z: float = 0, w: float = 1) -> dict:
    return {"__type__": "cc.Quat", "x": x, "y": y, "z": z, "w": w}


def _vec2(x: float = 0, y: float = 0) -> dict:
    return {"__type__": "cc.Vec2", "x": x, "y": y}


def _vec4(x: float = 0, y: float = 0, z: float = 0, w: float = 0) -> dict:
    return {"__type__": "cc.Vec4", "x": x, "y": y, "z": z, "w": w}


def _size(w: float = 0, h: float = 0) -> dict:
    return {"__type__": "cc.Size", "width": w, "height": h}


def _color(r: int = 255, g: int = 255, b: int = 255, a: int = 255) -> dict:
    return {"__type__": "cc.Color", "r": r, "g": g, "b": b, "a": a}


def _rect(x: float = 0, y: float = 0, w: float = 1, h: float = 1) -> dict:
    return {"__type__": "cc.Rect", "x": x, "y": y, "width": w, "height": h}


def _ref(idx: int) -> dict:
    return {"__id__": idx}


_id_counter = [0]
def _nid(prefix: str = "n") -> str:
    """Generate a 22-char Cocos node `_id` string (just needs to be unique)."""
    _id_counter[0] += 1
    s = f"{prefix}{_id_counter[0]:06d}xxxxxxxxxxxxxxxx"
    return s[:22]


# ----------- factory: low-level object dicts -----------

def _make_node(name: str, parent_idx: int | None, lpos=(0, 0, 0), lscale=(1, 1, 1),
               layer: int = LAYER_UI_2D, active: bool = True) -> dict:
    return {
        "__type__": "cc.Node",
        "_name": name,
        "_objFlags": 0,
        "_parent": _ref(parent_idx) if parent_idx is not None else None,
        "_children": [],
        "_active": active,
        "_components": [],
        "_prefab": None,
        "_lpos": _vec3(*lpos),
        "_lrot": _quat(),
        "_lscale": _vec3(*lscale),
        "_layer": layer,
        "_euler": _vec3(),
        "_id": _nid(name[:6] if name else "node"),
    }


def _make_uitransform(node_idx: int, w: float, h: float, ax: float = 0.5, ay: float = 0.5) -> dict:
    return {
        "__type__": "cc.UITransform",
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_priority": 0,
        "_contentSize": _size(w, h),
        "_anchorPoint": _vec2(ax, ay),
        "_id": _nid("uit"),
    }


def _make_camera(node_idx: int, ortho_height: float = 320, clear_color=(0, 0, 0, 0)) -> dict:
    return {
        "__type__": "cc.Camera",
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_projection": 0,
        "_priority": 1073741824,
        "_fov": 45,
        "_fovAxis": 0,
        "_orthoHeight": ortho_height,
        "_near": 1,
        "_far": 2000,
        "_color": _color(*clear_color),
        "_depth": 1,
        "_stencil": 0,
        "_clearFlags": 7,
        "_rect": _rect(0, 0, 1, 1),
        "_aperture": 19,
        "_shutter": 7,
        "_iso": 0,
        "_screenScale": 1,
        "_visibility": 41943040,
        "_targetTexture": None,
        "_cameraType": -1,
        "_trackingType": 0,
        "_id": _nid("cam"),
    }


def _make_canvas(node_idx: int, camera_cmp_idx: int) -> dict:
    return {
        "__type__": "cc.Canvas",
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_cameraComponent": _ref(camera_cmp_idx),
        "_alignCanvasWithScreen": True,
        "_id": _nid("cvs"),
    }


def _make_widget(node_idx: int, align_flags: int = 45, target_idx: int | None = None) -> dict:
    return {
        "__type__": "cc.Widget",
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_alignFlags": align_flags,
        "_target": _ref(target_idx) if target_idx is not None else None,
        "_left": 0,
        "_right": 0,
        "_top": 0,
        "_bottom": 0,
        "_horizontalCenter": 0,
        "_verticalCenter": 0,
        "_isAbsLeft": True,
        "_isAbsRight": True,
        "_isAbsTop": True,
        "_isAbsBottom": True,
        "_isAbsHorizontalCenter": True,
        "_isAbsVerticalCenter": True,
        "_originalWidth": 0,
        "_originalHeight": 0,
        "_alignMode": 2,
        "_lockFlags": 0,
        "_id": _nid("wgt"),
    }


def _make_sprite(node_idx: int, sprite_frame_uuid: str | None, size_mode: int = 0, color=(255, 255, 255, 255)) -> dict:
    """size_mode: 0=CUSTOM, 1=TRIMMED, 2=RAW"""
    return {
        "__type__": "cc.Sprite",
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_customMaterial": None,
        "_srcBlendFactor": 2,
        "_dstBlendFactor": 4,
        "_color": _color(*color),
        "_spriteFrame": {"__uuid__": sprite_frame_uuid} if sprite_frame_uuid else None,
        "_type": 0,
        "_fillType": 0,
        "_sizeMode": size_mode,
        "_fillCenter": _vec2(0, 0),
        "_fillStart": 0,
        "_fillRange": 0,
        "_isTrimmedMode": True,
        "_useGrayscale": False,
        "_atlas": None,
        "_id": _nid("spr"),
    }


def _make_label(node_idx: int, text: str, font_size: int = 40, color=(255, 255, 255, 255),
                h_align: int = 1, v_align: int = 1) -> dict:
    return {
        "__type__": "cc.Label",
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_customMaterial": None,
        "_srcBlendFactor": 2,
        "_dstBlendFactor": 4,
        "_color": _color(*color),
        "_useOriginalSize": False,
        "_string": text,
        "_horizontalAlign": h_align,
        "_verticalAlign": v_align,
        "_actualFontSize": font_size,
        "_fontSize": font_size,
        "_fontFamily": "Arial",
        "_lineHeight": font_size,
        "_overflow": 0,
        "_enableWrapText": False,
        "_font": None,
        "_isSystemFontUsed": True,
        "_spacingX": 0,
        "_isItalic": False,
        "_isBold": False,
        "_isUnderline": False,
        "_underlineHeight": 2,
        "_cacheMode": 0,
        "_enableOutline": True,
        "_outlineColor": _color(0, 0, 0, 255),
        "_outlineWidth": 3,
        "_enableShadow": False,
        "_shadowColor": _color(0, 0, 0, 255),
        "_shadowOffset": _vec2(2, 2),
        "_shadowBlur": 2,
        "_id": _nid("lbl"),
    }


def _make_graphics(node_idx: int) -> dict:
    return {
        "__type__": "cc.Graphics",
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_customMaterial": None,
        "_srcBlendFactor": 2,
        "_dstBlendFactor": 4,
        "_color": _color(255, 255, 255, 255),
        "_lineWidth": 2,
        "_strokeColor": _color(0, 0, 0, 255),
        "_lineJoin": 2,
        "_lineCap": 0,
        "_fillColor": _color(255, 255, 255, 255),
        "_miterLimit": 10,
        "_id": _nid("gfx"),
    }


def _make_script_component(script_uuid_compressed: str, node_idx: int, props: dict | None = None) -> dict:
    obj = {
        "__type__": script_uuid_compressed,
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        "_id": _nid("scr"),
    }
    if props:
        # Convert any {"__id__": N} hints already passed
        obj.update(props)
    return obj


# ----------- scene-globals helpers -----------

def _make_ambient_info() -> dict:
    return {
        "__type__": "cc.AmbientInfo",
        "_skyColor": _vec4(0.2, 0.5019607843137255, 0.8, 0.520833125),
        "_skyIllum": 20000,
        "_groundAlbedo": _vec4(0.2, 0.2, 0.2, 1),
        "_skyColorLDR": _vec4(0.2, 0.5019607843137255, 0.8, 0.520833125),
        "_skyColorHDR": _vec4(0.2, 0.5019607843137255, 0.8, 0.520833125),
        "_groundAlbedoLDR": _vec4(0.2, 0.2, 0.2, 1),
        "_groundAlbedoHDR": _vec4(0.2, 0.2, 0.2, 1),
        "_skyIllumLDR": 0.78125,
        "_skyIllumHDR": 20000,
    }


def _make_skybox_info() -> dict:
    return {
        "__type__": "cc.SkyboxInfo",
        "_envmap": None,
        "_enabled": False,
        "_useHDR": True,
        "_envmapLDR": None,
        "_envmapHDR": None,
        "_diffuseMapLDR": None,
        "_diffuseMapHDR": None,
        "_envLightingType": 0,
    }


def _make_shadows_info() -> dict:
    return {
        "__type__": "cc.ShadowsInfo",
        "_enabled": False,
        "_normal": _vec3(0, 1, 0),
        "_distance": 0,
        "_shadowColor": _color(0, 0, 0, 76),
    }


# ----------- read / write -----------

def _load_scene(scene_path: str | Path) -> list:
    with open(scene_path) as f:
        return json.load(f)


def _save_scene(scene_path: str | Path, scene: list) -> None:
    with open(scene_path, "w") as f:
        json.dump(scene, f, indent=2)


# ----------- public API -----------

def create_empty_scene(scene_path: str | Path, scene_uuid: str | None = None,
                       canvas_width: int = 960, canvas_height: int = 640,
                       clear_color: tuple = (135, 206, 235, 255)) -> dict:
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
    from .meta_util import write_meta
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


# Components that require UITransform to render. If attaching one of these
# and the node doesn't already have a UITransform, auto-add one.
_UI_RENDER_TYPES = frozenset({
    "cc.Sprite", "cc.Label", "cc.Graphics", "cc.RichText", "cc.Mask",
    "cc.ParticleSystem2D", "sp.Skeleton", "dragonBones.ArmatureDisplay",
})


def _has_uitransform(s: list, node_id: int) -> bool:
    for comp_ref in s[node_id].get("_components", []):
        cid = comp_ref.get("__id__")
        if cid is not None and cid < len(s) and s[cid].get("__type__") == "cc.UITransform":
            return True
    return False


def _ensure_uitransform(s: list, node_id: int) -> None:
    """Auto-add a default UITransform if the node doesn't have one."""
    if not _has_uitransform(s, node_id):
        uit = _make_uitransform(node_id, 100, 100)
        s.append(uit)
        uit_id = len(s) - 1
        s[node_id].setdefault("_components", []).insert(0, _ref(uit_id))


def _attach_component(s: list, node_id: int, comp_obj: dict) -> int:
    if s[node_id].get("__type__") != "cc.Node":
        raise ValueError(f"node_id {node_id} is not a cc.Node")
    # Auto-add UITransform for UI render components
    comp_type = comp_obj.get("__type__", "")
    if comp_type in _UI_RENDER_TYPES:
        _ensure_uitransform(s, node_id)
    s.append(comp_obj)
    new_id = len(s) - 1
    s[node_id].setdefault("_components", []).append(_ref(new_id))
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
              color: tuple = (255, 255, 255, 255), h_align: int = 1, v_align: int = 1) -> int:
    s = _load_scene(scene_path)
    cid = _attach_component(s, node_id, _make_label(node_id, text, font_size, color, h_align, v_align))
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
    `props` lets you set @property fields. References should be passed as
    plain ints (node/component ids) and will be wrapped automatically.
    """
    s = _load_scene(scene_path)
    if props:
        wrapped: dict[str, Any] = {}
        for k, v in props.items():
            if isinstance(v, int) and not isinstance(v, bool):
                # Heuristic: an int property is interpreted as a node/component
                # ref. Cocos numeric props that aren't refs should be passed
                # as float (e.g. 1.0).
                wrapped[k] = _ref(v)
            else:
                wrapped[k] = v
        props = wrapped
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


def validate_scene(scene_path: str | Path) -> dict:
    """Sanity-check a scene file: ref ranges, type tags, parent linkage."""
    s = _load_scene(scene_path)
    issues = []
    n = len(s)

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

    objects = []

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

    from .meta_util import write_meta
    write_meta(prefab_path, prefab_meta(uuid=prefab_uuid, sync_node_name=root_name))

    return {
        "prefab_path": str(prefab_path),
        "prefab_uuid": prefab_uuid,
        "root_node_id": root_idx,
    }


# ================================================================
#  P0 extensions: generic component, physics, UI, audio, animation
# ================================================================

# ----------- auto-wrap composite values -----------

def _auto_wrap_value(key: str, val: Any) -> Any:
    """Heuristic coercion for scene-file property values.

    Rules (applied in order):
      * dict with `__type__`, `__id__`, or `__uuid__` → passthrough
      * list len 3 → cc.Vec3(x,y,z)
      * list len 4 + key contains "color" → cc.Color(r,g,b,a)
      * list len 4 otherwise → cc.Vec4
      * list len 2 + key contains "size" → cc.Size(w,h)
      * list len 2 otherwise → cc.Vec2(x,y)
      * int (not bool) → {__id__: N} (node/component ref)
      * everything else → passthrough
    """
    if isinstance(val, dict):
        return val  # caller already structured it
    if isinstance(val, list):
        if len(val) == 3:
            return _vec3(*val)
        if len(val) == 4:
            if "color" in key.lower() or "Color" in key:
                return _color(*[int(v) for v in val])
            return _vec4(*val)
        if len(val) == 2:
            if "size" in key.lower() or "Size" in key:
                return _size(*val)
            return _vec2(*val)
        return val
    if isinstance(val, int) and not isinstance(val, bool):
        return _ref(val)
    return val


def _wrap_props(props: dict | None) -> dict:
    if not props:
        return {}
    return {k: _auto_wrap_value(k, v) for k, v in props.items()}


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
        props["_N$barSprite"] = bar_sprite_id  # int → auto ref
    return add_component(scene_path, node_id, "cc.ProgressBar", props)


def add_scroll_view(scene_path: str | Path, node_id: int,
                    content_id: int | None = None,
                    horizontal: bool = False, vertical: bool = True,
                    inertia: bool = True, brake: float = 0.75,
                    elastic: bool = True, bounce_duration: float = 0.23) -> int:
    """Attach cc.ScrollView."""
    props: dict[str, Any] = {
        "horizontal": horizontal,
        "vertical": vertical,
        "inertia": inertia,
        "brake": brake,
        "elastic": elastic,
        "bounceDuration": bounce_duration,
    }
    if content_id is not None:
        props["content"] = content_id  # int → auto ref
    return add_component(scene_path, node_id, "cc.ScrollView", props)


def add_toggle(scene_path: str | Path, node_id: int,
               is_checked: bool = False, transition: int = 2) -> int:
    """Attach cc.Toggle."""
    return add_component(scene_path, node_id, "cc.Toggle", {
        "isChecked": is_checked,
        "transition": transition,
        "_interactable": True,
    })


def add_editbox(scene_path: str | Path, node_id: int,
                placeholder: str = "Enter text...",
                max_length: int = -1, input_mode: int = 6,
                return_type: int = 0) -> int:
    """Attach cc.EditBox. input_mode: 0=ANY, 6=SINGLE_LINE, ..."""
    return add_component(scene_path, node_id, "cc.EditBox", {
        "placeholder": placeholder,
        "maxLength": max_length,
        "inputMode": input_mode,
        "returnType": return_type,
        "_string": "",
    })


def add_slider(scene_path: str | Path, node_id: int,
               direction: int = 0, progress: float = 0.5) -> int:
    """Attach cc.Slider. direction: 0=Horizontal, 1=Vertical."""
    return add_component(scene_path, node_id, "cc.Slider", {
        "direction": direction,
        "progress": progress,
    })


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
#  Batch operations (single file read/write for multiple mutations)
# ================================================================

def batch_ops(scene_path: str | Path, operations: list[dict]) -> dict:
    """Execute multiple scene operations in one file read/write cycle.

    Supports $N back-references: if an op returns an int (node/component id),
    later ops can reference it as "$0", "$1", etc.
    """
    s = _load_scene(scene_path)
    results = []

    def resolve(val):
        """Replace "$N" strings with the result of op N."""
        if isinstance(val, str) and val.startswith("$") and val[1:].isdigit():
            idx = int(val[1:])
            if idx < len(results):
                return results[idx]
        return val

    def resolve_dict(d: dict) -> dict:
        return {k: resolve(v) for k, v in d.items()}

    for i, raw_op in enumerate(operations):
        op = resolve_dict(raw_op)
        action = op.get("op", "")
        try:
            if action == "add_node":
                node = _make_node(
                    op.get("name", f"Node_{i}"),
                    op.get("parent_id", 2),
                    lpos=(op.get("pos_x", 0), op.get("pos_y", 0), op.get("pos_z", 0)),
                    layer=op.get("layer", LAYER_UI_2D),
                    active=op.get("active", True),
                )
                s.append(node)
                new_id = len(s) - 1
                parent = s[op.get("parent_id", 2)]
                children = parent.setdefault("_children", [])
                si = op.get("sibling_index", -1)
                if si < 0 or si >= len(children):
                    children.append(_ref(new_id))
                else:
                    children.insert(si, _ref(new_id))
                results.append(new_id)

            elif action == "add_uitransform":
                nid = op["node_id"]
                cid = _attach_component(s, nid, _make_uitransform(
                    nid, op.get("width", 100), op.get("height", 100),
                    op.get("anchor_x", 0.5), op.get("anchor_y", 0.5)))
                results.append(cid)

            elif action == "add_label":
                nid = op["node_id"]
                color = (op.get("color_r", 255), op.get("color_g", 255),
                         op.get("color_b", 255), op.get("color_a", 255))
                cid = _attach_component(s, nid, _make_label(
                    nid, op.get("text", ""), op.get("font_size", 40), color))
                results.append(cid)

            elif action == "add_sprite":
                nid = op["node_id"]
                cid = _attach_component(s, nid, _make_sprite(
                    nid, op.get("sprite_frame_uuid"), op.get("size_mode", 0)))
                results.append(cid)

            elif action == "add_graphics":
                nid = op["node_id"]
                cid = _attach_component(s, nid, _make_graphics(nid))
                results.append(cid)

            elif action == "add_component":
                nid = op["node_id"]
                obj: dict[str, Any] = {
                    "__type__": op["type_name"],
                    "_name": "", "_objFlags": 0,
                    "node": _ref(nid), "_enabled": True,
                    "__prefab": None, "_id": _nid("cmp"),
                }
                obj.update(_wrap_props(op.get("props") or {}))
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_rigidbody2d":
                nid = op["node_id"]
                obj: dict[str, Any] = {
                    "__type__": "cc.RigidBody2D", "_name": "", "_objFlags": 0,
                    "node": _ref(nid), "_enabled": True, "__prefab": None,
                    "_id": _nid("rb2"),
                    "enabledContactListener": True,
                    "type": op.get("body_type", 2),
                    "gravityScale": op.get("gravity_scale", 1.0),
                    "linearDamping": op.get("linear_damping", 0.0),
                    "angularDamping": op.get("angular_damping", 0.0),
                    "fixedRotation": op.get("fixed_rotation", False),
                    "bullet": op.get("bullet", False),
                    "allowSleep": True,
                    "awakeOnLoad": op.get("awake_on_load", True),
                    "linearVelocity": _vec2(0, 0),
                    "angularVelocity": 0.0,
                }
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_box_collider2d":
                nid = op["node_id"]
                obj = {
                    "__type__": "cc.BoxCollider2D", "_name": "", "_objFlags": 0,
                    "node": _ref(nid), "_enabled": True, "__prefab": None,
                    "_id": _nid("bc2"),
                    "tag": op.get("tag", 0),
                    "_density": op.get("density", 1.0),
                    "_sensor": op.get("is_sensor", False),
                    "_friction": op.get("friction", 0.2),
                    "_restitution": op.get("restitution", 0.0),
                    "_size": _size(op.get("width", 100), op.get("height", 100)),
                    "_offset": _vec2(op.get("offset_x", 0), op.get("offset_y", 0)),
                }
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_circle_collider2d":
                nid = op["node_id"]
                obj = {
                    "__type__": "cc.CircleCollider2D", "_name": "", "_objFlags": 0,
                    "node": _ref(nid), "_enabled": True, "__prefab": None,
                    "_id": _nid("cc2"),
                    "tag": op.get("tag", 0),
                    "_density": op.get("density", 1.0),
                    "_sensor": op.get("is_sensor", False),
                    "_friction": op.get("friction", 0.2),
                    "_restitution": op.get("restitution", 0.0),
                    "_radius": op.get("radius", 50),
                    "_offset": _vec2(op.get("offset_x", 0), op.get("offset_y", 0)),
                }
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_button":
                nid = op["node_id"]
                obj = {
                    "__type__": "cc.Button", "_name": "", "_objFlags": 0,
                    "node": _ref(nid), "_enabled": True, "__prefab": None,
                    "_id": _nid("btn"),
                    "transition": op.get("transition", 2),
                    "zoomScale": op.get("zoom_scale", 1.1),
                    "duration": 0.1, "_interactable": True, "clickEvents": [],
                }
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "attach_script":
                nid = op["node_id"]
                props = _wrap_props(op.get("props") or {})
                cid = _attach_component(s, nid, _make_script_component(
                    op["script_uuid_compressed"], nid, props))
                results.append(cid)

            elif action == "link_property":
                cid = op["component_id"]
                target = op.get("target_id")
                s[cid][op["prop_name"]] = _ref(target) if target is not None else None
                results.append(True)

            elif action == "set_property":
                s[op["object_id"]][op["prop_name"]] = op["value"]
                results.append(True)

            elif action == "set_position":
                s[op["node_id"]]["_lpos"] = _vec3(op.get("x", 0), op.get("y", 0), op.get("z", 0))
                results.append(True)

            elif action == "set_active":
                s[op["node_id"]]["_active"] = op.get("active", True)
                results.append(True)

            else:
                results.append({"error": f"unknown op: {action}"})

        except Exception as e:
            results.append({"error": f"op[{i}] {action}: {e}"})

    _save_scene(scene_path, s)
    return {
        "object_count": len(s),
        "ops_executed": len(operations),
        "results": results,
    }


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

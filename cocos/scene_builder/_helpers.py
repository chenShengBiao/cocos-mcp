"""Internal helpers shared across the scene_builder submodules.

Three categories live here:

  * **Primitive value factories** (``_vec3``/``_color``/``_ref`` ...) and
    **component factories** (``_make_node``/``_make_uitransform`` ...) that
    produce the JSON dicts Cocos Creator expects in scene/prefab files.
  * **Scene IO** — ``_load_scene``/``_save_scene`` and the
    ``_attach_component`` mutator with its UITransform auto-attach safety net.
  * **Property auto-wrapping** — ``_auto_wrap_value`` / ``_wrap_props`` for
    the heuristic int→__id__ / list→Vec3 coercion used in batch & script attach.

Every name in this module is treated as private to ``cocos.scene_builder``;
nothing outside the package should import from here directly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Compact mode trims `indent=2` to `separators=(",", ":")` for ~35% faster
# scene-file writes on big scenes (500+ objects). Cocos Creator parses both
# fine; the only thing you lose is git-diff-friendly formatting. Enable
# with `COCOS_MCP_SCENE_COMPACT=1` for CI / batch builds where speed beats
# diff readability.
_COMPACT = os.environ.get("COCOS_MCP_SCENE_COMPACT", "").lower() in ("1", "true", "yes")

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
                h_align: int = 1, v_align: int = 1,
                overflow: int = 0, enable_wrap: bool = False,
                line_height: int = 0, enable_outline: bool = True,
                outline_color=(0, 0, 0, 255), outline_width: int = 3,
                cache_mode: int = 0) -> dict:
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
        "_lineHeight": line_height if line_height > 0 else font_size,
        "_overflow": overflow,
        "_enableWrapText": enable_wrap,
        "_font": None,
        "_isSystemFontUsed": True,
        "_spacingX": 0,
        "_isItalic": False,
        "_isBold": False,
        "_isUnderline": False,
        "_underlineHeight": 2,
        "_cacheMode": cache_mode,
        "_enableOutline": enable_outline,
        "_outlineColor": _color(*outline_color),
        "_outlineWidth": outline_width,
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
        if _COMPACT:
            json.dump(scene, f, separators=(",", ":"))
        else:
            json.dump(scene, f, indent=2)


# ----------- attachment helpers (UI-render auto-attach) -----------

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


# ----------- property auto-wrapping (used by attach_script + batch_ops) -----------

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

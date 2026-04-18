"""Batch scene operations — execute many mutations in one read/write cycle.

Useful when an MCP client wants to build a node + attach UI + attach script
in three "logical" calls without paying the file-IO cost three times.

Supports `$N` back-references: if op N returns a node/component id, op M
(M > N) can pass `"$N"` wherever an int id is expected.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ._helpers import (
    LAYER_UI_2D,
    _attach_component,
    _load_scene,
    _make_camera,
    _make_graphics,
    _make_label,
    _make_node,
    _make_script_component,
    _make_sprite,
    _make_uitransform,
    _make_widget,
    _nid,
    _quat,
    _ref,
    _save_scene,
    _size,
    _vec2,
    _vec3,
    _wrap_props,
)


def _make_generic(nid: int, type_name: str, prefix: str, props: dict) -> dict:
    """In-memory factory for components without a dedicated _make_* helper.

    Mirrors what ``add_component`` does in the public API: builds the standard
    Cocos component skeleton (name/objFlags/node-ref/_id) and merges the
    type-specific props on top. Used by batch ops to avoid going through the
    full read-mutate-write cycle.
    """
    obj: dict = {
        "__type__": type_name,
        "_name": "",
        "_objFlags": 0,
        "node": _ref(nid),
        "_enabled": True,
        "__prefab": None,
        "_id": _nid(prefix),
    }
    obj.update(props)
    return obj


def batch_ops(scene_path: str | Path, operations: list[dict]) -> dict:
    """Execute multiple scene operations in one file read/write cycle.

    Supports $N back-references: if an op returns an int (node/component id),
    later ops can reference it as "$0", "$1", etc.

    Supported op types:

      Structural:
        add_node, attach_script, link_property, set_property,
        set_position, set_active, set_scale, set_rotation, set_layer,
        set_uuid_property

      Components:
        add_uitransform, add_widget, add_sprite, add_label, add_graphics,
        add_camera, add_mask, add_richtext, add_button, add_layout,
        add_progress_bar, add_audio_source, add_animation,
        add_rigidbody2d, add_box_collider2d, add_circle_collider2d,
        add_component (generic — pass type_name + props)
    """
    s = _load_scene(scene_path)
    results: list[Any] = []

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
                obj = {
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
                props = op.get("props") or {}  # no auto-wrap, pass as-is
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

            elif action == "set_scale":
                nid = op["node_id"]
                s[nid]["_lscale"] = _vec3(
                    op.get("sx", 1), op.get("sy", 1), op.get("sz", 1))
                results.append(True)

            elif action == "set_rotation":
                nid = op["node_id"]
                angle_z = op.get("angle_z", 0)
                s[nid]["_euler"] = _vec3(0, 0, angle_z)
                rad = math.radians(angle_z / 2)
                s[nid]["_lrot"] = _quat(0, 0, math.sin(rad), math.cos(rad))
                results.append(True)

            elif action == "set_layer":
                s[op["node_id"]]["_layer"] = op["layer"]
                results.append(True)

            elif action == "set_uuid_property":
                s[op["object_id"]][op["prop_name"]] = {"__uuid__": op["uuid"]}
                results.append(True)

            elif action == "add_widget":
                nid = op["node_id"]
                cid = _attach_component(s, nid, _make_widget(
                    nid, op.get("align_flags", 45), op.get("target_id")))
                results.append(cid)

            elif action == "add_camera":
                nid = op["node_id"]
                color = (op.get("clear_color_r", 0), op.get("clear_color_g", 0),
                         op.get("clear_color_b", 0), op.get("clear_color_a", 255))
                cid = _attach_component(s, nid, _make_camera(
                    nid, op.get("ortho_height", 320), color))
                results.append(cid)

            elif action == "add_layout":
                nid = op["node_id"]
                cid = _attach_component(s, nid, _make_generic(nid, "cc.Layout", "lay", {
                    "_layoutType": op.get("layout_type", 1),
                    "_resizeMode": op.get("resize_mode", 1),
                    "_N$spacingX": op.get("spacing_x", 0),
                    "_N$spacingY": op.get("spacing_y", 0),
                    "_N$paddingTop": op.get("padding_top", 0),
                    "_N$paddingBottom": op.get("padding_bottom", 0),
                    "_N$paddingLeft": op.get("padding_left", 0),
                    "_N$paddingRight": op.get("padding_right", 0),
                    "_N$horizontalDirection": op.get("h_direction", 0),
                    "_N$verticalDirection": op.get("v_direction", 1),
                }))
                results.append(cid)

            elif action == "add_progress_bar":
                nid = op["node_id"]
                props = {
                    "mode": op.get("mode", 0),
                    "totalLength": op.get("total_length", 100),
                    "progress": op.get("progress", 1.0),
                    "reverse": op.get("reverse", False),
                }
                if op.get("bar_sprite_id") is not None:
                    props["_N$barSprite"] = _ref(op["bar_sprite_id"])
                cid = _attach_component(s, nid, _make_generic(nid, "cc.ProgressBar", "pgb", props))
                results.append(cid)

            elif action == "add_audio_source":
                nid = op["node_id"]
                props = {
                    "playOnAwake": op.get("play_on_awake", False),
                    "loop": op.get("loop", False),
                    "volume": op.get("volume", 1.0),
                }
                if op.get("clip_uuid"):
                    props["_clip"] = {"__uuid__": op["clip_uuid"]}
                cid = _attach_component(s, nid, _make_generic(nid, "cc.AudioSource", "aud", props))
                results.append(cid)

            elif action == "add_animation":
                nid = op["node_id"]
                props = {
                    "playOnLoad": op.get("play_on_load", True),
                    "_clips": [],
                }
                if op.get("default_clip_uuid"):
                    props["_defaultClip"] = {"__uuid__": op["default_clip_uuid"]}
                if op.get("clip_uuids"):
                    props["_clips"] = [{"__uuid__": u} for u in op["clip_uuids"]]
                cid = _attach_component(s, nid, _make_generic(nid, "cc.Animation", "anm", props))
                results.append(cid)

            elif action == "add_mask":
                nid = op["node_id"]
                cid = _attach_component(s, nid, _make_generic(nid, "cc.Mask", "msk", {
                    "_type": op.get("mask_type", 0),
                    "_inverted": op.get("inverted", False),
                    "_segments": op.get("segments", 64),
                }))
                results.append(cid)

            elif action == "add_richtext":
                nid = op["node_id"]
                cid = _attach_component(s, nid, _make_generic(nid, "cc.RichText", "rtx", {
                    "_lineHeight": op.get("line_height", 40),
                    "string": op.get("text", "<b>Hello</b>"),
                    "fontSize": op.get("font_size", 40),
                    "maxWidth": op.get("max_width", 0),
                    "horizontalAlign": op.get("horizontal_align", 0),
                    "handleTouchEvent": True,
                }))
                results.append(cid)

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

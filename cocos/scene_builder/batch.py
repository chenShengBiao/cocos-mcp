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

from ..types import BatchOpsResult
from ._helpers import (
    LAYER_UI_2D,
    _attach_component,
    _ensure_node_prefab_info,
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
    _size as _cc_size,
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


def batch_ops(scene_path: str | Path, operations: list[dict]) -> BatchOpsResult:
    """Execute multiple scene operations in one file read/write cycle.

    Supports two back-reference forms:
      * ``"$N"`` — positional: the result of op index N (0-based).
      * ``"$name"`` — named: the result of any earlier op that set
        ``"name": "<name>"``. Cleaner for large batches where agents
        lose track of positional indices. Names are resolved against
        the ``named_results`` dict built as ops run, so forward
        references don't resolve (the name must already be bound).

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
        add_polygon_collider2d, add_component (generic — pass type_name + props)

      Physics joints (Cocos 3.8 — 8 variants):
        add_distance_joint2d, add_hinge_joint2d, add_spring_joint2d,
        add_mouse_joint2d, add_slider_joint2d, add_wheel_joint2d,
        add_fixed_joint_2d, add_relative_joint2d
    """
    s = _load_scene(scene_path)
    is_prefab = str(scene_path).endswith(".prefab")
    results: list[Any] = []
    named_results: dict[str, Any] = {}

    def resolve(val):
        """Replace ``"$N"`` / ``"$name"`` strings with prior op results.

        Positional form looks at ``results[N]``; named form looks at
        ``named_results[name]``. Unknown names fall through unchanged
        so agents get a clear KeyError at use-site rather than a silent
        substitution of the literal string.
        """
        if isinstance(val, str) and val.startswith("$") and len(val) > 1:
            key = val[1:]
            if key.isdigit():
                idx = int(key)
                if idx < len(results):
                    return results[idx]
            elif key in named_results:
                return named_results[key]
        return val

    def resolve_dict(d: dict) -> dict:
        # ``name`` is the ref key itself and must survive raw — never run
        # it through resolve() (otherwise ``name: "bird"`` would attempt
        # to look up ``bird`` before it's bound and fall through, but a
        # later op with the same literal would reach a shadowed value).
        return {k: (v if k == "name" else resolve(v)) for k, v in d.items()}

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
                # Prefab files: give every node its own cc.PrefabInfo.
                if is_prefab:
                    _ensure_node_prefab_info(s, new_id)
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
                # Field names mirror cocos-engine 3.8's @serializable
                # layout — see physics.py module docstring for the full
                # convention. Mismatches (e.g. "type" instead of "_type")
                # are silently discarded at deserialization, falling the
                # body back to its runtime default.
                nid = op["node_id"]
                obj = {
                    "__type__": "cc.RigidBody2D", "_name": "", "_objFlags": 0,
                    "node": _ref(nid), "_enabled": True, "__prefab": None,
                    "_id": _nid("rb2"),
                    # Public @serializable — no underscore.
                    "enabledContactListener": True,
                    "bullet": op.get("bullet", False),
                    "awakeOnLoad": op.get("awake_on_load", True),
                    # Private @serializable — underscore prefix.
                    "_group": op.get("group", 1),
                    "_type": op.get("body_type", 2),
                    "_allowSleep": True,
                    "_gravityScale": op.get("gravity_scale", 1.0),
                    "_linearDamping": op.get("linear_damping", 0.0),
                    "_angularDamping": op.get("angular_damping", 0.0),
                    "_linearVelocity": _vec2(0, 0),
                    "_angularVelocity": 0.0,
                    "_fixedRotation": op.get("fixed_rotation", False),
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
                    "_size": _cc_size(op.get("width", 100), op.get("height", 100)),
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
                # Auto-compress 36-char standard UUIDs. Same contract as
                # the direct scene_builder.add_script — agents routinely
                # paste the standard UUID from .ts.meta, and silently
                # passing it as __type__ would produce a no-op component.
                script_uuid = op["script_uuid_compressed"]
                if len(script_uuid) == 36 and script_uuid.count("-") == 4:
                    from ..uuid_util import compress_uuid
                    script_uuid = compress_uuid(script_uuid)
                cid = _attach_component(s, nid, _make_script_component(
                    script_uuid, nid, props))
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

            elif action == "add_polygon_collider2d":
                nid = op["node_id"]
                pts = op.get("points") or [[-50, -50], [50, -50], [50, 50], [-50, 50]]
                obj = _make_generic(nid, "cc.PolygonCollider2D", "pc2", {
                    "tag": op.get("tag", 0),
                    "_density": op.get("density", 1.0),
                    "_sensor": op.get("is_sensor", False),
                    "_friction": op.get("friction", 0.2),
                    "_restitution": op.get("restitution", 0.0),
                    # Engine typing is ``Vec2[]`` — each vertex must be
                    # a cc.Vec2 dict, not a [x, y] list.
                    "_points": [_vec2(x, y) for x, y in pts],
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            # ---- Joint2D dispatch (Cocos 3.8 — 8 variants) ----
            # Every joint inherits {node, connectedBody, collideConnected}
            # (public @serializable — no underscore). Subclass-specific
            # fields (_motorSpeed, _maxLength, etc.) use the private
            # underscore-prefixed names. _joint_base emits the shared
            # skeleton; each branch layers its own tunables. See
            # physics.py for the serialization convention note.
            elif action == "add_distance_joint2d":
                # Note: serialized distance field is ``_maxLength``
                # (not ``_distance``) in Cocos 3.8.
                nid = op["node_id"]
                obj = _joint_base(nid, "cc.DistanceJoint2D", "dj2", op)
                obj.update({
                    "anchor": _vec2(op.get("anchor_x", 0), op.get("anchor_y", 0)),
                    "connectedAnchor": _vec2(op.get("connected_anchor_x", 0),
                                             op.get("connected_anchor_y", 0)),
                    "_maxLength": op.get("distance", 1.0),
                    "_autoCalcDistance": op.get("auto_calc_distance", True),
                    "_frequency": op.get("frequency", 0.0),
                    "_dampingRatio": op.get("damping_ratio", 0.0),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_hinge_joint2d":
                nid = op["node_id"]
                obj = _joint_base(nid, "cc.HingeJoint2D", "hj2", op)
                obj.update({
                    "anchor": _vec2(op.get("anchor_x", 0), op.get("anchor_y", 0)),
                    "connectedAnchor": _vec2(op.get("connected_anchor_x", 0),
                                             op.get("connected_anchor_y", 0)),
                    "_enableMotor": op.get("enable_motor", False),
                    "_motorSpeed": op.get("motor_speed", 0.0),
                    "_maxMotorTorque": op.get("max_motor_torque", 1000.0),
                    "_enableLimit": op.get("enable_limit", False),
                    "_lowerAngle": op.get("lower_angle", 0.0),
                    "_upperAngle": op.get("upper_angle", 0.0),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_spring_joint2d":
                nid = op["node_id"]
                obj = _joint_base(nid, "cc.SpringJoint2D", "sj2", op)
                obj.update({
                    "anchor": _vec2(op.get("anchor_x", 0), op.get("anchor_y", 0)),
                    "connectedAnchor": _vec2(op.get("connected_anchor_x", 0),
                                             op.get("connected_anchor_y", 0)),
                    "_distance": op.get("distance", 1.0),
                    "_autoCalcDistance": op.get("auto_calc_distance", True),
                    "_frequency": op.get("frequency", 5.0),
                    "_dampingRatio": op.get("damping_ratio", 0.7),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_mouse_joint2d":
                # MouseJoint doesn't use the base connectedBody /
                # collideConnected machinery. _target is a runtime-only
                # field but we emit it for consumer inspection.
                nid = op["node_id"]
                obj = _make_generic(nid, "cc.MouseJoint2D", "mj2", {
                    "_maxForce": op.get("max_force", 1000.0),
                    "_frequency": op.get("frequency", 5.0),
                    "_dampingRatio": op.get("damping_ratio", 0.7),
                    "_target": _vec2(op.get("target_x", 0), op.get("target_y", 0)),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_slider_joint2d":
                nid = op["node_id"]
                obj = _joint_base(nid, "cc.SliderJoint2D", "sl2", op)
                obj.update({
                    "anchor": _vec2(op.get("anchor_x", 0), op.get("anchor_y", 0)),
                    "connectedAnchor": _vec2(op.get("connected_anchor_x", 0),
                                             op.get("connected_anchor_y", 0)),
                    "_angle": op.get("angle", 0.0),
                    "_enableMotor": op.get("enable_motor", False),
                    "_motorSpeed": op.get("motor_speed", 0.0),
                    "_maxMotorForce": op.get("max_motor_force", 1000.0),
                    "_enableLimit": op.get("enable_limit", False),
                    "_lowerLimit": op.get("lower_limit", 0.0),
                    "_upperLimit": op.get("upper_limit", 0.0),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_wheel_joint2d":
                nid = op["node_id"]
                obj = _joint_base(nid, "cc.WheelJoint2D", "wj2", op)
                obj.update({
                    "anchor": _vec2(op.get("anchor_x", 0), op.get("anchor_y", 0)),
                    "connectedAnchor": _vec2(op.get("connected_anchor_x", 0),
                                             op.get("connected_anchor_y", 0)),
                    "_angle": op.get("angle", 90.0),
                    "_enableMotor": op.get("enable_motor", False),
                    "_motorSpeed": op.get("motor_speed", 0.0),
                    "_maxMotorTorque": op.get("max_motor_torque", 1000.0),
                    "_frequency": op.get("frequency", 5.0),
                    "_dampingRatio": op.get("damping_ratio", 0.7),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_fixed_joint_2d":
                # FixedJoint2D in 3.8 has no ``_angle`` field —
                # removed; the old ``angle=`` param was silently ignored.
                nid = op["node_id"]
                obj = _joint_base(nid, "cc.FixedJoint2D", "fj2", op)
                obj.update({
                    "anchor": _vec2(op.get("anchor_x", 0), op.get("anchor_y", 0)),
                    "connectedAnchor": _vec2(op.get("connected_anchor_x", 0),
                                             op.get("connected_anchor_y", 0)),
                    "_frequency": op.get("frequency", 5.0),
                    "_dampingRatio": op.get("damping_ratio", 0.7),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            elif action == "add_relative_joint2d":
                nid = op["node_id"]
                obj = _joint_base(nid, "cc.RelativeJoint2D", "rj2", op)
                obj.update({
                    "_maxForce": op.get("max_force", 1000.0),
                    "_maxTorque": op.get("max_torque", 1000.0),
                    "_correctionFactor": op.get("correction_factor", 0.3),
                    "_autoCalcOffset": op.get("auto_calc_offset", True),
                    "_linearOffset": _vec2(op.get("linear_offset_x", 0),
                                           op.get("linear_offset_y", 0)),
                    "_angularOffset": op.get("angular_offset", 0.0),
                })
                cid = _attach_component(s, nid, obj)
                results.append(cid)

            else:
                results.append({"error": f"unknown op: {action}"})

            # Bind the name (if set) AFTER the op succeeded — so a failed
            # op doesn't leak a broken entry into named_results. We peek
            # the LAST element of results rather than tracking a separate
            # variable; works for both success (int) and error (dict) —
            # the latter is intentionally indexable so a later op can
            # detect upstream failure if it wants.
            name = raw_op.get("name")
            if isinstance(name, str) and name:
                named_results[name] = results[-1]

        except (KeyError, TypeError, ValueError, IndexError) as e:
            # Only swallow errors that plausibly come from malformed op input
            # (missing required field, wrong type, bad $N ref). Programmer
            # bugs in this module (AttributeError, NameError, ImportError,
            # RuntimeError, ...) should still bubble up so they surface in
            # tests rather than being silently reported as "op failed".
            results.append({"error": f"op[{i}] {action}: {type(e).__name__}: {e}"})

    _save_scene(scene_path, s)
    return {
        "object_count": len(s),
        "ops_executed": len(operations),
        "results": results,
        "named_results": named_results,
    }


def _joint_base(nid: int, type_name: str, prefix: str, op: dict) -> dict:
    """Shared skeleton for ``cc.*Joint2D`` ops inside ``batch_ops``.

    Joint2D's base @serializable fields are PUBLIC — no underscore
    prefix on ``connectedBody`` / ``collideConnected``. See the
    joint-2d.ts source and the note in physics.py.
    """
    obj: dict = {
        "__type__": type_name,
        "_name": "",
        "_objFlags": 0,
        "node": _ref(nid),
        "_enabled": True,
        "__prefab": None,
        "_id": _nid(prefix),
        "collideConnected": op.get("collide_connected", False),
    }
    cb = op.get("connected_body_id")
    obj["connectedBody"] = _ref(cb) if cb is not None else None
    return obj

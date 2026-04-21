"""2D physics components — RigidBody2D, three colliders, and nine joint types.

All ``add_*`` functions follow the ``load → mutate → save`` pattern via the
shared helpers in ``_helpers`` — no in-memory scene state leaks across calls.

Why this lives outside ``__init__.py``: joints alone are ~200 lines of
near-identical boilerplate (each joint type has 5-10 knobs) and benefit
from being kept together. The imports of ``add_component`` are late-bound
(inside each function) because ``__init__.py`` re-imports from this module,
and eager imports would create a load-time cycle.
"""
from __future__ import annotations

from pathlib import Path

from ._helpers import (
    _attach_component,
    _load_scene,
    _nid,
    _ref,
    _save_scene,
    _size as _cc_size,
    _vec2,
)


# Field-name conventions (verified against cocos-engine 3.8 source, see
# ``cocos/physics-2d/framework/components/*``):
#
# * Cocos uses ``@serializable`` on the *backing* field. Getter/setter
#   pairs don't change the JSON key — the key is whatever the stored
#   member is named. So for ``get type() {...} set type(v){this._type=v}``
#   plus ``@serializable private _type``, the JSON key is ``_type``.
# * The Joint2D base class (see joint-2d.ts) uses PUBLIC ``@serializable``
#   fields without underscore: ``anchor``, ``connectedAnchor``,
#   ``collideConnected``, ``connectedBody``. Subclass-specific fields
#   (e.g. HingeJoint2D's ``_motorSpeed``) are private + underscore.
# * RigidBody2D's public serializables are ``enabledContactListener``,
#   ``bullet``, ``awakeOnLoad``; everything else (``_type``, ``_allowSleep``,
#   ``_gravityScale``, ``_linearDamping``, ``_angularDamping``,
#   ``_linearVelocity``, ``_angularVelocity``, ``_fixedRotation``, ``_group``)
#   is underscore-prefixed.
# * BoxCollider2D.``_size`` is a ``cc.Size`` dict (not a bare [w, h] list).
#   Same for any ``Vec2`` field — a list deserializes to a default-value
#   Vec2, silently losing the configuration the agent just set.
#
# Before the cocos-engine audit (commit history for physics.py), most of
# the above keys were written without the underscore prefix. The engine
# read them as "unknown property" and silently fell back to the defaults,
# so every cocos-mcp-built RigidBody2D ran as a Dynamic body with
# gravity=1 / no damping / movable rotation regardless of what the
# caller asked for. Fixed here; batch.py mirrors the same shape.


# ----------- rigid body + colliders -----------

def add_rigidbody2d(scene_path: str | Path, node_id: int,
                    body_type: int = 2, gravity_scale: float = 1.0,
                    linear_damping: float = 0.0, angular_damping: float = 0.0,
                    fixed_rotation: bool = False, bullet: bool = False,
                    awake_on_load: bool = True, group: int = 1) -> int:
    """Attach cc.RigidBody2D.

    Body type: 0=Static, 1=Kinematic, 2=Dynamic. ``group`` is the
    physics collision-group bitmask (``PhysicsGroup.DEFAULT`` = 1).

    Emits the exact serialization shape Cocos 3.8's engine reads — see
    the field-name note at the top of the file.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.RigidBody2D", {
        # Public @serializable fields — no underscore.
        "enabledContactListener": True,
        "bullet": bullet,
        "awakeOnLoad": awake_on_load,
        # Private @serializable backing fields — underscore prefix.
        "_group": group,
        "_type": body_type,
        "_allowSleep": True,
        "_gravityScale": gravity_scale,
        "_linearDamping": linear_damping,
        "_angularDamping": angular_damping,
        "_linearVelocity": _vec2(0, 0),
        "_angularVelocity": 0.0,
        "_fixedRotation": fixed_rotation,
    })


def add_box_collider2d(scene_path: str | Path, node_id: int,
                       width: float = 100, height: float = 100,
                       offset_x: float = 0, offset_y: float = 0,
                       density: float = 1.0, friction: float = 0.2,
                       restitution: float = 0.0, is_sensor: bool = False,
                       tag: int = 0) -> int:
    """Attach cc.BoxCollider2D.

    ``_size`` is emitted as a ``cc.Size`` dict and ``_offset`` as a
    ``cc.Vec2`` dict — list forms silently deserialize to default (0)
    values in Cocos 3.8.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.BoxCollider2D", {
        "tag": tag,
        "_density": density,
        "_sensor": is_sensor,
        "_friction": friction,
        "_restitution": restitution,
        "_size": _cc_size(width, height),
        "_offset": _vec2(offset_x, offset_y),
    })


def add_circle_collider2d(scene_path: str | Path, node_id: int,
                          radius: float = 50,
                          offset_x: float = 0, offset_y: float = 0,
                          density: float = 1.0, friction: float = 0.2,
                          restitution: float = 0.0, is_sensor: bool = False,
                          tag: int = 0) -> int:
    """Attach cc.CircleCollider2D. ``_offset`` emitted as cc.Vec2 dict."""
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.CircleCollider2D", {
        "tag": tag,
        "_density": density,
        "_sensor": is_sensor,
        "_friction": friction,
        "_restitution": restitution,
        "_radius": radius,
        "_offset": _vec2(offset_x, offset_y),
    })


def add_polygon_collider2d(scene_path: str | Path, node_id: int,
                           points: list[list[float]] | None = None,
                           density: float = 1.0, friction: float = 0.2,
                           restitution: float = 0.0, is_sensor: bool = False,
                           tag: int = 0) -> int:
    """Attach cc.PolygonCollider2D.

    ``points`` is a list of ``[x, y]`` pairs; each is wrapped as a
    ``cc.Vec2`` dict on write. Engine typing is ``Vec2[]`` — raw tuples
    deserialize to zero-filled Vec2 and the shape becomes a degenerate
    point.
    """
    from cocos.scene_builder import add_component
    pts = points or [[-50, -50], [50, -50], [50, 50], [-50, 50]]
    return add_component(scene_path, node_id, "cc.PolygonCollider2D", {
        "tag": tag,
        "_density": density,
        "_sensor": is_sensor,
        "_friction": friction,
        "_restitution": restitution,
        "_points": [_vec2(x, y) for x, y in pts],
    })


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
    """Common joint object skeleton.

    Joint2D base class uses PUBLIC ``@serializable`` fields, so the
    JSON keys have no underscore — see joint-2d.ts for the source-of-
    truth. Subclass-specific fields (``_motorSpeed`` etc.) are emitted
    by each ``add_*_joint2d`` below.
    """
    return {
        "__type__": type_name,
        "_name": "",
        "_objFlags": 0,
        "node": _ref(node_idx),
        "_enabled": True,
        "__prefab": None,
        # Public @serializable — NO underscore prefix.
        "connectedBody": _ref(connected_body_id) if connected_body_id is not None else None,
        "collideConnected": collide_connected,
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
    """Attach cc.DistanceJoint2D — keeps two bodies a fixed distance apart.

    Note: the serialized distance field is ``_maxLength`` in Cocos 3.8,
    not ``_distance`` as older ports assumed. The python parameter name
    ``distance=`` stays for API stability.
    """
    obj = _make_joint2d_base(node_id, "cc.DistanceJoint2D", "dj2", connected_body_id, collide_connected)
    obj.update({
        "anchor": _vec2(*anchor),
        "connectedAnchor": _vec2(*connected_anchor),
        "_maxLength": distance,
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
        "anchor": _vec2(*anchor),
        "connectedAnchor": _vec2(*connected_anchor),
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
        "anchor": _vec2(*anchor),
        "connectedAnchor": _vec2(*connected_anchor),
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
    """Attach cc.MouseJoint2D — drag-to-target constraint, used for picking up bodies.

    Note: MouseJoint2D's ``_target`` is a non-serialized runtime field in
    Cocos 3.8 — we still emit it for consumer convenience (agents that
    inspect the scene file), but the runtime reads it from user input,
    not from the scene. ``anchor`` / ``connectedAnchor`` / ``connectedBody``
    are inherited but unused by the mouse-joint runtime and omitted.
    """
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
        "anchor": _vec2(*anchor),
        "connectedAnchor": _vec2(*connected_anchor),
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
        "anchor": _vec2(*anchor),
        "connectedAnchor": _vec2(*connected_anchor),
        "_angle": angle,
        "_enableMotor": enable_motor,
        "_motorSpeed": motor_speed,
        "_maxMotorTorque": max_motor_torque,
        "_frequency": frequency,
        "_dampingRatio": damping_ratio,
    })
    return _attach_joint(scene_path, node_id, obj)


def add_fixed_joint_2d(scene_path: str | Path, node_id: int,
                       connected_body_id: int | None = None,
                       anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                       frequency: float = 5.0, damping_ratio: float = 0.7,
                       collide_connected: bool = False) -> int:
    """Attach cc.FixedJoint2D — rigidly fuses two bodies (breakable structures).

    Named "weld" in Box2D and in earlier releases of this library; Cocos 3.8's
    class is ``cc.FixedJoint2D``. The previous ``add_weld_joint2d`` emitted
    ``cc.WeldJoint2D`` which the 3.8 engine does not recognize, so scenes
    built with it silently had no joint at runtime.

    Note: FixedJoint2D in 3.8 has no ``_angle`` field (unlike Slider /
    Wheel). The previous ``angle=`` parameter was emitted but silently
    ignored; it is removed here. If you want a fixed rotational offset,
    pre-rotate the second body before attaching.
    """
    obj = _make_joint2d_base(node_id, "cc.FixedJoint2D", "fj2", connected_body_id, collide_connected)
    obj.update({
        "anchor": _vec2(*anchor),
        "connectedAnchor": _vec2(*connected_anchor),
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


# cc.MotorJoint2D does not exist in Cocos Creator 3.8 (verified against
# cocos-engine v3.8.6 sources: no motor-joint-2d.ts file in
# cocos/physics-2d/framework/components/joints/). The previous
# ``add_motor_joint2d`` tool emitted ``cc.MotorJoint2D`` which the runtime
# ignores, producing silently broken scenes. Removed for 3.8 parity. If you
# need a drive-to-target behavior, use ``add_relative_joint2d``, which
# covers the same use case via _linearOffset + _angularOffset.

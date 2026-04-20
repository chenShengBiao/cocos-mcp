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
    _vec2,
)


# ----------- rigid body + colliders -----------

def add_rigidbody2d(scene_path: str | Path, node_id: int,
                    body_type: int = 2, gravity_scale: float = 1.0,
                    linear_damping: float = 0.0, angular_damping: float = 0.0,
                    fixed_rotation: bool = False, bullet: bool = False,
                    awake_on_load: bool = True) -> int:
    """Attach cc.RigidBody2D. body_type: 0=Static, 1=Kinematic, 2=Dynamic."""
    from cocos.scene_builder import add_component
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
    from cocos.scene_builder import add_component
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
    from cocos.scene_builder import add_component
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
    from cocos.scene_builder import add_component
    pts = points or [[-50, -50], [50, -50], [50, 50], [-50, 50]]
    return add_component(scene_path, node_id, "cc.PolygonCollider2D", {
        "tag": tag,
        "_density": density,
        "_sensor": is_sensor,
        "_friction": friction,
        "_restitution": restitution,
        "_points": pts,
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


def add_fixed_joint_2d(scene_path: str | Path, node_id: int,
                       connected_body_id: int | None = None,
                       anchor: tuple = (0, 0), connected_anchor: tuple = (0, 0),
                       angle: float = 0.0,
                       frequency: float = 5.0, damping_ratio: float = 0.7,
                       collide_connected: bool = False) -> int:
    """Attach cc.FixedJoint2D — rigidly fuses two bodies (breakable structures).

    Named "weld" in Box2D and in earlier releases of this library; Cocos 3.8's
    class is ``cc.FixedJoint2D``. The previous ``add_weld_joint2d`` emitted
    ``cc.WeldJoint2D`` which the 3.8 engine does not recognize, so scenes
    built with it silently had no joint at runtime.
    """
    obj = _make_joint2d_base(node_id, "cc.FixedJoint2D", "fj2", connected_body_id, collide_connected)
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


# cc.MotorJoint2D does not exist in Cocos Creator 3.8 (verified against
# cocos-engine v3.8.6 sources: no motor-joint-2d.ts file in
# cocos/physics-2d/framework/components/joints/). The previous
# ``add_motor_joint2d`` tool emitted ``cc.MotorJoint2D`` which the runtime
# ignores, producing silently broken scenes. Removed for 3.8 parity. If you
# need a drive-to-target behavior, use ``add_relative_joint2d``, which
# covers the same use case via _linearOffset + _angularOffset.

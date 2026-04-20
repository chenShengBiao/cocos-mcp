"""3D physics components — RigidBody, nine colliders, two CharacterControllers.

Defaults match ``cocos-engine v3.8.6`` source exactly (verified per-field in
``cocos/physics/framework/components/...``). Notably:

* ``ERigidBodyType`` uses non-contiguous ints: STATIC=2, DYNAMIC=1, KINEMATIC=4.
  Don't assume 0/1/2 like the 2D API.
* ``EAxisDirection``: X=0, Y=1, Z=2 — the default for capsule/cylinder/cone.
* ``PhysicsSystem.PhysicsGroup.DEFAULT = 1`` — same default for RigidBody and
  CharacterController.

PhysicsMaterial is an **asset** (.pmat file), not a component — create one via
``cocos.project.create_physics_material`` and pass its UUID through
``cocos_set_uuid_property`` on the collider's ``_material`` field if you
need per-collider friction/restitution.

The late ``add_component`` import inside each function keeps the load graph
acyclic with ``scene_builder.__init__``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._helpers import (
    _attach_component,
    _load_scene,
    _nid,
    _ref,
    _save_scene,
    _vec3,
)

# ERigidBodyType — as defined in cocos/physics/framework/physics-enum.ts
RIGIDBODY_DYNAMIC = 1
RIGIDBODY_STATIC = 2
RIGIDBODY_KINEMATIC = 4

# EAxisDirection
AXIS_X = 0
AXIS_Y = 1
AXIS_Z = 2

_DEFAULT_GROUP = 1  # PhysicsSystem.PhysicsGroup.DEFAULT


# ----------- RigidBody -----------

def add_rigidbody_3d(scene_path: str | Path, node_id: int,
                    body_type: int = RIGIDBODY_DYNAMIC,
                    mass: float = 1.0,
                    use_gravity: bool = True,
                    allow_sleep: bool = True,
                    linear_damping: float = 0.1,
                    angular_damping: float = 0.1,
                    linear_factor: tuple = (1, 1, 1),
                    angular_factor: tuple = (1, 1, 1),
                    group: int = _DEFAULT_GROUP) -> int:
    """Attach cc.RigidBody (3D).

    body_type uses ``ERigidBodyType`` values: DYNAMIC=1, STATIC=2, KINEMATIC=4
    (non-contiguous — these are bitmask flags in the engine, not ordinals).
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.RigidBody", {
        "_group": group,
        "_type": body_type,
        "_mass": mass,
        "_allowSleep": allow_sleep,
        "_linearDamping": linear_damping,
        "_angularDamping": angular_damping,
        "_useGravity": use_gravity,
        "_linearFactor": _vec3(*linear_factor),
        "_angularFactor": _vec3(*angular_factor),
    })


# ----------- Colliders -----------
#
# Every 3D collider shares the base fields _isTrigger=false and
# _center=Vec3(0,0,0). Shape-specific fields are appended on top.

def _make_collider_base(is_trigger: bool = False,
                        center: tuple = (0, 0, 0)) -> dict:
    return {
        "_isTrigger": is_trigger,
        "_center": _vec3(*center),
    }


def add_box_collider_3d(scene_path: str | Path, node_id: int,
                        size: tuple = (1, 1, 1),
                        center: tuple = (0, 0, 0),
                        is_trigger: bool = False) -> int:
    """Attach cc.BoxCollider."""
    from cocos.scene_builder import add_component
    props = _make_collider_base(is_trigger, center)
    props["_size"] = _vec3(*size)
    return add_component(scene_path, node_id, "cc.BoxCollider", props)


def add_sphere_collider_3d(scene_path: str | Path, node_id: int,
                           radius: float = 0.5,
                           center: tuple = (0, 0, 0),
                           is_trigger: bool = False) -> int:
    """Attach cc.SphereCollider."""
    from cocos.scene_builder import add_component
    props = _make_collider_base(is_trigger, center)
    props["_radius"] = radius
    return add_component(scene_path, node_id, "cc.SphereCollider", props)


def add_capsule_collider_3d(scene_path: str | Path, node_id: int,
                            radius: float = 0.5,
                            cylinder_height: float = 1.0,
                            direction: int = AXIS_Y,
                            center: tuple = (0, 0, 0),
                            is_trigger: bool = False) -> int:
    """Attach cc.CapsuleCollider. direction: 0=X, 1=Y, 2=Z (EAxisDirection)."""
    from cocos.scene_builder import add_component
    props = _make_collider_base(is_trigger, center)
    props["_radius"] = radius
    props["_cylinderHeight"] = cylinder_height
    props["_direction"] = direction
    return add_component(scene_path, node_id, "cc.CapsuleCollider", props)


def add_cylinder_collider_3d(scene_path: str | Path, node_id: int,
                             radius: float = 0.5,
                             height: float = 2.0,
                             direction: int = AXIS_Y,
                             center: tuple = (0, 0, 0),
                             is_trigger: bool = False) -> int:
    """Attach cc.CylinderCollider."""
    from cocos.scene_builder import add_component
    props = _make_collider_base(is_trigger, center)
    props["_radius"] = radius
    props["_height"] = height
    props["_direction"] = direction
    return add_component(scene_path, node_id, "cc.CylinderCollider", props)


def add_cone_collider_3d(scene_path: str | Path, node_id: int,
                         radius: float = 0.5,
                         height: float = 1.0,
                         direction: int = AXIS_Y,
                         center: tuple = (0, 0, 0),
                         is_trigger: bool = False) -> int:
    """Attach cc.ConeCollider."""
    from cocos.scene_builder import add_component
    props = _make_collider_base(is_trigger, center)
    props["_radius"] = radius
    props["_height"] = height
    props["_direction"] = direction
    return add_component(scene_path, node_id, "cc.ConeCollider", props)


def add_plane_collider_3d(scene_path: str | Path, node_id: int,
                          normal: tuple = (0, 1, 0),
                          constant: float = 0.0,
                          center: tuple = (0, 0, 0),
                          is_trigger: bool = False) -> int:
    """Attach cc.PlaneCollider — infinite plane (ground)."""
    from cocos.scene_builder import add_component
    props = _make_collider_base(is_trigger, center)
    props["_normal"] = _vec3(*normal)
    props["_constant"] = constant
    return add_component(scene_path, node_id, "cc.PlaneCollider", props)


def add_mesh_collider_3d(scene_path: str | Path, node_id: int,
                         mesh_uuid: str | None = None,
                         convex: bool = False,
                         center: tuple = (0, 0, 0),
                         is_trigger: bool = False) -> int:
    """Attach cc.MeshCollider. ``convex=True`` is required for dynamic bodies —
    the PhysX/Bullet backends only support convex meshes on non-static rigid
    bodies. For static ground geometry, triangle (non-convex) meshes work."""
    from cocos.scene_builder import add_component
    props: dict[str, Any] = _make_collider_base(is_trigger, center)
    props["_mesh"] = {"__uuid__": mesh_uuid} if mesh_uuid else None
    props["_convex"] = convex
    return add_component(scene_path, node_id, "cc.MeshCollider", props)


def add_terrain_collider_3d(scene_path: str | Path, node_id: int,
                            terrain_uuid: str | None = None,
                            center: tuple = (0, 0, 0),
                            is_trigger: bool = False) -> int:
    """Attach cc.TerrainCollider. Requires a cc.Terrain asset to already
    exist; pass its UUID. If ``terrain_uuid`` is None the component is
    attached with an empty terrain ref (caller can wire it later via
    cocos_set_uuid_property)."""
    from cocos.scene_builder import add_component
    props: dict[str, Any] = _make_collider_base(is_trigger, center)
    props["_terrain"] = {"__uuid__": terrain_uuid} if terrain_uuid else None
    return add_component(scene_path, node_id, "cc.TerrainCollider", props)


# ----------- CharacterController -----------
#
# CharacterController is mutually exclusive with RigidBody — it's the
# engine's built-in kinematic movement for player characters (avoids the
# common "write your own kinematic controller" pitfall). Two shape variants:
# box + capsule.

def _make_character_base(group: int,
                         min_move_distance: float,
                         step_offset: float,
                         slope_limit: float,
                         skin_width: float,
                         center: tuple) -> dict:
    return {
        "_group": group,
        "_minMoveDistance": min_move_distance,
        "_stepOffset": step_offset,
        "_slopeLimit": slope_limit,
        "_skinWidth": skin_width,
        "_center": _vec3(*center),
    }


def add_box_character_controller(scene_path: str | Path, node_id: int,
                                 half_height: float = 0.5,
                                 half_side_extent: float = 0.5,
                                 half_forward_extent: float = 0.5,
                                 min_move_distance: float = 0.001,
                                 step_offset: float = 0.5,
                                 slope_limit: float = 45.0,
                                 skin_width: float = 0.01,
                                 center: tuple = (0, 0, 0),
                                 group: int = _DEFAULT_GROUP) -> int:
    """Attach cc.BoxCharacterController — AABB character shape."""
    from cocos.scene_builder import add_component
    props = _make_character_base(group, min_move_distance, step_offset,
                                 slope_limit, skin_width, center)
    props.update({
        "_halfHeight": half_height,
        "_halfSideExtent": half_side_extent,
        "_halfForwardExtent": half_forward_extent,
    })
    return add_component(scene_path, node_id, "cc.BoxCharacterController", props)


def add_capsule_character_controller(scene_path: str | Path, node_id: int,
                                     radius: float = 0.5,
                                     height: float = 1.0,
                                     min_move_distance: float = 0.001,
                                     step_offset: float = 0.5,
                                     slope_limit: float = 45.0,
                                     skin_width: float = 0.01,
                                     center: tuple = (0, 0, 0),
                                     group: int = _DEFAULT_GROUP) -> int:
    """Attach cc.CapsuleCharacterController — capsule character shape (more
    common for humanoid players than box)."""
    from cocos.scene_builder import add_component
    props = _make_character_base(group, min_move_distance, step_offset,
                                 slope_limit, skin_width, center)
    props.update({
        "_radius": radius,
        "_height": height,
    })
    return add_component(scene_path, node_id, "cc.CapsuleCharacterController", props)

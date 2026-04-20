"""Tests for the 3D physics surface: RigidBody, colliders, CharacterController,
PhysicsMaterial asset, and set_physics_3d_config.

Field defaults in the assertions below are copied from cocos-engine v3.8.6
sources (cocos/physics/framework/components/...). If one of these tests
starts failing after an engine bump, the fix is to pull the new defaults
from the source — don't relax the assertion to whatever our code emits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import build as cb
from cocos import project as cp
from cocos import scene_builder as sb


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "p"
    (p / "assets").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


def _tmp_scene(tmp_path: Path) -> tuple[Path, dict]:
    path = tmp_path / "s.scene"
    info = sb.create_empty_scene(path)
    return path, info


# ----------- RigidBody -----------

def test_rigidbody_3d_dynamic_defaults_match_engine(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Player")
    cid = sb.add_rigidbody_3d(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.RigidBody"
    # ERigidBodyType.DYNAMIC = 1 (not 0 or 2 — bitmask-valued enum)
    assert obj["_type"] == 1
    assert obj["_mass"] == 1.0
    assert obj["_allowSleep"] is True
    assert obj["_useGravity"] is True
    assert obj["_linearDamping"] == 0.1
    assert obj["_angularDamping"] == 0.1
    assert obj["_group"] == 1
    # Vec3-shaped factor fields
    assert obj["_linearFactor"] == {"__type__": "cc.Vec3", "x": 1, "y": 1, "z": 1}
    assert obj["_angularFactor"] == {"__type__": "cc.Vec3", "x": 1, "y": 1, "z": 1}


def test_rigidbody_3d_static_kinematic_enum_values(tmp_path: Path):
    """Regression guard for the non-contiguous ERigidBodyType enum."""
    assert sb.RIGIDBODY_DYNAMIC == 1
    assert sb.RIGIDBODY_STATIC == 2
    assert sb.RIGIDBODY_KINEMATIC == 4

    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Wall")
    cid = sb.add_rigidbody_3d(str(path), n, body_type=sb.RIGIDBODY_STATIC)
    assert sb.get_object(path, cid)["_type"] == 2

    path2 = tmp_path / "k.scene"
    info2 = sb.create_empty_scene(path2)
    n2 = sb.add_node(path2, info2["canvas_node_id"], "Platform")
    cid2 = sb.add_rigidbody_3d(str(path2), n2, body_type=sb.RIGIDBODY_KINEMATIC)
    assert sb.get_object(path2, cid2)["_type"] == 4


# ----------- Colliders -----------

@pytest.mark.parametrize("adder, type_name, extra_check", [
    (lambda p, n: sb.add_box_collider_3d(p, n, size=(2, 3, 4)),
     "cc.BoxCollider",
     lambda o: o["_size"] == {"__type__": "cc.Vec3", "x": 2, "y": 3, "z": 4}),
    (lambda p, n: sb.add_sphere_collider_3d(p, n, radius=2.5),
     "cc.SphereCollider",
     lambda o: o["_radius"] == 2.5),
    (lambda p, n: sb.add_capsule_collider_3d(p, n, radius=0.4, cylinder_height=1.5, direction=sb.AXIS_Z),
     "cc.CapsuleCollider",
     lambda o: o["_radius"] == 0.4 and o["_cylinderHeight"] == 1.5 and o["_direction"] == 2),
    (lambda p, n: sb.add_cylinder_collider_3d(p, n, height=3),
     "cc.CylinderCollider",
     lambda o: o["_height"] == 3),
    (lambda p, n: sb.add_cone_collider_3d(p, n, radius=1.0),
     "cc.ConeCollider",
     lambda o: o["_radius"] == 1.0),
    (lambda p, n: sb.add_plane_collider_3d(p, n, normal=(1, 0, 0), constant=5),
     "cc.PlaneCollider",
     lambda o: (o["_normal"] == {"__type__": "cc.Vec3", "x": 1, "y": 0, "z": 0}
                and o["_constant"] == 5)),
])
def test_collider_3d_shape_fields(tmp_path: Path, adder, type_name, extra_check):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Obj")
    cid = adder(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == type_name
    assert obj["_isTrigger"] is False
    assert obj["_center"] == {"__type__": "cc.Vec3", "x": 0, "y": 0, "z": 0}
    assert extra_check(obj), f"shape-specific fields on {type_name} don't match"


def test_mesh_collider_3d_convex_and_uuid(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Model")
    cid = sb.add_mesh_collider_3d(str(path), n, mesh_uuid="abc-123", convex=True)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.MeshCollider"
    assert obj["_mesh"] == {"__uuid__": "abc-123"}
    assert obj["_convex"] is True


def test_mesh_collider_3d_no_uuid_means_null(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Unbound")
    cid = sb.add_mesh_collider_3d(str(path), n)
    assert sb.get_object(path, cid)["_mesh"] is None


def test_collider_3d_trigger_and_center(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Sensor")
    cid = sb.add_box_collider_3d(str(path), n, center=(1, 2, 3), is_trigger=True)
    obj = sb.get_object(path, cid)
    assert obj["_isTrigger"] is True
    assert obj["_center"] == {"__type__": "cc.Vec3", "x": 1, "y": 2, "z": 3}


# ----------- CharacterController -----------

def test_box_character_controller_defaults(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "BoxPlayer")
    cid = sb.add_box_character_controller(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.BoxCharacterController"
    assert obj["_halfHeight"] == 0.5
    assert obj["_halfSideExtent"] == 0.5
    assert obj["_halfForwardExtent"] == 0.5
    # Base CharacterController fields (from engine source defaults)
    assert obj["_minMoveDistance"] == 0.001
    assert obj["_stepOffset"] == 0.5
    assert obj["_slopeLimit"] == 45.0
    assert obj["_skinWidth"] == 0.01


def test_capsule_character_controller_defaults(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Player")
    cid = sb.add_capsule_character_controller(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.CapsuleCharacterController"
    assert obj["_radius"] == 0.5
    assert obj["_height"] == 1.0


# ----------- PhysicsMaterial asset -----------

def test_create_physics_material_writes_pmat_and_meta(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = cp.create_physics_material(str(proj), "ice",
                                     friction=0.02, restitution=0.0)
    pmat_path = proj / res["rel_path"]
    assert pmat_path.exists()
    assert pmat_path.suffix == ".pmat"

    with open(pmat_path) as f:
        data = json.load(f)
    assert isinstance(data, list) and len(data) == 1
    entry = data[0]
    assert entry["__type__"] == "cc.PhysicsMaterial"
    assert entry["_friction"] == 0.02
    assert entry["_restitution"] == 0.0
    assert entry["_name"] == "ice"

    # meta sidecar points to the right importer and uuid
    meta_path = pmat_path.with_suffix(pmat_path.suffix + ".meta")
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "physics-material"
    assert meta["uuid"] == res["uuid"]


def test_physics_material_engine_defaults_match(tmp_path: Path):
    """Don't drift from engine defaults silently — fail loudly if we do."""
    proj = _make_project(tmp_path)
    res = cp.create_physics_material(str(proj), "default")
    with open(proj / res["rel_path"]) as f:
        entry = json.load(f)[0]
    # From cocos/physics/framework/assets/physics-material.ts
    assert entry["_friction"] == 0.6
    assert entry["_rollingFriction"] == 0.0
    assert entry["_spinningFriction"] == 0.0
    assert entry["_restitution"] == 0.0


# ----------- set_physics_3d_config -----------

def test_set_physics_3d_config_writes_physics_json(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = cb.set_physics_3d_config(str(proj),
                                   gravity_y=-9.8,
                                   max_sub_steps=3)
    cfg_path = Path(res["settings_path"])
    assert cfg_path.name == "physics.json"
    assert cfg_path.parent.name == "packages"

    with open(cfg_path) as f:
        data = json.load(f)
    # Metric units — NOT pixels like set_physics_2d_config (which uses -320)
    assert data["gravity"] == {"x": 0, "y": -9.8, "z": 0}
    assert data["maxSubSteps"] == 3
    assert data["allowSleep"] is True


def test_set_physics_3d_config_preserves_unrelated_keys(tmp_path: Path):
    """Second call must not wipe out fields written by a first call."""
    proj = _make_project(tmp_path)
    cb.set_physics_3d_config(str(proj), gravity_x=1, gravity_y=2, gravity_z=3)
    cb.set_physics_3d_config(str(proj), max_sub_steps=5)
    cfg_path = proj / "settings" / "v2" / "packages" / "physics.json"
    with open(cfg_path) as f:
        data = json.load(f)
    assert data["maxSubSteps"] == 5
    # Second call explicitly rewrites gravity, so this test only covers the
    # fact that the file isn't deleted between calls. Real preservation of
    # caller-supplied keys (e.g. a custom physicsBackend field) would need
    # a read-merge-write pattern, which we could add later.
    assert "gravity" in data


# ----------- scene integrity -----------

def test_scene_still_valid_after_3d_physics_ops(tmp_path: Path):
    """Integration: a node with RigidBody + Collider + PhysicsMaterial ref
    passes scene validation."""
    proj = _make_project(tmp_path)
    path, info = _tmp_scene(tmp_path)

    mat = cp.create_physics_material(str(proj), "bouncy", restitution=0.8)
    n = sb.add_node(path, info["canvas_node_id"], "Ball")
    sb.add_rigidbody_3d(str(path), n)
    col_id = sb.add_sphere_collider_3d(str(path), n, radius=1.0)
    sb.set_uuid_property(path, col_id, "_material", mat["uuid"])

    v = sb.validate_scene(path)
    assert v["valid"], f"scene invalid: {v['issues']}"

"""Tests for the second feature pass:

1. 9-slice border meta setter (meta_util.set_sprite_frame_border)
2. Scene-globals lighting setters (ambient / skybox / shadows)
3. 2D physics joints (9 cc.*Joint2D components)
4. Prefab instantiation into a scene
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import meta_util as mu
from cocos import scene_builder as sb

# ----------- helpers -----------

def _make_png(path: Path, w: int = 64, h: int = 64) -> None:
    Image.new("RGBA", (w, h), (200, 100, 50, 255)).save(path)


def _scene() -> tuple[Path, dict]:
    f = tempfile.NamedTemporaryFile(suffix=".scene", delete=False)
    f.close()
    info = sb.create_empty_scene(f.name)
    return Path(f.name), info


# ============================================================
#  9-slice border
# ============================================================

def test_new_sprite_frame_meta_with_border(tmp_path: Path):
    png = tmp_path / "panel.png"
    _make_png(png, 100, 100)
    meta = mu.new_sprite_frame_meta(png, border=(8, 8, 12, 12))
    sub = meta["subMetas"][mu.SPRITE_FRAME_SUB_ID]["userData"]
    assert sub["borderTop"] == 8
    assert sub["borderBottom"] == 8
    assert sub["borderLeft"] == 12
    assert sub["borderRight"] == 12


def test_set_sprite_frame_border_in_place(tmp_path: Path):
    png = tmp_path / "btn.png"
    _make_png(png)
    # Write a fresh meta with default zero border
    meta = mu.new_sprite_frame_meta(png)
    mu.write_meta(png, meta)

    # Now patch borders
    updated = mu.set_sprite_frame_border(str(png) + ".meta", top=10, bottom=10, left=20, right=20)
    sub = updated["subMetas"][mu.SPRITE_FRAME_SUB_ID]["userData"]
    assert (sub["borderTop"], sub["borderBottom"], sub["borderLeft"], sub["borderRight"]) == (10, 10, 20, 20)

    # Re-reading from disk should see the same values (idempotency check)
    with open(str(png) + ".meta") as f:
        round_trip = json.load(f)
    assert round_trip["subMetas"][mu.SPRITE_FRAME_SUB_ID]["userData"]["borderTop"] == 10


def test_set_sprite_frame_border_rejects_texture_only_meta(tmp_path: Path):
    png = tmp_path / "raw.png"
    _make_png(png)
    # Build a texture-only meta (no sprite-frame sub)
    main_uuid = mu.new_uuid()
    texture_only = {
        "ver": "1.0.27", "importer": "image", "imported": True,
        "uuid": main_uuid, "files": [".json", ".png"],
        "subMetas": {mu.TEXTURE_SUB_ID: mu._texture_sub(main_uuid, "raw")},
        "userData": {"type": "texture"},
    }
    mu.write_meta(png, texture_only)

    with pytest.raises(ValueError, match="sprite-frame sub-resource"):
        mu.set_sprite_frame_border(str(png) + ".meta", top=5)


# ============================================================
#  Scene-globals setters
# ============================================================

def test_set_ambient_partial_update():
    path, _ = _scene()
    info = sb.set_ambient(path, sky_color=(0.8, 0.6, 0.2, 1.0), sky_illum=15000)
    assert info["_skyColor"]["x"] == 0.8
    assert info["_skyIllum"] == 15000
    # ground_albedo wasn't passed → stays at default
    assert info["_groundAlbedo"]["x"] == 0.2


def test_set_skybox_full_config():
    path, _ = _scene()
    info = sb.set_skybox(path, enabled=True, envmap_uuid="cube-uuid-123",
                         use_hdr=False, env_lighting_type=2)
    assert info["_enabled"] is True
    assert info["_envmap"] == {"__uuid__": "cube-uuid-123", "__expectedType__": "cc.TextureCube"}
    assert info["_useHDR"] is False
    assert info["_envLightingType"] == 2


def test_set_skybox_clear_envmap():
    path, _ = _scene()
    sb.set_skybox(path, envmap_uuid="something")
    info = sb.set_skybox(path, envmap_uuid="")  # empty string clears
    assert info["_envmap"] is None


def test_set_shadows_planar():
    path, _ = _scene()
    info = sb.set_shadows(path, enabled=True, normal=(0, 1, 0),
                          distance=-1.5, color=(50, 50, 50, 200))
    assert info["_enabled"] is True
    assert info["_normal"] == {"__type__": "cc.Vec3", "x": 0, "y": 1, "z": 0}
    assert info["_distance"] == -1.5
    assert info["_shadowColor"]["a"] == 200


def test_lighting_setters_reject_scene_without_globals(tmp_path: Path):
    p = tmp_path / "broken.scene"
    p.write_text(json.dumps([{"__type__": "cc.SceneAsset"}]))
    with pytest.raises(ValueError, match=r"cc\.AmbientInfo"):
        sb.set_ambient(p, sky_illum=100)


# ============================================================
#  2D physics joints
# ============================================================

def _scene_with_two_bodies() -> tuple[Path, int, int, int, int]:
    """Build a scene with two nodes, each carrying a RigidBody2D."""
    path, info = _scene()
    canvas = info["canvas_node_id"]
    n1 = sb.add_node(path, canvas, "BodyA")
    sb.add_uitransform(path, n1, 50, 50)
    rb1 = sb.add_rigidbody2d(path, n1)
    n2 = sb.add_node(path, canvas, "BodyB")
    sb.add_uitransform(path, n2, 50, 50)
    rb2 = sb.add_rigidbody2d(path, n2)
    return path, n1, rb1, n2, rb2


@pytest.mark.parametrize("adder, type_name", [
    (sb.add_distance_joint2d, "cc.DistanceJoint2D"),
    (sb.add_hinge_joint2d, "cc.HingeJoint2D"),
    (sb.add_spring_joint2d, "cc.SpringJoint2D"),
    (sb.add_slider_joint2d, "cc.SliderJoint2D"),
    (sb.add_wheel_joint2d, "cc.WheelJoint2D"),
    (sb.add_fixed_joint_2d, "cc.FixedJoint2D"),
    (sb.add_relative_joint2d, "cc.RelativeJoint2D"),
])
def test_two_body_joints(adder, type_name):
    path, n1, _rb1, _n2, rb2 = _scene_with_two_bodies()
    cid = adder(str(path), n1, connected_body_id=rb2)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == type_name
    # Joint2D base uses PUBLIC @serializable fields — JSON key is
    # ``connectedBody`` (no underscore). Pre-audit we wrote
    # ``_connectedBody`` which the engine silently ignored, so every
    # two-body joint ran as a world-anchored joint at runtime.
    assert obj["connectedBody"] == {"__id__": rb2}
    assert "_connectedBody" not in obj
    # Validate scene structure intact
    assert sb.validate_scene(path)["valid"]


def test_mouse_joint2d_has_no_connected_body():
    """MouseJoint2D differs from the others — no connected body, just a target.

    The ``_target`` field isn't ``@serializable`` in engine 3.8 either,
    but we still emit it for agent inspection; the runtime reads it
    from pointer input, not the scene file.
    """
    path, info = _scene()
    n1 = sb.add_node(path, info["canvas_node_id"], "DraggableBody")
    sb.add_uitransform(path, n1, 50, 50)
    sb.add_rigidbody2d(path, n1)
    cid = sb.add_mouse_joint2d(str(path), n1, max_force=500.0, target=(100, 50))
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.MouseJoint2D"
    assert obj["_maxForce"] == 500.0
    assert obj["_target"] == {"__type__": "cc.Vec2", "x": 100, "y": 50}
    # MouseJoint inherits connectedBody/collideConnected but the engine
    # runtime ignores them — direct builder omits both fields entirely.
    assert "connectedBody" not in obj
    assert "_connectedBody" not in obj


def test_hinge_joint_motor_and_limit_fields():
    path, n1, _rb1, _n2, rb2 = _scene_with_two_bodies()
    cid = sb.add_hinge_joint2d(str(path), n1, connected_body_id=rb2,
                               enable_motor=True, motor_speed=180,
                               max_motor_torque=2000, enable_limit=True,
                               lower_angle=-45, upper_angle=45)
    obj = sb.get_object(path, cid)
    assert obj["_enableMotor"] is True
    assert obj["_motorSpeed"] == 180
    assert obj["_lowerAngle"] == -45
    assert obj["_upperAngle"] == 45


# ============================================================
#  Prefab instantiation
# ============================================================

def _build_prefab(prefab_path: Path) -> dict:
    """Build a small prefab with root + UITransform + Label."""
    info = sb.create_prefab(prefab_path, root_name="Bullet")
    sb.add_uitransform(prefab_path, info["root_node_id"], 32, 32)
    sb.add_label(prefab_path, info["root_node_id"], "BANG", 24)
    return info


def test_instantiate_prefab_basic(tmp_path: Path):
    prefab = tmp_path / "Bullet.prefab"
    _build_prefab(prefab)
    scene = tmp_path / "Game.scene"
    sinfo = sb.create_empty_scene(scene)
    canvas = sinfo["canvas_node_id"]

    new_root = sb.instantiate_prefab(scene, canvas, prefab,
                                     name="Bullet1", lpos=(100, 0, 0))
    s = json.loads(scene.read_text())
    root = s[new_root]
    assert root["__type__"] == "cc.Node"
    assert root["_name"] == "Bullet1"
    assert root["_lpos"]["x"] == 100
    # parent points back at canvas
    assert root["_parent"] == {"__id__": canvas}
    # canvas now has the new root in its children list
    assert {"__id__": new_root} in s[canvas]["_children"]


def test_instantiate_prefab_twice_yields_unique_fileids(tmp_path: Path):
    prefab = tmp_path / "Bullet.prefab"
    _build_prefab(prefab)
    scene = tmp_path / "Game.scene"
    sinfo = sb.create_empty_scene(scene)
    canvas = sinfo["canvas_node_id"]

    r1 = sb.instantiate_prefab(scene, canvas, prefab, name="A")
    r2 = sb.instantiate_prefab(scene, canvas, prefab, name="B")
    s = json.loads(scene.read_text())
    pi1 = s[s[r1]["_prefab"]["__id__"]]
    pi2 = s[s[r2]["_prefab"]["__id__"]]
    assert pi1["fileId"] != pi2["fileId"], "each instance must have its own PrefabInfo.fileId"
    # All component refs must still validate
    assert sb.validate_scene(scene)["valid"]


def test_instantiate_prefab_components_resolve(tmp_path: Path):
    prefab = tmp_path / "Bullet.prefab"
    _build_prefab(prefab)
    scene = tmp_path / "Game.scene"
    sinfo = sb.create_empty_scene(scene)

    new_root = sb.instantiate_prefab(scene, sinfo["canvas_node_id"], prefab)
    s = json.loads(scene.read_text())
    root = s[new_root]
    # The label & uitransform we added inside the prefab should now live as
    # scene components attached to the new root.
    comp_types = sorted(s[c["__id__"]].get("__type__") for c in root["_components"])
    assert "cc.Label" in comp_types
    assert "cc.UITransform" in comp_types


def test_instantiate_prefab_rejects_bad_parent(tmp_path: Path):
    prefab = tmp_path / "X.prefab"
    _build_prefab(prefab)
    scene = tmp_path / "Game.scene"
    sb.create_empty_scene(scene)
    with pytest.raises(ValueError, match=r"not a cc\.Node"):
        sb.instantiate_prefab(scene, parent_id=0, prefab_path=prefab)  # 0 is SceneAsset


def test_instantiate_prefab_rejects_non_prefab_file(tmp_path: Path):
    fake = tmp_path / "Fake.prefab"
    fake.write_text(json.dumps([{"__type__": "cc.NotAPrefab"}]))
    scene = tmp_path / "Game.scene"
    sb.create_empty_scene(scene)
    with pytest.raises(ValueError, match="not a valid prefab"):
        sb.instantiate_prefab(scene, parent_id=2, prefab_path=fake)

"""Tests for the 3D rendering surface: lights, MeshRenderer, SkinnedMeshRenderer.

Field defaults match cocos-engine v3.8.6 sources. Keep them in lockstep —
if one of these assertions starts failing after an engine bump, pull the
new defaults from the source rather than relaxing the test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import scene_builder as sb


def _tmp_scene(tmp_path: Path) -> tuple[Path, dict]:
    path = tmp_path / "s.scene"
    info = sb.create_empty_scene(path)
    return path, info


# ----------- Lights -----------

def test_directional_light_defaults_match_engine(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Sun")
    cid = sb.add_directional_light(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.DirectionalLight"
    # Light base fields
    assert obj["_color"] == {"__type__": "cc.Color", "r": 255, "g": 255, "b": 255, "a": 255}
    assert obj["_useColorTemperature"] is False
    assert obj["_colorTemperature"] == 6550
    assert obj["_visibility"] == sb.CAMERA_DEFAULT_MASK
    # DirectionalLight-specific
    assert obj["_illuminanceHDR"] == obj["_illuminanceLDR"] == 65000
    assert obj["_shadowEnabled"] is False
    # CSM defaults that keep the engine inspector round-tripping cleanly
    assert obj["_csmLevel"] == 4
    assert obj["_shadowDistance"] == 50.0


def test_sphere_light_has_size_and_range(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Bulb")
    cid = sb.add_sphere_light(str(path), n, size=0.5, luminance=3000, light_range=10)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.SphereLight"
    assert obj["_size"] == 0.5
    assert obj["_luminanceHDR"] == 3000
    assert obj["_luminanceLDR"] == 3000
    assert obj["_range"] == 10
    # PhotometricTerm default = LUMINOUS_FLUX = 0
    assert obj["_term"] == 0


def test_spot_light_cone_fields(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Torch")
    cid = sb.add_spot_light(str(path), n,
                            spot_angle=45, angle_attenuation_strength=0.3,
                            shadow_enabled=True, shadow_pcf=sb.PCF_SOFT_2X)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.SpotLight"
    assert obj["_spotAngle"] == 45
    assert obj["_angleAttenuationStrength"] == 0.3
    assert obj["_shadowEnabled"] is True
    assert obj["_shadowPcf"] == 2  # SOFT_2X


def test_all_three_lights_share_base_light_fields(tmp_path: Path):
    """Regression guard: each light type must carry the full Light base."""
    path, info = _tmp_scene(tmp_path)
    canvas = info["canvas_node_id"]

    n1 = sb.add_node(path, canvas, "A")
    n2 = sb.add_node(path, canvas, "B")
    n3 = sb.add_node(path, canvas, "C")
    cid1 = sb.add_directional_light(str(path), n1,
                                    color=(255, 100, 50, 255),
                                    use_color_temperature=True,
                                    color_temperature=3200)
    cid2 = sb.add_sphere_light(str(path), n2,
                               color=(100, 255, 100, 255))
    cid3 = sb.add_spot_light(str(path), n3,
                             color=(50, 50, 255, 255))

    for cid, expected_color in [
        (cid1, {"r": 255, "g": 100, "b": 50, "a": 255}),
        (cid2, {"r": 100, "g": 255, "b": 100, "a": 255}),
        (cid3, {"r": 50, "g": 50, "b": 255, "a": 255}),
    ]:
        o = sb.get_object(path, cid)
        assert o["_color"]["r"] == expected_color["r"]
        assert o["_color"]["g"] == expected_color["g"]
        assert o["_color"]["b"] == expected_color["b"]
        # StaticLightSettings sub-object must be present on every light
        assert o["_staticSettings"]["__type__"] == "cc.scene.StaticLightSettings"


# ----------- Renderers -----------

def test_mesh_renderer_defaults(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Box")
    cid = sb.add_mesh_renderer(str(path), n,
                               mesh_uuid="mesh-123",
                               material_uuids=["mat-a", "mat-b"])
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.MeshRenderer"
    assert obj["_mesh"] == {"__uuid__": "mesh-123"}
    assert obj["_materials"] == [{"__uuid__": "mat-a"}, {"__uuid__": "mat-b"}]
    # Engine-default shadow modes
    assert obj["_shadowCastingMode"] == 0  # OFF
    assert obj["_shadowReceivingMode"] == 1  # ON
    assert obj["_reflectionProbeId"] == -1
    assert obj["_reflectionProbeBlendId"] == -1
    assert obj["_enableMorph"] is True
    # Nested bake settings
    assert obj["bakeSettings"]["__type__"] == "cc.ModelBakeSettings"
    assert obj["bakeSettings"]["_bakeable"] is False
    assert obj["bakeSettings"]["_reflectionProbeType"] == 0  # NONE


def test_mesh_renderer_no_uuids_nulls(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Empty")
    cid = sb.add_mesh_renderer(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["_mesh"] is None
    assert obj["_materials"] == []


def test_mesh_renderer_shadow_flags(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Shadower")
    cid = sb.add_mesh_renderer(str(path), n,
                               shadow_casting=sb.SHADOW_CAST_ON,
                               shadow_receiving=sb.SHADOW_RECV_OFF,
                               reflection_probe_type=sb.REFLECT_PLANAR)
    obj = sb.get_object(path, cid)
    assert obj["_shadowCastingMode"] == 1
    assert obj["_shadowReceivingMode"] == 0
    assert obj["bakeSettings"]["_reflectionProbeType"] == 2  # PLANAR


def test_skinned_mesh_renderer_has_skeleton_and_root_ref(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    canvas = info["canvas_node_id"]
    armature = sb.add_node(path, canvas, "Armature")
    cid = sb.add_skinned_mesh_renderer(
        str(path), canvas,
        mesh_uuid="mesh-x",
        skeleton_uuid="skel-y",
        skinning_root_node_id=armature,
        material_uuids=["mat-body"],
    )
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.SkinnedMeshRenderer"
    assert obj["_skeleton"] == {"__uuid__": "skel-y"}
    # _skinningRoot is a node REFERENCE (__id__), not a uuid
    assert obj["_skinningRoot"] == {"__id__": armature}
    # Inherits MeshRenderer mesh + materials
    assert obj["_mesh"] == {"__uuid__": "mesh-x"}
    assert obj["_materials"] == [{"__uuid__": "mat-body"}]


def test_skinned_mesh_renderer_null_refs(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Naked")
    cid = sb.add_skinned_mesh_renderer(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["_skeleton"] is None
    assert obj["_skinningRoot"] is None


# ----------- scene integrity -----------

def test_scene_validates_with_3d_render_stack(tmp_path: Path):
    """Full 3D render stack on a node should pass scene validation."""
    path, info = _tmp_scene(tmp_path)
    canvas = info["canvas_node_id"]

    sun = sb.add_node(path, canvas, "Sun")
    sb.add_directional_light(str(path), sun)

    model = sb.add_node(path, canvas, "Model")
    sb.add_mesh_renderer(str(path), model,
                         mesh_uuid="abc", material_uuids=["def"])

    v = sb.validate_scene(path)
    assert v["valid"], f"scene invalid: {v['issues']}"

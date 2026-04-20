"""3D rendering components — three light types, MeshRenderer, SkinnedMeshRenderer.

Defaults match ``cocos-engine v3.8.6`` sources exactly:

* ``cocos/3d/lights/{directional,sphere,spot}-light-component.ts``
* ``cocos/misc/renderer.ts`` (the ``_materials`` array)
* ``cocos/3d/framework/mesh-renderer.ts``
* ``cocos/3d/skinned-mesh-renderer/skinned-mesh-renderer.ts``

All three lights inherit a common base (``cc.Light``) that carries colour,
temperature, and visibility. Every field on lights/renderers has HDR and
LDR counterparts — the engine switches which one is used at runtime based
on the pipeline, but both must be present in the serialized scene or the
asset refuses to load.

Shadow / CSM / reflection-probe defaults preserve the Cocos inspector
"just works" behavior: shadows off, no reflection probe, one unshadowed
cascade. Callers who want rich lighting should set the shadow flags and
reflection-probe-id after attaching.

The late ``add_component`` import inside each function keeps the load
graph acyclic with ``scene_builder.__init__``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._helpers import (
    _color,
    _make_uitransform,  # noqa: F401 — imported for downstream convenience
    _ref,
    _vec3,
)

# ModelShadowCastingMode / ReceivingMode (engine uses 0/1)
SHADOW_CAST_OFF = 0
SHADOW_CAST_ON = 1
SHADOW_RECV_OFF = 0
SHADOW_RECV_ON = 1

# PCFType
PCF_HARD = 0
PCF_SOFT = 1
PCF_SOFT_2X = 2
PCF_SOFT_4X = 3

# ReflectionProbeType
REFLECT_NONE = 0
REFLECT_BAKED_CUBEMAP = 1
REFLECT_PLANAR = 2
REFLECT_BLEND = 3

# Default camera visibility mask — the Light.base class stores this as
# _visibility. Matches engine's CAMERA_DEFAULT_MASK so a plain-attached
# light actually lights the default scene.
CAMERA_DEFAULT_MASK = 0x3FFFFFFF


def _make_static_light_settings() -> dict:
    """Default StaticLightSettings sub-object embedded in every Light."""
    return {
        "__type__": "cc.scene.StaticLightSettings",
        "_editorOnly": False,
        "_castShadow": False,
    }


def _make_light_base(color: tuple, use_color_temperature: bool,
                     color_temperature: float, visibility: int) -> dict:
    """Base Light @serializable fields shared by directional/sphere/spot."""
    return {
        "_color": _color(*color),
        "_useColorTemperature": use_color_temperature,
        "_colorTemperature": color_temperature,
        "_staticSettings": _make_static_light_settings(),
        "_visibility": visibility,
    }


# ----------- lights -----------

def add_directional_light(scene_path: str | Path, node_id: int,
                          color: tuple = (255, 255, 255, 255),
                          illuminance: float = 65000,
                          use_color_temperature: bool = False,
                          color_temperature: float = 6550,
                          shadow_enabled: bool = False,
                          shadow_pcf: int = PCF_HARD,
                          shadow_distance: float = 50.0,
                          csm_level: int = 4,
                          visibility: int = CAMERA_DEFAULT_MASK) -> int:
    """Attach cc.DirectionalLight — sun/moon-style parallel light.

    ``illuminance`` is in lux. Engine stores both HDR and LDR values; we
    write the same number to both which is how a fresh inspector-created
    light serializes.
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = _make_light_base(color, use_color_temperature,
                                             color_temperature, visibility)
    props.update({
        "_illuminanceHDR": illuminance,
        "_illuminanceLDR": illuminance,
        "_shadowEnabled": shadow_enabled,
        "_shadowPcf": shadow_pcf,
        "_shadowBias": 0.00001,
        "_shadowNormalBias": 0.0,
        "_shadowSaturation": 1.0,
        "_shadowDistance": shadow_distance,
        "_shadowInvisibleOcclusionRange": 200,
        "_csmLevel": csm_level,
        "_csmLayerLambda": 0.75,
        "_csmOptimizationMode": 2,
        "_csmAdvancedOptions": False,
        "_csmLayersTransition": False,
        "_csmTransitionRange": 0.05,
        "_shadowFixedArea": False,
        "_shadowNear": 0.1,
        "_shadowFar": 10.0,
        "_shadowOrthoSize": 5.0,
    })
    return add_component(scene_path, node_id, "cc.DirectionalLight", props)


def add_sphere_light(scene_path: str | Path, node_id: int,
                     color: tuple = (255, 255, 255, 255),
                     size: float = 0.15,
                     luminance: float = 1700,
                     light_range: float = 1.0,
                     term: int = 0,
                     use_color_temperature: bool = False,
                     color_temperature: float = 6550,
                     visibility: int = CAMERA_DEFAULT_MASK) -> int:
    """Attach cc.SphereLight — point-light with a physical size.

    ``term``: 0=LUMINOUS_FLUX (default), 1=LUMINANCE. Determines how the
    luminance number is interpreted when computing exposure.
    ``light_range`` maps to ``_range``; use small values (1-5) for
    localized lighting, large (50+) for area fills.
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = _make_light_base(color, use_color_temperature,
                                             color_temperature, visibility)
    props.update({
        "_size": size,
        "_luminanceHDR": luminance,
        "_luminanceLDR": luminance,
        "_term": term,
        "_range": light_range,
    })
    return add_component(scene_path, node_id, "cc.SphereLight", props)


def add_spot_light(scene_path: str | Path, node_id: int,
                   color: tuple = (255, 255, 255, 255),
                   size: float = 0.15,
                   luminance: float = 1700,
                   light_range: float = 1.0,
                   spot_angle: float = 60.0,
                   angle_attenuation_strength: float = 0.0,
                   term: int = 0,
                   shadow_enabled: bool = False,
                   shadow_pcf: int = PCF_HARD,
                   use_color_temperature: bool = False,
                   color_temperature: float = 6550,
                   visibility: int = CAMERA_DEFAULT_MASK) -> int:
    """Attach cc.SpotLight — cone-of-light source (torch, stage spotlight)."""
    from cocos.scene_builder import add_component
    props: dict[str, Any] = _make_light_base(color, use_color_temperature,
                                             color_temperature, visibility)
    props.update({
        "_size": size,
        "_luminanceHDR": luminance,
        "_luminanceLDR": luminance,
        "_term": term,
        "_range": light_range,
        "_spotAngle": spot_angle,
        "_angleAttenuationStrength": angle_attenuation_strength,
        "_shadowEnabled": shadow_enabled,
        "_shadowPcf": shadow_pcf,
        "_shadowBias": 0.00001,
        "_shadowNormalBias": 0.0,
    })
    return add_component(scene_path, node_id, "cc.SpotLight", props)


# ----------- renderers -----------

def _make_bake_settings() -> dict:
    """Default ModelBakeSettings sub-object embedded in every MeshRenderer."""
    return {
        "__type__": "cc.ModelBakeSettings",
        "_bakeable": False,
        "_castShadow": False,
        "_receiveShadow": False,
        "_lightmapSize": 64,
        "_useLightProbe": False,
        "_bakeToLightProbe": True,
        "_reflectionProbeType": REFLECT_NONE,
        "_bakeToReflectionProbe": True,
    }


def add_mesh_renderer(scene_path: str | Path, node_id: int,
                     mesh_uuid: str | None = None,
                     material_uuids: list[str] | None = None,
                     shadow_casting: int = SHADOW_CAST_OFF,
                     shadow_receiving: int = SHADOW_RECV_ON,
                     reflection_probe_type: int = REFLECT_NONE,
                     enable_morph: bool = True) -> int:
    """Attach cc.MeshRenderer.

    ``mesh_uuid``: UUID of a cc.Mesh asset (from add_image-style importer
    after a model import, or a third-party .fbx/.gltf conversion). Pass
    None to attach an empty MeshRenderer that you'll wire later via
    cocos_set_uuid_property(id, "_mesh", uuid).

    ``material_uuids``: list of cc.Material UUIDs, one per submesh.
    Order matters — submesh 0 uses material[0], etc.
    """
    from cocos.scene_builder import add_component
    materials = [{"__uuid__": u} if u else None for u in (material_uuids or [])]
    bake = _make_bake_settings()
    bake["_reflectionProbeType"] = reflection_probe_type
    props: dict[str, Any] = {
        "_materials": materials,
        "_visFlags": 0,
        "_mesh": {"__uuid__": mesh_uuid} if mesh_uuid else None,
        "_shadowCastingMode": shadow_casting,
        "_shadowReceivingMode": shadow_receiving,
        "_shadowBias": 0,
        "_shadowNormalBias": 0,
        "_reflectionProbeId": -1,
        "_reflectionProbeBlendId": -1,
        "_reflectionProbeBlendWeight": 0,
        "bakeSettings": bake,
        "_enableMorph": enable_morph,
    }
    return add_component(scene_path, node_id, "cc.MeshRenderer", props)


def add_skinned_mesh_renderer(scene_path: str | Path, node_id: int,
                              mesh_uuid: str | None = None,
                              skeleton_uuid: str | None = None,
                              skinning_root_node_id: int | None = None,
                              material_uuids: list[str] | None = None,
                              shadow_casting: int = SHADOW_CAST_OFF,
                              shadow_receiving: int = SHADOW_RECV_ON) -> int:
    """Attach cc.SkinnedMeshRenderer — MeshRenderer + skeleton binding.

    ``skeleton_uuid`` points to a cc.Skeleton asset. ``skinning_root_node_id``
    is the scene-array index of the Node under which the skeleton's bone
    hierarchy lives (typically the armature root node created during
    model import).
    """
    from cocos.scene_builder import add_component
    materials = [{"__uuid__": u} if u else None for u in (material_uuids or [])]
    props: dict[str, Any] = {
        "_materials": materials,
        "_visFlags": 0,
        "_mesh": {"__uuid__": mesh_uuid} if mesh_uuid else None,
        "_shadowCastingMode": shadow_casting,
        "_shadowReceivingMode": shadow_receiving,
        "_shadowBias": 0,
        "_shadowNormalBias": 0,
        "_reflectionProbeId": -1,
        "_reflectionProbeBlendId": -1,
        "_reflectionProbeBlendWeight": 0,
        "bakeSettings": _make_bake_settings(),
        "_enableMorph": True,
        "_skeleton": {"__uuid__": skeleton_uuid} if skeleton_uuid else None,
        "_skinningRoot": _ref(skinning_root_node_id) if skinning_root_node_id is not None else None,
    }
    return add_component(scene_path, node_id, "cc.SkinnedMeshRenderer", props)

"""Media + scene-lighting — audio, animation, particles, camera, skeletal
animation (Spine + DragonBones), TiledMap, VideoPlayer, plus the
set-ambient / set-skybox / set-shadows scene-globals mutators.

Why they live together: each is a "component attached to a node that
references an external asset UUID" (audio clip, spine json, tmx map, ...)
plus the scene-globals setters that configure the same render pipeline.

The late ``add_component`` import inside each function keeps the load
graph acyclic — ``__init__.py`` re-exports from this module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._helpers import (
    _color,
    _load_scene,
    _rect,
    _save_scene,
    _vec3,
    _vec4,
)


# ----------- audio -----------

def add_audio_source(scene_path: str | Path, node_id: int,
                     clip_uuid: str | None = None,
                     play_on_awake: bool = False, loop: bool = False,
                     volume: float = 1.0) -> int:
    """Attach cc.AudioSource."""
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {
        "playOnAwake": play_on_awake,
        "loop": loop,
        "volume": volume,
    }
    if clip_uuid:
        props["_clip"] = {"__uuid__": clip_uuid}
    return add_component(scene_path, node_id, "cc.AudioSource", props)


# ----------- animation -----------

def add_animation(scene_path: str | Path, node_id: int,
                  default_clip_uuid: str | None = None,
                  play_on_load: bool = True,
                  clip_uuids: list[str] | None = None) -> int:
    """Attach cc.Animation."""
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {
        "playOnLoad": play_on_load,
        "_clips": [],
    }
    if default_clip_uuid:
        props["_defaultClip"] = {"__uuid__": default_clip_uuid}
    if clip_uuids:
        props["_clips"] = [{"__uuid__": u} for u in clip_uuids]
    return add_component(scene_path, node_id, "cc.Animation", props)


# ----------- particle -----------

def add_particle_system_2d(scene_path: str | Path, node_id: int,
                           duration: float = -1, emission_rate: float = 10,
                           life: float = 1, life_var: float = 0,
                           total_particles: int = 150,
                           start_color: tuple = (255, 255, 255, 255),
                           end_color: tuple = (255, 255, 255, 0),
                           angle: float = 90, angle_var: float = 360,
                           speed: float = 180, speed_var: float = 50,
                           gravity_x: float = 0, gravity_y: float = 0,
                           start_size: float = 50, start_size_var: float = 0,
                           end_size: float = 0, end_size_var: float = 0,
                           emitter_mode: int = 0) -> int:
    """Attach cc.ParticleSystem2D."""
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.ParticleSystem2D", {
        "duration": duration,
        "emissionRate": emission_rate,
        "life": life,
        "lifeVar": life_var,
        "totalParticles": total_particles,
        "_startColor": list(start_color),
        "_endColor": list(end_color),
        "angle": angle,
        "angleVar": angle_var,
        "speed": speed,
        "speedVar": speed_var,
        "gravity": [gravity_x, gravity_y],
        "startSize": start_size,
        "startSizeVar": start_size_var,
        "endSize": end_size,
        "endSizeVar": end_size_var,
        "emitterMode": emitter_mode,
        "positionType": 0,
    })


# ----------- camera -----------

def add_camera(scene_path: str | Path, node_id: int,
               projection: int = 0, priority: int = 0,
               ortho_height: float = 320, fov: float = 45,
               near: float = 1, far: float = 2000,
               clear_color: tuple = (0, 0, 0, 255),
               clear_flags: int = 7,
               visibility: int = 41943040) -> int:
    """Attach cc.Camera. projection: 0=ORTHO, 1=PERSPECTIVE.

    Use this for secondary cameras (minimap, split-screen). The default
    camera created by cocos_create_scene has priority=1073741824.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.Camera", {
        "_projection": projection,
        "_priority": priority,
        "_fov": fov,
        "_fovAxis": 0,
        "_orthoHeight": ortho_height,
        "_near": near,
        "_far": far,
        "_color": _color(*clear_color),
        "_depth": 1,
        "_stencil": 0,
        "_clearFlags": clear_flags,
        "_rect": _rect(0, 0, 1, 1),
        "_aperture": 19,
        "_shutter": 7,
        "_iso": 0,
        "_screenScale": 1,
        "_visibility": visibility,
        "_targetTexture": None,
        "_cameraType": -1,
        "_trackingType": 0,
    })


# ----------- skeletal animation -----------

def add_spine(scene_path: str | Path, node_id: int,
              skeleton_data_uuid: str | None = None,
              default_skin: str = "default",
              default_animation: str = "",
              loop: bool = True,
              premultiplied_alpha: bool = True,
              time_scale: float = 1.0) -> int:
    """Attach sp.Skeleton (Spine skeletal animation component).

    `skeleton_data_uuid` is the UUID of the .json spine data asset.
    Set via cocos_add_spine_data() or cocos_set_uuid_property() later.
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {
        "defaultSkin": default_skin,
        "defaultAnimation": default_animation,
        "loop": loop,
        "premultipliedAlpha": premultiplied_alpha,
        "timeScale": time_scale,
        "_preCacheMode": 0,
        "_cacheMode": 0,
    }
    if skeleton_data_uuid:
        props["_N$skeletonData"] = {"__uuid__": skeleton_data_uuid}
    return add_component(scene_path, node_id, "sp.Skeleton", props)


def add_dragonbones(scene_path: str | Path, node_id: int,
                    dragon_asset_uuid: str | None = None,
                    dragon_atlas_asset_uuid: str | None = None,
                    armature_name: str = "",
                    animation_name: str = "",
                    play_times: int = -1,
                    time_scale: float = 1.0) -> int:
    """Attach dragonBones.ArmatureDisplay (DragonBones skeletal animation).

    `dragon_asset_uuid` is the UUID of the DragonBones JSON data.
    `dragon_atlas_asset_uuid` is the UUID of the texture atlas JSON.
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {
        "_armatureName": armature_name,
        "_animationName": animation_name,
        "playTimes": play_times,
        "timeScale": time_scale,
    }
    if dragon_asset_uuid:
        props["_N$dragonAsset"] = {"__uuid__": dragon_asset_uuid}
    if dragon_atlas_asset_uuid:
        props["_N$dragonAtlasAsset"] = {"__uuid__": dragon_atlas_asset_uuid}
    return add_component(scene_path, node_id, "dragonBones.ArmatureDisplay", props)


# ----------- tiled map -----------

def add_tiled_map(scene_path: str | Path, node_id: int,
                  tmx_asset_uuid: str | None = None) -> int:
    """Attach cc.TiledMap component.

    `tmx_asset_uuid` is the UUID of the .tmx TiledMap asset.
    Import the .tmx file via cocos_add_tiled_map_asset() first.
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {}
    if tmx_asset_uuid:
        props["_tmxAsset"] = {"__uuid__": tmx_asset_uuid}
    return add_component(scene_path, node_id, "cc.TiledMap", props)


def add_tiled_layer(scene_path: str | Path, node_id: int,
                    layer_name: str = "") -> int:
    """Attach cc.TiledLayer. Usually auto-created by TiledMap, but can be
    added manually for custom layer control."""
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.TiledLayer", {
        "_layerName": layer_name,
    })


# ----------- video -----------

def add_video_player(scene_path: str | Path, node_id: int,
                     resource_type: int = 1,
                     remote_url: str = "",
                     clip_uuid: str | None = None,
                     play_on_awake: bool = True,
                     volume: float = 1.0,
                     mute: bool = False,
                     loop: bool = False,
                     keep_aspect_ratio: bool = True,
                     full_screen_on_awake: bool = False,
                     stay_on_bottom: bool = False) -> int:
    """Attach cc.VideoPlayer — plays mp4 from a local cc.VideoClip asset or a remote URL.

    resource_type: 0=REMOTE (use remote_url), 1=LOCAL (use clip_uuid).

    Common uses: cinematic intro, in-game cutscenes, rewarded video ads.
    Note: WeChat mini-game uses a native overlay; stay_on_bottom + the
    full screen flag affect platform-specific rendering behavior.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.VideoPlayer", {
        "_resourceType": resource_type,
        "_remoteURL": remote_url,
        "_clip": {"__uuid__": clip_uuid, "__expectedType__": "cc.VideoClip"} if clip_uuid else None,
        "_playOnAwake": play_on_awake,
        "_volume": volume,
        "_mute": mute,
        "_loop": loop,
        "_keepAspectRatio": keep_aspect_ratio,
        "_fullScreenOnAwake": full_screen_on_awake,
        "_stayOnBottom": stay_on_bottom,
    })


# ================================================================
#  Scene-globals setters: ambient, skybox, shadows
# ================================================================
#
# Every scene built via create_empty_scene has a SceneGlobals object that
# holds three sub-objects: AmbientInfo, SkyboxInfo, ShadowsInfo. To configure
# lighting after creation you mutate those sub-objects in place — but their
# array indices aren't fixed in user-edited scenes, so we look them up by
# component __type__ rather than hard-coding a position.

def _find_global_info(s: list, type_name: str) -> int | None:
    """Locate a singleton scene-globals component (cc.AmbientInfo etc.) by type."""
    for i, obj in enumerate(s):
        if isinstance(obj, dict) and obj.get("__type__") == type_name:
            return i
    return None


def set_ambient(scene_path: str | Path,
                sky_color: tuple | None = None,
                sky_illum: float | None = None,
                ground_albedo: tuple | None = None) -> dict:
    """Set ambient lighting on the scene's cc.AmbientInfo.

    Each arg is optional — pass None to leave that field unchanged.
      sky_color, ground_albedo: (r, g, b, a) floats 0-1 (NOT 0-255).
      sky_illum: lux value, default 20000 in a fresh scene.

    Returns the updated AmbientInfo dict.
    """
    s = _load_scene(scene_path)
    idx = _find_global_info(s, "cc.AmbientInfo")
    if idx is None:
        raise ValueError("scene has no cc.AmbientInfo (was it created via create_empty_scene?)")
    info = s[idx]
    if sky_color is not None:
        info["_skyColor"] = _vec4(*sky_color)
        info["_skyColorLDR"] = _vec4(*sky_color)
        info["_skyColorHDR"] = _vec4(*sky_color)
    if sky_illum is not None:
        info["_skyIllum"] = sky_illum
        info["_skyIllumHDR"] = sky_illum
    if ground_albedo is not None:
        info["_groundAlbedo"] = _vec4(*ground_albedo)
        info["_groundAlbedoLDR"] = _vec4(*ground_albedo)
        info["_groundAlbedoHDR"] = _vec4(*ground_albedo)
    _save_scene(scene_path, s)
    return info


def set_skybox(scene_path: str | Path,
               enabled: bool | None = None,
               envmap_uuid: str | None = None,
               use_hdr: bool | None = None,
               env_lighting_type: int | None = None) -> dict:
    """Set skybox on the scene's cc.SkyboxInfo.

      env_lighting_type: 0=HEMISPHERE_DIFFUSE, 1=AUTOGEN_HEMISPHERE_DIFFUSE, 2=DIFFUSEMAP_WITH_REFLECTION.
      envmap_uuid: cc.TextureCube uuid; pass empty string "" to clear.

    Each arg is optional. Returns the updated SkyboxInfo dict.
    """
    s = _load_scene(scene_path)
    idx = _find_global_info(s, "cc.SkyboxInfo")
    if idx is None:
        raise ValueError("scene has no cc.SkyboxInfo")
    info = s[idx]
    if enabled is not None:
        info["_enabled"] = enabled
    if envmap_uuid is not None:
        ref = {"__uuid__": envmap_uuid, "__expectedType__": "cc.TextureCube"} if envmap_uuid else None
        info["_envmap"] = ref
        info["_envmapHDR"] = ref
        info["_envmapLDR"] = ref
    if use_hdr is not None:
        info["_useHDR"] = use_hdr
    if env_lighting_type is not None:
        info["_envLightingType"] = env_lighting_type
    _save_scene(scene_path, s)
    return info


def set_shadows(scene_path: str | Path,
                enabled: bool | None = None,
                normal: tuple | None = None,
                distance: float | None = None,
                color: tuple | None = None) -> dict:
    """Set planar shadows on the scene's cc.ShadowsInfo.

      normal: (x, y, z) shadow plane normal, default (0, 1, 0) for ground.
      distance: signed offset along normal from origin.
      color: (r, g, b, a) ints 0-255.

    Each arg is optional. Returns the updated ShadowsInfo dict.
    """
    s = _load_scene(scene_path)
    idx = _find_global_info(s, "cc.ShadowsInfo")
    if idx is None:
        raise ValueError("scene has no cc.ShadowsInfo")
    info = s[idx]
    if enabled is not None:
        info["_enabled"] = enabled
    if normal is not None:
        info["_normal"] = _vec3(*normal)
    if distance is not None:
        info["_distance"] = distance
    if color is not None:
        info["_shadowColor"] = _color(*color)
    _save_scene(scene_path, s)
    return info

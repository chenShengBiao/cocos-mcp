"""3D rendering MCP tools — three light types + MeshRenderer + SkinnedMeshRenderer.

Flat tuple→params conversion for each tool (MCP schemas prefer primitives
over nested list/dict args so the LLM doesn't have to guess structure).
Defaults taken from ``cocos-engine v3.8.6`` sources.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import scene_builder as sb

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- Lights ----------------

    @mcp.tool()
    def cocos_add_directional_light(scene_path: str, node_id: int,
                                    color_r: int = 255, color_g: int = 255,
                                    color_b: int = 255, color_a: int = 255,
                                    illuminance: float = 65000,
                                    use_color_temperature: bool = False,
                                    color_temperature: float = 6550,
                                    shadow_enabled: bool = False,
                                    shadow_pcf: int = 0,
                                    shadow_distance: float = 50.0,
                                    csm_level: int = 4) -> int:
        """Attach cc.DirectionalLight — sun/moon parallel light.

        ``illuminance`` is in lux (default 65000 ≈ midday sun).
        ``shadow_pcf``: 0=HARD, 1=SOFT, 2=SOFT_2X, 3=SOFT_4X.
        A scene typically has exactly one directional light.
        """
        return sb.add_directional_light(scene_path, node_id,
                                        (color_r, color_g, color_b, color_a),
                                        illuminance, use_color_temperature,
                                        color_temperature, shadow_enabled,
                                        shadow_pcf, shadow_distance, csm_level)

    @mcp.tool()
    def cocos_add_sphere_light(scene_path: str, node_id: int,
                               color_r: int = 255, color_g: int = 255,
                               color_b: int = 255, color_a: int = 255,
                               size: float = 0.15,
                               luminance: float = 1700,
                               light_range: float = 1.0,
                               term: int = 0,
                               use_color_temperature: bool = False,
                               color_temperature: float = 6550) -> int:
        """Attach cc.SphereLight — point-light with physical size (bulb, lantern).

        ``term``: 0=LUMINOUS_FLUX (default), 1=LUMINANCE.
        ``light_range`` is the falloff distance.
        """
        return sb.add_sphere_light(scene_path, node_id,
                                   (color_r, color_g, color_b, color_a),
                                   size, luminance, light_range, term,
                                   use_color_temperature, color_temperature)

    @mcp.tool()
    def cocos_add_spot_light(scene_path: str, node_id: int,
                             color_r: int = 255, color_g: int = 255,
                             color_b: int = 255, color_a: int = 255,
                             size: float = 0.15,
                             luminance: float = 1700,
                             light_range: float = 1.0,
                             spot_angle: float = 60.0,
                             angle_attenuation_strength: float = 0.0,
                             term: int = 0,
                             shadow_enabled: bool = False,
                             shadow_pcf: int = 0,
                             use_color_temperature: bool = False,
                             color_temperature: float = 6550) -> int:
        """Attach cc.SpotLight — cone-shaped light (torch, stage spot)."""
        return sb.add_spot_light(scene_path, node_id,
                                 (color_r, color_g, color_b, color_a),
                                 size, luminance, light_range, spot_angle,
                                 angle_attenuation_strength, term,
                                 shadow_enabled, shadow_pcf,
                                 use_color_temperature, color_temperature)

    # ---------------- MeshRenderer ----------------

    @mcp.tool()
    def cocos_add_mesh_renderer(scene_path: str, node_id: int,
                                mesh_uuid: str | None = None,
                                material_uuids: list[str] | None = None,
                                shadow_casting: int = 0,
                                shadow_receiving: int = 1,
                                reflection_probe_type: int = 0,
                                enable_morph: bool = True) -> int:
        """Attach cc.MeshRenderer — renders a 3D mesh.

        ``material_uuids``: one per submesh; order matters. Pass None to
        wire later via cocos_set_uuid_property(id, "_mesh", uuid).
        ``shadow_casting``: 0=OFF (default), 1=ON.
        ``shadow_receiving``: 0=OFF, 1=ON (default).
        ``reflection_probe_type``: 0=NONE, 1=BAKED_CUBEMAP, 2=PLANAR, 3=BLEND.
        """
        return sb.add_mesh_renderer(scene_path, node_id, mesh_uuid, material_uuids,
                                    shadow_casting, shadow_receiving,
                                    reflection_probe_type, enable_morph)

    @mcp.tool()
    def cocos_add_skinned_mesh_renderer(scene_path: str, node_id: int,
                                        mesh_uuid: str | None = None,
                                        skeleton_uuid: str | None = None,
                                        skinning_root_node_id: int | None = None,
                                        material_uuids: list[str] | None = None,
                                        shadow_casting: int = 0,
                                        shadow_receiving: int = 1) -> int:
        """Attach cc.SkinnedMeshRenderer — MeshRenderer driven by a skeleton.

        Use this for humanoid/animal characters imported from GLTF/FBX.
        ``skinning_root_node_id`` is the scene-array index of the armature
        root node created during model import (pass the Node id, not a UUID).
        """
        return sb.add_skinned_mesh_renderer(scene_path, node_id, mesh_uuid,
                                            skeleton_uuid, skinning_root_node_id,
                                            material_uuids, shadow_casting,
                                            shadow_receiving)

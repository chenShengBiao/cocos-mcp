"""3D physics MCP tools — RigidBody, 8 colliders, 2 CharacterControllers,
plus ``PhysicsMaterial`` asset creation.

Defaults match ``cocos-engine v3.8.6`` source. ``ERigidBodyType`` uses
non-contiguous ints (DYNAMIC=1, STATIC=2, KINEMATIC=4) — exposed as the
``body_type`` parameter default and documented in the tool descriptions
so LLM callers don't guess 0.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import project as cp
from cocos import scene_builder as sb

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- 3D RigidBody ----------------

    @mcp.tool()
    def cocos_add_rigidbody_3d(scene_path: str, node_id: int,
                               body_type: int = 1,
                               mass: float = 1.0,
                               use_gravity: bool = True,
                               allow_sleep: bool = True,
                               linear_damping: float = 0.1,
                               angular_damping: float = 0.1,
                               linear_factor_x: float = 1, linear_factor_y: float = 1, linear_factor_z: float = 1,
                               angular_factor_x: float = 1, angular_factor_y: float = 1, angular_factor_z: float = 1,
                               group: int = 1) -> int:
        """Attach cc.RigidBody (3D).

        body_type: 1=DYNAMIC (default), 2=STATIC, 4=KINEMATIC. Values are
        engine's ERigidBodyType bitmask, NOT contiguous 0/1/2 like the 2D API.
        linear_factor / angular_factor lock motion on a per-axis basis (set
        component to 0 to freeze that axis, 1 for free movement).
        """
        return sb.add_rigidbody_3d(scene_path, node_id, body_type, mass,
                                   use_gravity, allow_sleep,
                                   linear_damping, angular_damping,
                                   (linear_factor_x, linear_factor_y, linear_factor_z),
                                   (angular_factor_x, angular_factor_y, angular_factor_z),
                                   group)

    # ---------------- 3D Colliders ----------------

    @mcp.tool()
    def cocos_add_box_collider_3d(scene_path: str, node_id: int,
                                  size_x: float = 1, size_y: float = 1, size_z: float = 1,
                                  center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                  is_trigger: bool = False) -> int:
        """Attach cc.BoxCollider (3D AABB shape)."""
        return sb.add_box_collider_3d(scene_path, node_id,
                                      (size_x, size_y, size_z),
                                      (center_x, center_y, center_z),
                                      is_trigger)

    @mcp.tool()
    def cocos_add_sphere_collider_3d(scene_path: str, node_id: int,
                                     radius: float = 0.5,
                                     center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                     is_trigger: bool = False) -> int:
        """Attach cc.SphereCollider (3D sphere shape)."""
        return sb.add_sphere_collider_3d(scene_path, node_id, radius,
                                         (center_x, center_y, center_z), is_trigger)

    @mcp.tool()
    def cocos_add_capsule_collider_3d(scene_path: str, node_id: int,
                                      radius: float = 0.5,
                                      cylinder_height: float = 1.0,
                                      direction: int = 1,
                                      center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                      is_trigger: bool = False) -> int:
        """Attach cc.CapsuleCollider. direction: 0=X, 1=Y (default), 2=Z."""
        return sb.add_capsule_collider_3d(scene_path, node_id, radius, cylinder_height,
                                          direction,
                                          (center_x, center_y, center_z), is_trigger)

    @mcp.tool()
    def cocos_add_cylinder_collider_3d(scene_path: str, node_id: int,
                                       radius: float = 0.5,
                                       height: float = 2.0,
                                       direction: int = 1,
                                       center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                       is_trigger: bool = False) -> int:
        """Attach cc.CylinderCollider."""
        return sb.add_cylinder_collider_3d(scene_path, node_id, radius, height,
                                           direction,
                                           (center_x, center_y, center_z), is_trigger)

    @mcp.tool()
    def cocos_add_cone_collider_3d(scene_path: str, node_id: int,
                                   radius: float = 0.5,
                                   height: float = 1.0,
                                   direction: int = 1,
                                   center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                   is_trigger: bool = False) -> int:
        """Attach cc.ConeCollider."""
        return sb.add_cone_collider_3d(scene_path, node_id, radius, height, direction,
                                       (center_x, center_y, center_z), is_trigger)

    @mcp.tool()
    def cocos_add_plane_collider_3d(scene_path: str, node_id: int,
                                    normal_x: float = 0, normal_y: float = 1, normal_z: float = 0,
                                    constant: float = 0.0,
                                    center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                    is_trigger: bool = False) -> int:
        """Attach cc.PlaneCollider — infinite plane, typically used for the ground.

        Default normal (0, 1, 0) + constant 0 means the XZ plane at y=0.
        """
        return sb.add_plane_collider_3d(scene_path, node_id,
                                        (normal_x, normal_y, normal_z),
                                        constant,
                                        (center_x, center_y, center_z), is_trigger)

    @mcp.tool()
    def cocos_add_mesh_collider_3d(scene_path: str, node_id: int,
                                   mesh_uuid: str | None = None,
                                   convex: bool = False,
                                   center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                   is_trigger: bool = False) -> int:
        """Attach cc.MeshCollider.

        IMPORTANT: ``convex=True`` is required when the rigid body is DYNAMIC
        — physics backends (PhysX/Bullet) only support convex meshes on
        non-static bodies. For static ground geometry, triangle (concave)
        meshes are fine with ``convex=False``.
        """
        return sb.add_mesh_collider_3d(scene_path, node_id, mesh_uuid, convex,
                                       (center_x, center_y, center_z), is_trigger)

    @mcp.tool()
    def cocos_add_terrain_collider_3d(scene_path: str, node_id: int,
                                      terrain_uuid: str | None = None,
                                      center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                      is_trigger: bool = False) -> int:
        """Attach cc.TerrainCollider (pass a cc.Terrain asset UUID)."""
        return sb.add_terrain_collider_3d(scene_path, node_id, terrain_uuid,
                                          (center_x, center_y, center_z), is_trigger)

    # ---------------- CharacterController ----------------

    @mcp.tool()
    def cocos_add_box_character_controller(scene_path: str, node_id: int,
                                           half_height: float = 0.5,
                                           half_side_extent: float = 0.5,
                                           half_forward_extent: float = 0.5,
                                           min_move_distance: float = 0.001,
                                           step_offset: float = 0.5,
                                           slope_limit: float = 45.0,
                                           skin_width: float = 0.01,
                                           center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                           group: int = 1) -> int:
        """Attach cc.BoxCharacterController — AABB-shaped kinematic character.

        Use this INSTEAD of RigidBody + Collider for player movement. It handles
        ground snapping, slope limits, step-up automatically.
        """
        return sb.add_box_character_controller(scene_path, node_id,
                                               half_height, half_side_extent, half_forward_extent,
                                               min_move_distance, step_offset, slope_limit, skin_width,
                                               (center_x, center_y, center_z), group)

    @mcp.tool()
    def cocos_add_capsule_character_controller(scene_path: str, node_id: int,
                                               radius: float = 0.5,
                                               height: float = 1.0,
                                               min_move_distance: float = 0.001,
                                               step_offset: float = 0.5,
                                               slope_limit: float = 45.0,
                                               skin_width: float = 0.01,
                                               center_x: float = 0, center_y: float = 0, center_z: float = 0,
                                               group: int = 1) -> int:
        """Attach cc.CapsuleCharacterController — capsule-shaped kinematic character.

        More common than box for humanoid characters; smoother wall sliding.
        ``height`` is the distance between the two sphere centers (NOT total
        capsule height, which is height + 2*radius).
        """
        return sb.add_capsule_character_controller(scene_path, node_id, radius, height,
                                                   min_move_distance, step_offset, slope_limit, skin_width,
                                                   (center_x, center_y, center_z), group)

    # ---------------- PhysicsMaterial asset ----------------

    @mcp.tool()
    def cocos_create_physics_material(project_path: str, material_name: str,
                                      friction: float = 0.6,
                                      rolling_friction: float = 0.0,
                                      spinning_friction: float = 0.0,
                                      restitution: float = 0.0,
                                      rel_dir: str | None = None) -> dict:
        """Create a cc.PhysicsMaterial (.pmat) asset. Returns {path, rel_path, uuid}.

        Bind to a collider via
        ``cocos_set_uuid_property(collider_id, "_material", <uuid>)``.

        Defaults match engine: friction=0.6, restitution=0 (no bounce).
        For bouncy materials set restitution 0.3-0.9; for ice set friction 0.02.
        """
        return cp.create_physics_material(project_path, material_name,
                                          friction, rolling_friction, spinning_friction,
                                          restitution, rel_dir)

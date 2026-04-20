"""PhysicsMaterial (.pmat) asset creation.

A ``cc.PhysicsMaterial`` is an asset, not a scene component. 3D colliders
reference one via ``_material: {"__uuid__": <pmat-uuid>}``. Defaults match
``cocos-engine v3.8.6`` (``cocos/physics/framework/assets/physics-material.ts``):

* _friction          0.6
* _rollingFriction   0.0
* _spinningFriction  0.0
* _restitution       0.0

Create one per distinct surface (ice, rubber, metal), then wire it to each
collider via ``cocos_set_uuid_property(collider_id, "_material", pmat_uuid)``.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..meta_util import write_meta
from ..uuid_util import new_uuid


def create_physics_material(project_path: str | Path, material_name: str,
                            friction: float = 0.6,
                            rolling_friction: float = 0.0,
                            spinning_friction: float = 0.0,
                            restitution: float = 0.0,
                            rel_dir: str | None = None,
                            uuid: str | None = None) -> dict:
    """Write a .pmat PhysicsMaterial asset + meta into the project.

    Returns ``{path, rel_path, uuid}``. Use the returned uuid in
    ``cocos_set_uuid_property(collider_id, "_material", uuid)`` to bind
    per-collider friction/restitution.
    """
    p = Path(project_path).expanduser().resolve()
    if rel_dir:
        base = rel_dir.lstrip("/")
        if not base.startswith("assets/"):
            base = f"assets/{base}"
    else:
        base = "assets/physics-materials"

    dst_dir = p / base
    dst_dir.mkdir(parents=True, exist_ok=True)
    pmat_path = dst_dir / f"{material_name}.pmat"

    pmat_uuid = uuid or new_uuid()

    # Serialized form of a cc.PhysicsMaterial asset — single-element array,
    # same layout every other Cocos asset JSON uses.
    pmat_data = [{
        "__type__": "cc.PhysicsMaterial",
        "_name": material_name,
        "_objFlags": 0,
        "_native": "",
        "_friction": friction,
        "_rollingFriction": rolling_friction,
        "_spinningFriction": spinning_friction,
        "_restitution": restitution,
    }]

    with open(pmat_path, "w") as f:
        json.dump(pmat_data, f, indent=2)

    write_meta(pmat_path, {
        "ver": "1.0.0",
        "importer": "physics-material",
        "imported": True,
        "uuid": pmat_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    })

    return {
        "path": str(pmat_path),
        "rel_path": str(pmat_path.relative_to(p)),
        "uuid": pmat_uuid,
    }

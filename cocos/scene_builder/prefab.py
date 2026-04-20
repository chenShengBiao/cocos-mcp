"""Prefab authoring and instantiation.

A .prefab file is a JSON array shaped like:
  [0] cc.Prefab         ← asset wrapper, holds optimization policy
  [1] cc.Node (root)    ← the real root node
  [2] cc.PrefabInfo     ← fileId metadata for the root
  [3..N] children/components, all referencing each other via ``__id__``

``instantiate_prefab`` deep-copies [1..N] into a target scene, shifts every
embedded ``__id__`` reference by the destination's current array length,
mints fresh ``_id`` strings and ``PrefabInfo.fileId`` UUIDs so multiple
instances don't alias, and reparents the cloned root under the caller's
``parent_id``.

Limitations of this minimal implementation:
  * Treats prefabs as "unlinked" — edits to the source .prefab won't
    propagate. Cocos's true linked-instance model uses CompPrefabInfo +
    instance overrides; supporting it is a separate (much larger) feature.
  * Doesn't validate that nested prefabs are themselves resolvable.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..meta_util import prefab_meta, write_meta
from ..uuid_util import new_uuid
from ._helpers import (
    _load_scene,
    _make_node,
    _nid,
    _ref,
    _save_scene,
    _vec3,
)


def create_prefab(prefab_path: str | Path, root_name: str = "Root", prefab_uuid: str | None = None) -> dict:
    """Create an empty .prefab file with one root node."""
    prefab_path = Path(prefab_path)
    prefab_path.parent.mkdir(parents=True, exist_ok=True)
    if prefab_uuid is None:
        prefab_uuid = new_uuid()

    objects: list[dict] = []

    def push(obj):
        idx = len(objects)
        objects.append(obj)
        return idx

    # [0] cc.Prefab
    p_idx = push({
        "__type__": "cc.Prefab",
        "_name": root_name,
        "_objFlags": 0,
        "_native": "",
        "data": None,
        "optimizationPolicy": 0,
        "asyncLoadAssets": False,
        "persistent": False,
    })

    # [1] Root cc.Node
    root_idx = push(_make_node(root_name, None))
    objects[p_idx]["data"] = _ref(root_idx)
    # 注意 prefab 节点的 _prefab 是 PrefabInfo 引用，会在最后填
    objects[root_idx]["_prefab"] = None  # placeholder

    # [N] PrefabInfo
    pi_idx = push({
        "__type__": "cc.PrefabInfo",
        "fileId": prefab_uuid,
    })
    objects[root_idx]["_prefab"] = _ref(pi_idx)

    _save_scene(prefab_path, objects)
    write_meta(prefab_path, prefab_meta(uuid=prefab_uuid, sync_node_name=root_name))

    return {
        "prefab_path": str(prefab_path),
        "prefab_uuid": prefab_uuid,
        "root_node_id": root_idx,
    }


def _shift_id_refs(obj, delta: int) -> None:
    """In-place: add `delta` to every {"__id__": N} integer reference."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "__id__" and isinstance(v, int):
                obj[k] = v + delta
            else:
                _shift_id_refs(v, delta)
    elif isinstance(obj, list):
        for item in obj:
            _shift_id_refs(item, delta)


def instantiate_prefab(scene_path: str | Path, parent_id: int,
                       prefab_path: str | Path,
                       name: str | None = None,
                       lpos: tuple | None = None,
                       lscale: tuple | None = None) -> int:
    """Drop a .prefab file into a scene as a child of parent_id.

    Returns the new root node's array index in the scene.

    Parameters:
      scene_path: target .scene file
      parent_id: array index of the cc.Node to parent the instance under
      prefab_path: source .prefab file (read-only)
      name: optional override for the root node's _name
      lpos: optional (x, y, z) overriding root local position
      lscale: optional (x, y, z) overriding root local scale

    The cloned subtree gets fresh _id values and PrefabInfo.fileId values
    so multiple instantiations of the same prefab don't collide.
    """
    s = _load_scene(scene_path)
    if parent_id < 0 or parent_id >= len(s) or s[parent_id].get("__type__") != "cc.Node":
        raise ValueError(f"parent_id {parent_id} is not a cc.Node in this scene")

    with open(prefab_path) as f:
        p_data = json.load(f)
    if not p_data or p_data[0].get("__type__") != "cc.Prefab":
        raise ValueError(f"{prefab_path} is not a valid prefab (missing cc.Prefab head)")

    # [0] is the asset wrapper — drop it. The remaining [1..N] become real scene objects.
    cloned = json.loads(json.dumps(p_data[1:]))  # deep copy

    # Old prefab index i (1..N) maps to new scene index (i - 1 + len(s)).
    # i.e. delta = len(s) - 1.
    delta = len(s) - 1
    for obj in cloned:
        _shift_id_refs(obj, delta)

    # Refresh _id (uniqueness within scene) and PrefabInfo.fileId (uniqueness across instances)
    for obj in cloned:
        if not isinstance(obj, dict):
            continue
        if "_id" in obj:
            obj["_id"] = _nid("ins")
        if obj.get("__type__") == "cc.PrefabInfo":
            obj["fileId"] = new_uuid()

    # Reparent root: prefab[1] is now cloned[0], lives at index len(s)
    root_new_idx = len(s)
    root = cloned[0]
    if root.get("__type__") != "cc.Node":
        raise ValueError(f"prefab root at [1] is {root.get('__type__')}, expected cc.Node")
    root["_parent"] = _ref(parent_id)
    if name is not None:
        root["_name"] = name
    if lpos is not None:
        root["_lpos"] = _vec3(*lpos)
    if lscale is not None:
        root["_lscale"] = _vec3(*lscale)

    s.extend(cloned)
    s[parent_id].setdefault("_children", []).append(_ref(root_new_idx))

    _save_scene(scene_path, s)
    return root_new_idx

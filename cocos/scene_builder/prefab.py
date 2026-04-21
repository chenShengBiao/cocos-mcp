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


def save_subtree_as_prefab(scene_path: str | Path,
                           root_node_id: int,
                           prefab_path: str | Path,
                           prefab_uuid: str | None = None) -> dict:
    """Extract a scene subtree into a reusable .prefab file.

    The common workflow: AI configures an "Enemy" in a working scene
    (Sprite + RigidBody2D + Collider + Animation + custom script — the
    whole stack), then wants to drop ten of them. Without this tool the
    caller has to manually re-run every ``add_*`` against ten target
    nodes. With it: build once, save once, ``instantiate_prefab`` N times.

    Self-contained requirement

    Prefabs MUST be self-contained — every ``__id__`` reachable from the
    chosen subtree has to target another object within the subtree, OR
    a non-node object (components, inline event handlers). A script
    that points at the HUD's score Label (outside the subtree) can't be
    preserved — Cocos's prefab model has no way to express "resolve this
    at instantiation time". We reject those cases with a clear error
    listing the offending external node. Typical fix: move the
    cross-reference into a property the runtime wires up on spawn, or
    include the referenced node inside the subtree.

    Sprite frames / audio clips / meshes referenced by ``__uuid__`` are
    fine — those are project-level assets, not scene objects, and the
    reference survives unchanged.

    What gets copied

    * The root ``cc.Node`` (``root_node_id``) plus every descendant.
    * Every ``cc.*`` component attached to any node in the subtree.
    * Every inline object referenced from a component field —
      ``cc.ClickEvent`` under ``Button.clickEvents``,
      ``cc.EventHandler`` under ``Toggle.checkEvents``, etc.
      These are independent scene-array entries even though they're
      "owned" by their component.

    What doesn't

    * External cc.Node references (raises).
    * Asset UUID references (kept as-is — they travel through the
      build pipeline via Cocos's asset DB, not via the prefab file).

    Effects on the source scene: **none**. This is a read-only operation
    on ``scene_path``; the source scene's objects and indices are
    untouched. If you want the scene to now contain an instance of the
    new prefab instead of the raw subtree, follow up with
    ``cocos_delete_node(scene, root_node_id)`` +
    ``cocos_instantiate_prefab(scene, parent, prefab_path)``.

    Returns::

        {
          "prefab_path": str,
          "prefab_uuid": str,
          "root_node_id": int,       # always 1 in the resulting .prefab array
          "object_count": int,       # length of the .prefab array
          "source_root_name": str,   # what we named the prefab's root
        }
    """
    s = _load_scene(scene_path)
    if root_node_id < 0 or root_node_id >= len(s):
        raise IndexError(
            f"root_node_id {root_node_id} out of range for scene "
            f"with {len(s)} objects"
        )
    root = s[root_node_id]
    if not isinstance(root, dict) or root.get("__type__") != "cc.Node":
        raise ValueError(
            f"root_node_id {root_node_id} is not a cc.Node "
            f"(got {root.get('__type__') if isinstance(root, dict) else type(root).__name__})"
        )

    # --- (1) transitive closure: collect every scene-array index that
    # belongs inside the prefab. Raises on external cc.Node refs.
    included: set[int] = set()
    node_ids_in_subtree: set[int] = set()

    def _include_node(nid: int) -> None:
        if nid in included:
            return
        included.add(nid)
        node_ids_in_subtree.add(nid)
        node = s[nid]
        for cref in node.get("_components", []):
            if isinstance(cref, dict) and "__id__" in cref:
                _include_component(cref["__id__"])
        for child_ref in node.get("_children", []):
            if isinstance(child_ref, dict) and "__id__" in child_ref:
                _include_node(child_ref["__id__"])

    def _include_component(cid: int) -> None:
        if cid in included:
            return
        included.add(cid)
        # A component can reference inline helper objects (ClickEvent,
        # EventHandler...) by __id__ in its serialized fields. Recurse
        # through the component's fields to pull those in too.
        for value in s[cid].values():
            _scan_for_refs(value, context=cid)

    def _scan_for_refs(value, context: int) -> None:
        if isinstance(value, dict):
            if "__id__" in value and isinstance(value["__id__"], int):
                rid = value["__id__"]
                if 0 <= rid < len(s):
                    target = s[rid]
                    if isinstance(target, dict):
                        ttype = target.get("__type__", "")
                        if ttype == "cc.Node":
                            # Node ref must already be in the subtree;
                            # the top-level _include_node walk has seen
                            # every descendant of root by this point.
                            # Unknown → external → hard error.
                            if rid not in node_ids_in_subtree:
                                ctx_obj = s[context]
                                ctx_name = ctx_obj.get("_name") or ctx_obj.get("__type__", "?")
                                raise ValueError(
                                    f"subtree at node {root_node_id} references "
                                    f"external cc.Node [{rid}] ({target.get('_name', '?')}) "
                                    f"via {ctx_name}. Prefabs must be self-contained — "
                                    "either include the referenced node, or remove the "
                                    "cross-reference before extracting."
                                )
                        elif rid not in included:
                            # Non-Node ref (component or inline object)
                            # — pull it in transitively.
                            included.add(rid)
                            for v in target.values():
                                _scan_for_refs(v, context=rid)
            else:
                for v in value.values():
                    _scan_for_refs(v, context=context)
        elif isinstance(value, list):
            for item in value:
                _scan_for_refs(item, context=context)

    _include_node(root_node_id)

    # --- (2) Build the old-index → new-index mapping. Prefab array layout:
    # [0] cc.Prefab, [1..N] cloned objects (root first!), [N+1] cc.PrefabInfo.
    # Keeping the root at index 1 matches create_prefab's layout and the
    # assumption instantiate_prefab makes when it reads cloned[0].
    ordered = [root_node_id] + sorted(included - {root_node_id})
    old_to_new = {old: new_idx + 1 for new_idx, old in enumerate(ordered)}

    # --- (3) Deep-copy + rewrite __id__ refs. At this point every __id__
    # in a cloned object should map; a miss means the closure logic is
    # buggy (rather than an external ref — those raise above).
    cloned = [json.loads(json.dumps(s[old_id])) for old_id in ordered]

    def _rewrite(obj) -> None:
        if isinstance(obj, dict):
            for key, val in list(obj.items()):
                if key == "__id__" and isinstance(val, int):
                    if val in old_to_new:
                        obj[key] = old_to_new[val]
                else:
                    _rewrite(val)
        elif isinstance(obj, list):
            for item in obj:
                _rewrite(item)

    for obj in cloned:
        _rewrite(obj)

    # Fresh _id strings so re-instantiation from the prefab won't alias
    # back to the source scene's nodes.
    for obj in cloned:
        if isinstance(obj, dict) and "_id" in obj:
            obj["_id"] = _nid("src")

    # --- (4) Prefab structure. cloned[0] is the root cc.Node because we
    # put root_node_id first in ``ordered`` — it lives at array index 1
    # after the cc.Prefab asset wrapper.
    #
    # Every cc.Node inside the prefab needs its own cc.PrefabInfo with a
    # unique fileId (dogfood-flappy Bug B). We emit one PrefabInfo per
    # cloned cc.Node, pack them contiguously after the cloned region,
    # and wire each node's _prefab field to its matching PrefabInfo index.
    new_prefab_uuid = prefab_uuid or new_uuid()
    root_name = cloned[0].get("_name") or "Prefab"
    cloned[0]["_parent"] = None           # prefab root has no parent

    pi_base = len(cloned) + 1  # first PrefabInfo sits right after the cloned slab
    prefab_infos: list[dict] = []
    pi_cursor = 0
    for new_idx, obj in enumerate(cloned):
        if not isinstance(obj, dict) or obj.get("__type__") != "cc.Node":
            continue
        pi_idx = pi_base + pi_cursor
        # Root gets the prefab's authoring uuid so it round-trips through
        # the Creator importer unchanged; children each get a fresh uuid
        # so their prefab-instance identity is unique.
        fileid = new_prefab_uuid if new_idx == 0 else new_uuid()
        prefab_infos.append({
            "__type__": "cc.PrefabInfo",
            "fileId": fileid,
        })
        obj["_prefab"] = {"__id__": pi_idx}
        pi_cursor += 1

    prefab_asset = {
        "__type__": "cc.Prefab",
        "_name": root_name,
        "_objFlags": 0,
        "_native": "",
        "data": {"__id__": 1},  # cloned root
        "optimizationPolicy": 0,
        "asyncLoadAssets": False,
        "persistent": False,
    }

    output = [prefab_asset] + cloned + prefab_infos

    prefab_path = Path(prefab_path)
    prefab_path.parent.mkdir(parents=True, exist_ok=True)
    _save_scene(prefab_path, output)
    write_meta(prefab_path, prefab_meta(uuid=new_prefab_uuid, sync_node_name=root_name))

    return {
        "prefab_path": str(prefab_path),
        "prefab_uuid": new_prefab_uuid,
        "root_node_id": 1,
        "object_count": len(output),
        "source_root_name": root_name,
    }

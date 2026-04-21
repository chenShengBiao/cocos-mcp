"""Cross-cutting composites — single-call shorthands for multi-call sequences.

Every function here is a pure wrapper over the per-layer primitives
(``cocos.project``, ``cocos.scene_builder``, ``cocos.uuid_util``). They
exist because the dogfood run showed the same 3–4-call dance repeated
for every script attached, every UI button created, every physics body
wired — enough that the bookkeeping drift (forgetting to compress a
UUID, losing track of which id belongs to which node, re-saving the
wrong scene path) became the dominant source of agent error.

Keeping these functions in one module rather than scattered across the
``tools/*.py`` files lets ``test_composites.py`` exercise them without
spinning up an MCP server, and lets callers reach them from Python
directly.
"""
from __future__ import annotations

from pathlib import Path

from . import project as cp
from . import scene_builder as sb
from . import uuid_util as uu


def add_and_attach_script(project_path: str | Path,
                          rel_path: str,
                          source: str,
                          scene_path: str | Path,
                          node_id: int,
                          props: dict | None = None,
                          uuid: str | None = None) -> dict:
    """Write a TS script + attach it to a scene node in one call.

    Replaces the 3-step dance agents ran repeatedly on the dogfood run::

        r = cocos_add_script(project, "Foo", source)
        short = cocos_compress_uuid(r["uuid"])
        cid = cocos_add_script(scene, node_id, short, props=...)

    with::

        r = cocos_add_and_attach_script(project, "Foo", source,
                                        scene, node_id, props=...)

    The two ``cocos_add_script`` overloads (the project-level script
    file writer vs the scene-level component attacher) sharing a name
    was the main trip-hazard here. This composite names the intent.

    Parameters mirror the two underlying primitives:

    * ``project_path`` / ``rel_path`` / ``source`` — where the .ts lives.
      ``rel_path`` follows the same auto-prefix rules as ``add_script``
      (bare names get ``assets/scripts/`` prepended; ``.ts`` appended if
      absent).
    * ``scene_path`` / ``node_id`` — the scene (or prefab) file and the
      target node's array index.
    * ``props`` — forwarded verbatim to the scene-level attach. Pass
      ``{"__id__": N}`` for node/component refs and ``{"__uuid__": "..."}``
      for asset refs; bare ints stay as ints.
    * ``uuid`` — optional override for the script's main UUID. When
      omitted and the .ts.meta already exists, the existing UUID is
      preserved (see Bug A fix in ``project.assets.add_script``).

    Returns a dict with both forms of the script UUID so the caller can
    immediately reference it from other places (e.g. linking a second
    component's @property at the same UUID)::

        {
          "script_path": "/abs/path/to/Foo.ts",
          "rel_path":    "assets/scripts/Foo.ts",
          "uuid_standard":   "5372d6f5-...",
          "uuid_compressed": "5372db1cH...",
          "component_id":    <int, the attached component's scene index>,
          "created":         <bool, False iff the .ts.meta was preserved>,
        }
    """
    script_info = cp.add_script(project_path, rel_path, source, uuid=uuid)
    compressed = uu.compress_uuid(script_info["uuid"])
    component_id = sb.add_script(scene_path, node_id, compressed, props=props)
    return {
        "script_path": script_info["path"],
        "rel_path": script_info["rel_path"],
        "uuid_standard": script_info["uuid"],
        "uuid_compressed": compressed,
        "component_id": component_id,
        "created": script_info["created"],
    }

"""MCP tool registrations for cross-cutting composites.

Each tool here wraps a multi-step sequence that agents ran over and
over during the dogfood run — ``add_script`` → ``compress_uuid`` →
scene-level ``add_script`` being the clearest case. Surfacing them
directly as single MCP tools cuts per-operation bookkeeping roughly
in half on any non-trivial scene.

The implementation lives in ``cocos.composites`` so it's importable
from plain Python (tests, callers that don't spin up an MCP server),
and this module is the thin FastMCP adapter.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import composites as co

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def cocos_add_and_attach_script(project_path: str,
                                    rel_path: str,
                                    source: str,
                                    scene_path: str,
                                    node_id: int,
                                    props: dict | None = None,
                                    uuid: str | None = None) -> dict:
        """Write a TS script file + attach it as a component in ONE call.

        Replaces the 3-call sequence agents ran dozens of times per
        session::

            r = cocos_add_script(project, "Bird", source)       # file + meta
            short = cocos_compress_uuid(r["uuid"])               # UUID form
            cid = cocos_add_script(scene, node_id, short, props) # attach

        The two same-named ``cocos_add_script`` tools (the project-
        level writer vs. the scene-level attacher) were the main
        friction — agents accidentally passed the standard UUID to
        the attacher, or skipped the compress step entirely and got
        a silently-broken component.

        Arguments:

        * ``project_path`` / ``rel_path`` / ``source`` — where the .ts
          lives. ``rel_path`` follows ``cocos_add_script``'s prefix
          rules (bare name → ``assets/scripts/<name>.ts``).
        * ``scene_path`` / ``node_id`` — target scene (or .prefab) and
          the node's array index.
        * ``props`` — component @property values, forwarded verbatim.
          Use ``{"__id__": N}`` for node/component refs,
          ``{"__uuid__": "..."}`` for asset refs.
        * ``uuid`` — optional override for the .ts.meta UUID. Omit to
          let the underlying ``add_script`` preserve an existing UUID
          on overwrite (Bug A fix) or mint a fresh one on first write.

        Returns::

            {
              "script_path":    "/abs/path/Foo.ts",
              "rel_path":       "assets/scripts/Foo.ts",
              "uuid_standard":  "5372d6f5-...",       # 36-char form
              "uuid_compressed":"5372db1cH...",       # what scenes use
              "component_id":   <int>,                # attached comp's id
              "created":        <bool>,               # False if meta preserved
            }
        """
        return co.add_and_attach_script(project_path, rel_path, source,
                                        scene_path, node_id,
                                        props=props, uuid=uuid)

"""MCP tool registrations for the gameplay-code scaffolds.

Each tool generates a canonical .ts starter module + writes its meta,
then hands the orchestrating LLM back both the standard and the
compressed UUID — so the very next call can be ``cocos_add_script`` (the
scene-mutation version) to attach the fresh component to a node.

The scaffolds themselves live in ``cocos/scaffolds/`` — these thin
wrappers exist only to publish them at the MCP layer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import scaffolds as sc

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def cocos_scaffold_input_abstraction(project_path: str,
                                         rel_path: str = "InputManager.ts") -> dict:
        """Generate InputManager.ts + meta - unified keyboard/touch input singleton.

        The generated script exposes a stable runtime API that other game
        scripts read each frame::

            InputManager.I.moveDir       // cc.Vec2, normalized, x/y in -1..1
                                         //   WASD + arrows; diagonals scaled 0.707
            InputManager.I.jumpPressed   // boolean, true for exactly one frame
                                         //   after SPACE press; reset in lateUpdate
            InputManager.I.firePressed   // boolean, true for one frame after
                                         //   KEY_J or any touch-start

        Singleton pattern: attach to exactly one persistent GameManager-like
        node. Extra instances self-destroy in onLoad.

        Typical flow::

            r = cocos_scaffold_input_abstraction(project)
            # r["uuid_compressed"] is the 23-char form the scene needs
            cocos_add_script(scene, gm_node_id, r["uuid_compressed"])

        Returns {path, rel_path, uuid_standard, uuid_compressed}.
        """
        return sc.scaffold_input_abstraction(project_path, rel_path)

    @mcp.tool()
    def cocos_scaffold_score_system(project_path: str,
                                    rel_path: str = "GameScore.ts") -> dict:
        """Generate GameScore.ts + meta - current/high score singleton with
        localStorage persistence and optional Label auto-render.

        Runtime API::

            GameScore.I.add(points)   // bump current; update high if beaten
            GameScore.I.reset()       // clear current (high survives)
            GameScore.I.current       // number, current run's score
            GameScore.I.high          // number, best ever, persisted

        The script has two optional ``@property(Label)`` slots:
        ``scoreLabel`` renders 'Score: N' on every change, ``highLabel``
        renders 'High: N'. Wire them after attach::

            cocos_set_uuid_property(scene, script_comp, 'scoreLabel', label_uuid)

        ... or let the user hook them up from the inspector if they prefer.

        High-score persistence uses ``localStorage`` under the key
        ``cocos-mcp-high-score``; write failures (private browsing,
        WeChat mini-game) are swallowed so gameplay never crashes over
        a missing save.

        Returns {path, rel_path, uuid_standard, uuid_compressed}.
        """
        return sc.scaffold_score_system(project_path, rel_path)

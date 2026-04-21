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

    @mcp.tool()
    def cocos_scaffold_player_controller(project_path: str,
                                         kind: str = "platformer",
                                         rel_path: str | None = None) -> dict:
        """Generate Player{Kind}.ts — game-type-specific player controller.

        Reads the ``InputManager`` singleton (run cocos_scaffold_input_abstraction
        FIRST) and drives node motion. Which fields the script exposes on
        the Inspector depends on the kind:

          "platformer" — side-view with gravity. Reads moveDir.x + jumpPressed.
                         Requires cc.RigidBody2D + cc.Collider2D on the node.
                         @property moveSpeed / jumpForce / doubleJumpEnabled.
          "topdown"    — bird's-eye. Full moveDir. RigidBody2D gravityScale
                         should be 0. @property moveSpeed.
          "flappy"     — jump-only. jumpPressed → fixed velocity.y impulse.
                         @property flapForce. Gravity carries it down.
          "click_only" — no physics body. Each click eases node _lpos toward
                         the hit point via tween. @property easeSpeed.

        Default ``rel_path`` per kind: PlayerPlatformer.ts / PlayerTopdown.ts /
        PlayerFlappy.ts / PlayerClick.ts. Returns
        {path, rel_path, uuid_standard, uuid_compressed}.
        """
        return sc.scaffold_player_controller(project_path, kind, rel_path)

    @mcp.tool()
    def cocos_scaffold_enemy_ai(project_path: str,
                                kind: str = "patrol",
                                rel_path: str | None = None) -> dict:
        """Generate Enemy{Kind}.ts — common enemy-behaviour starters.

          "patrol" — oscillates between @property Nodes patrolA ↔ patrolB.
                     Flips optional @property mirrorSprite on direction
                     change. Exposes @property speed.
          "chase"  — tracks @property target Node when within chaseRadius;
                     gives up past loseAggroRadius (hysteresis prevents
                     aggro flicker). Kinematic setPosition update.
                     @property moveSpeed.
          "shoot"  — stationary turret. Every @property fireInterval s,
                     instantiates @property bulletPrefab with velocity
                     toward @property target if within @property range.

        Default ``rel_path`` per kind: EnemyPatrol.ts / EnemyChase.ts /
        EnemyShoot.ts. Returns the usual four keys.
        """
        return sc.scaffold_enemy_ai(project_path, kind, rel_path)

    @mcp.tool()
    def cocos_scaffold_spawner(project_path: str,
                               kind: str = "time",
                               rel_path: str | None = None) -> dict:
        """Generate Spawner{Kind}.ts — instantiate @property prefab on a trigger.

          "time"      — every @property interval s, up to @property maxActive
                        concurrent. Jitters spawn position within
                        @property spawnBoxSize half-extents. Over cap:
                        despawn oldest (destroy + shift queue).
          "proximity" — spawn when @property player is within
                        @property triggerRadius, respecting @property cooldown
                        seconds and @property maxActive cap.

        Both variants parent spawned nodes under ``this.node.parent``
        (NOT the spawner itself — inheriting the spawner's transform is
        usually wrong) and fire optional @property onSpawn callback post-
        addChild so game code can attach health, patrol targets, etc.

        Default ``rel_path``: SpawnerTime.ts / SpawnerProximity.ts.
        """
        return sc.scaffold_spawner(project_path, kind, rel_path)

    @mcp.tool()
    def cocos_scaffold_game_loop(project_path: str,
                                 states: list[str] | None = None,
                                 rel_path: str = "GameLoop.ts") -> dict:
        """Generate GameLoop.ts — singleton state machine.

        ``states``: ordered list, default ["menu", "play", "over"].
        Each state name generates a pair of inspector-visible callbacks:
        ``onEnter<PascalCase>`` and ``onExit<PascalCase>`` — so ``"game_over"``
        becomes ``onEnterGameOver`` / ``onExitGameOver``. Designers can wire
        either from the Inspector or from script code.

        Runtime API::

            GameLoop.I.current          // current state name
            GameLoop.I.go(state)        // transition; fires onExit<old> → onEnter<new>
            GameLoop.I.reset()          // jump to first state

        State-name validation at scaffold time:
          - at least one state
          - identifier-safe (no spaces, no leading digits)
          - no duplicates
        Violations raise ValueError so the broken template never lands.

        Returns {path, rel_path, uuid_standard, uuid_compressed}.
        """
        return sc.scaffold_game_loop(project_path, states, rel_path)

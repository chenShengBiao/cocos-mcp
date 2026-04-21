"""Scaffold for a game-type-specific player controller.

A "player" means a wildly different thing depending on the game: a
platformer wants gravity + jump + maybe double-jump, a top-down shooter
wants free 2D motion with gravity disabled, a flappy-style game is jump-
only, and a click/puzzle game has no physics body at all. Rather than
ship one over-general controller that pretends to handle all four (and
ends up handling none of them cleanly), we generate a targeted script
per ``kind``. Each variant reads the canonical ``InputManager`` singleton
so upstream tooling can chain the two scaffolds together without the LLM
having to rewire input each time.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_PLATFORMER = """\
import { _decorator, Component, RigidBody2D, Vec2 } from 'cc';
import { InputManager } from './InputManager';
const { ccclass, property } = _decorator;

/**
 * Side-view platformer controller.
 *
 * Reads InputManager.I.moveDir.x (horizontal) and jumpPressed (one-frame
 * trigger). Requires cc.RigidBody2D + cc.Collider2D on the same node.
 *
 * Grounded check uses linearVelocity.y ~= 0 as a cheap heuristic — it is
 * deliberately not a proper raycast because raycasts fight tiny slope
 * geometry in practice. If your level has sloped ground, swap this for a
 * short downward raycast.
 */
@ccclass('PlayerPlatformer')
export class PlayerPlatformer extends Component {
    @property({ tooltip: 'Horizontal speed in world units / sec' })
    moveSpeed: number = 300;

    @property({ tooltip: 'Upward impulse applied on jump' })
    jumpForce: number = 600;

    @property({ tooltip: 'If true, allow one extra jump in mid-air' })
    doubleJumpEnabled: boolean = false;

    private rigidBody: RigidBody2D | null = null;
    private _jumpsLeft: number = 0;
    private _tmpVel: Vec2 = new Vec2(0, 0);

    onLoad() {
        this.rigidBody = this.getComponent(RigidBody2D);
    }

    update(_dt: number) {
        if (!this.rigidBody) return;
        const mgr = InputManager.I;
        // Guard in case InputManager hasn't been scaffolded / attached
        // yet — don't crash the game, just no-op until it shows up.
        if (!mgr) return;

        this.rigidBody.linearVelocity = this._tmpVel;
        this._tmpVel = this.rigidBody.linearVelocity;

        // Horizontal: InputManager feeds normalized -1..1.
        const vx = mgr.moveDir.x * this.moveSpeed * 0.01;
        this._tmpVel.x = vx;

        const grounded = Math.abs(this._tmpVel.y) < 0.05;
        if (grounded) {
            const max = this.doubleJumpEnabled ? 2 : 1;
            this._jumpsLeft = max;
        }

        if (mgr.jumpPressed && this._jumpsLeft > 0) {
            this._tmpVel.y = this.jumpForce * 0.01;
            this._jumpsLeft -= 1;
        }

        this.rigidBody.linearVelocity = this._tmpVel;
    }
}
"""

_TOPDOWN = """\
import { _decorator, Component, RigidBody2D, Vec2 } from 'cc';
import { InputManager } from './InputManager';
const { ccclass, property } = _decorator;

/**
 * Top-down (bird's-eye) controller.
 *
 * No gravity, no jump. Reads the full InputManager.I.moveDir (both x and
 * y) and sets linearVelocity directly. Requires cc.RigidBody2D with
 * gravityScale = 0 on the same node.
 */
@ccclass('PlayerTopdown')
export class PlayerTopdown extends Component {
    @property({ tooltip: 'Movement speed in world units / sec' })
    moveSpeed: number = 300;

    private rigidBody: RigidBody2D | null = null;
    private _tmpVel: Vec2 = new Vec2(0, 0);

    onLoad() {
        this.rigidBody = this.getComponent(RigidBody2D);
    }

    update(_dt: number) {
        if (!this.rigidBody) return;
        const mgr = InputManager.I;
        // No-op if the singleton hasn't been installed yet.
        if (!mgr) return;

        this._tmpVel.x = mgr.moveDir.x * this.moveSpeed * 0.01;
        this._tmpVel.y = mgr.moveDir.y * this.moveSpeed * 0.01;
        this.rigidBody.linearVelocity = this._tmpVel;
    }
}
"""

_FLAPPY = """\
import { _decorator, Component, RigidBody2D, Vec2 } from 'cc';
import { InputManager } from './InputManager';
const { ccclass, property } = _decorator;

/**
 * Flappy-style jump-only controller.
 *
 * No horizontal control. Each time InputManager.I.jumpPressed fires
 * (keyboard Space or — once touch-jump is wired in — tap-anywhere),
 * replace linearVelocity.y with a fixed upward impulse. Gravity does
 * the rest, so RigidBody2D.gravityScale should be > 0.
 */
@ccclass('PlayerFlappy')
export class PlayerFlappy extends Component {
    @property({ tooltip: 'Upward velocity applied on each flap' })
    flapForce: number = 400;

    private rigidBody: RigidBody2D | null = null;
    private _tmpVel: Vec2 = new Vec2(0, 0);

    onLoad() {
        this.rigidBody = this.getComponent(RigidBody2D);
    }

    update(_dt: number) {
        if (!this.rigidBody) return;
        const mgr = InputManager.I;
        if (!mgr) return;

        if (mgr.jumpPressed) {
            this._tmpVel = this.rigidBody.linearVelocity;
            this._tmpVel.y = this.flapForce * 0.01;
            this.rigidBody.linearVelocity = this._tmpVel;
        }
    }
}
"""

_CLICK_ONLY = """\
import { _decorator, Component, Input, input, EventTouch, UITransform, Vec3, tween } from 'cc';
const { ccclass, property } = _decorator;

/**
 * Click / tap controller — no physics.
 *
 * On every touch-start, the node's local position eases toward the
 * touched world point over ``easeSpeed`` seconds via cc.tween. Suitable
 * for puzzle / tap-based games where the "player" is really just a
 * cursor that jumps to where you clicked.
 */
@ccclass('PlayerClick')
export class PlayerClick extends Component {
    @property({ tooltip: 'Seconds for the ease to reach the click point' })
    easeSpeed: number = 0.25;

    onLoad() {
        input.on(Input.EventType.TOUCH_START, this._onTouch, this);
    }

    onDestroy() {
        input.off(Input.EventType.TOUCH_START, this._onTouch, this);
    }

    private _onTouch(e: EventTouch) {
        const parent = this.node.parent;
        if (!parent) return;
        const tf = parent.getComponent(UITransform);
        if (!tf) return;

        const world = e.getUILocation();
        const local = tf.convertToNodeSpaceAR(new Vec3(world.x, world.y, 0));
        tween(this.node)
            .stop()
            .to(this.easeSpeed, { position: local })
            .start();
    }
}
"""

_TEMPLATES: dict[str, str] = {
    "platformer": _PLATFORMER,
    "topdown": _TOPDOWN,
    "flappy": _FLAPPY,
    "click_only": _CLICK_ONLY,
}

_DEFAULT_REL_PATHS: dict[str, str] = {
    "platformer": "PlayerPlatformer.ts",
    "topdown": "PlayerTopdown.ts",
    "flappy": "PlayerFlappy.ts",
    "click_only": "PlayerClick.ts",
}


def scaffold_player_controller(project_path: str | Path,
                               kind: str = "platformer",
                               rel_path: str | None = None) -> dict:
    """Generate Player{Platformer|Topdown|Flappy|Click}.ts — a game-type-
    specific player controller that reads InputManager and drives motion.

    kind values:

      "platformer" — side-view with gravity. Reads InputManager.I.moveDir.x
          for horizontal, .jumpPressed for vertical. Requires cc.RigidBody2D
          + cc.Collider2D on the same node. Exposes @property moveSpeed,
          jumpForce, and @property doubleJumpEnabled (allow one extra
          jump in mid-air).

      "topdown" — bird's-eye with no gravity. Reads full InputManager.I.moveDir
          to set linearVelocity directly. RigidBody2D.gravityScale should
          be 0. @property moveSpeed.

      "flappy" — jump-only (Space or tap anywhere). Reads
          InputManager.I.jumpPressed to set linearVelocity.y to a fixed
          impulse. Relies on gravity. No horizontal control. @property
          flapForce.

      "click_only" — no physics body. Reads screen-space touch/click;
          each click, the node's _lpos eases toward the hit point over
          `easeSpeed` seconds. For puzzle / tap-based games.

    ``rel_path`` defaults (based on kind):
      platformer → "PlayerPlatformer.ts"
      topdown    → "PlayerTopdown.ts"
      flappy     → "PlayerFlappy.ts"
      click_only → "PlayerClick.ts"

    All variants (except click_only) import InputManager via
    ``import { InputManager } from './InputManager'`` — callers MUST run
    ``scaffold_input_abstraction`` first (or ensure an ``InputManager.ts``
    is adjacent to the generated file) or the Creator type-checker will
    complain about the unresolved import.

    Returns {path, rel_path, uuid_standard, uuid_compressed}. The caller
    attaches via ``cocos_add_script(scene, node, uuid_compressed)``.
    """
    if kind not in _TEMPLATES:
        raise ValueError(
            f"unknown kind {kind!r}; valid options: "
            f"{sorted(_TEMPLATES.keys())}"
        )

    source = _TEMPLATES[kind]
    chosen_rel = rel_path if rel_path is not None else _DEFAULT_REL_PATHS[kind]
    result = add_script(project_path, chosen_rel, source)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

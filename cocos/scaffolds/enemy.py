"""Scaffolds for the three most-reused enemy-AI starter behaviours.

Enemy behaviour is project-specific in the long run, but the *scaffolds*
— "oscillate between two points", "chase if within radius", "turret
that fires at a target" — are recreated in nearly every gameplay demo.
Generating them from a single canonical template keeps naming
(``speed``, ``moveSpeed``, ``fireInterval`` ...) consistent across a
project so a designer pulling these into the Inspector sees the same
vocabulary every time, and keeps the orchestrating LLM out of the
business of retyping kinematic update loops or ``instantiate`` + bullet
velocity math from memory.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_PATROL_TS = """\
import { _decorator, Component, Node, Sprite, Vec3 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * Oscillates between two @property anchor nodes. Deterministic motion —
 * good for platformer mooks / patrolling guards. Flips mirrorSprite's
 * _flipU on direction change so the art faces the way of travel.
 *
 * Assumes the node has cc.RigidBody2D + cc.Collider2D already attached
 * if you want physics-driven interactions; the motion itself is pure
 * kinematic via direct position update.
 */
@ccclass('EnemyPatrol')
export class EnemyPatrol extends Component {
    @property(Node)
    patrolA: Node | null = null;

    @property(Node)
    patrolB: Node | null = null;

    @property(Sprite)
    mirrorSprite: Sprite | null = null;

    @property({ tooltip: 'Units per second along the patrol line.' })
    speed: number = 100;

    private _target: Node | null = null;
    private _tmp: Vec3 = new Vec3();

    start() {
        // Pick an initial destination; if neither anchor is set we just
        // stand still rather than crash — designers may drop this script
        // on a prototype node before wiring the anchors.
        this._target = this.patrolA || this.patrolB;
    }

    update(dt: number) {
        if (!this._target || !this.patrolA || !this.patrolB) return;

        const pos = this.node.getPosition(this._tmp);
        const tgt = this._target.getWorldPosition();
        const dx = tgt.x - pos.x;
        const dy = tgt.y - pos.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 1) {
            // Arrived — flip direction.
            const next = this._target === this.patrolA ? this.patrolB : this.patrolA;
            const flippingRight = next.getWorldPosition().x > pos.x;
            if (this.mirrorSprite) {
                // Not every enemy has a sprite to flip (e.g. a sensor-only
                // patroller) — only touch the component if it's wired.
                this.mirrorSprite.spriteFrame && (this.mirrorSprite as any)._flipU = !flippingRight;
            }
            this._target = next;
            return;
        }

        const step = this.speed * dt;
        const nx = pos.x + (dx / dist) * step;
        const ny = pos.y + (dy / dist) * step;
        this.node.setPosition(nx, ny, pos.z);
    }
}
"""

_CHASE_TS = """\
import { _decorator, Component, Node, Vec3 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * Moves toward @property target each frame while target is within
 * chaseRadius, stops beyond loseAggroRadius. Two radii (with
 * loseAggro > chase) give hysteresis — prevents the enemy from
 * twitching on/off at the edge of the activation zone.
 *
 * Kinematic via setPosition rather than RigidBody2D velocity, so
 * aggro-driven motion doesn't fight the physics collision response
 * (velocity-driven enemies ping-pong into walls on contact).
 */
@ccclass('EnemyChase')
export class EnemyChase extends Component {
    @property(Node)
    target: Node | null = null;

    @property({ tooltip: 'Start chasing when target is this close.' })
    chaseRadius: number = 200;

    @property({ tooltip: 'Give up if target escapes beyond this radius.' })
    loseAggroRadius: number = 350;

    @property({ tooltip: 'Units per second toward the target.' })
    moveSpeed: number = 80;

    private _aggro: boolean = false;
    private _tmp: Vec3 = new Vec3();

    update(dt: number) {
        if (!this.target) return;

        const selfPos = this.node.getWorldPosition(this._tmp);
        const tgtPos = this.target.getWorldPosition();
        const dist = Vec3.distance(selfPos, tgtPos);

        if (!this._aggro && dist <= this.chaseRadius) {
            this._aggro = true;
        } else if (this._aggro && dist > this.loseAggroRadius) {
            this._aggro = false;
        }

        if (!this._aggro) return;

        const dx = tgtPos.x - selfPos.x;
        const dy = tgtPos.y - selfPos.y;
        const step = this.moveSpeed * dt;
        if (dist < 0.001) return;
        const local = this.node.getPosition();
        const nx = local.x + (dx / dist) * step;
        const ny = local.y + (dy / dist) * step;
        this.node.setPosition(new Vec3(nx, ny, local.z));
    }
}
"""

_SHOOT_TS = """\
import { _decorator, Component, Node, Prefab, Vec3, instantiate, RigidBody2D, Vec2 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * Stationary turret. Every fireInterval seconds, if the target is
 * within range, spawns a bullet instance at this node's world position
 * and aims it at the target. If the bullet prefab has a RigidBody2D on
 * its root we set linearVelocity; otherwise it's the caller's job to
 * animate the bullet (tween, custom script, etc.).
 */
@ccclass('EnemyShoot')
export class EnemyShoot extends Component {
    @property(Node)
    target: Node | null = null;

    @property(Prefab)
    bulletPrefab: Prefab | null = null;

    @property({ tooltip: 'Seconds between shots.' })
    fireInterval: number = 1.0;

    @property({ tooltip: 'Only fire when target is within this radius.' })
    range: number = 300;

    @property({ tooltip: 'Bullet launch speed, units/sec.' })
    bulletSpeed: number = 400;

    public cooldownTimer: number = 0;

    update(dt: number) {
        this.cooldownTimer += dt;
        if (!this.target || !this.bulletPrefab) return;
        if (this.cooldownTimer < this.fireInterval) return;

        const selfPos = this.node.getWorldPosition();
        const tgtPos = this.target.getWorldPosition();
        const dist = Vec3.distance(selfPos, tgtPos);
        if (dist > this.range) return;

        this.cooldownTimer = 0;
        const bullet = instantiate(this.bulletPrefab);
        if (!this.node.parent) return;
        this.node.parent.addChild(bullet);
        bullet.setWorldPosition(selfPos);

        const dx = tgtPos.x - selfPos.x;
        const dy = tgtPos.y - selfPos.y;
        const inv = dist > 0 ? 1 / dist : 0;
        const vx = dx * inv * this.bulletSpeed;
        const vy = dy * inv * this.bulletSpeed;

        const rb = bullet.getComponent(RigidBody2D);
        if (rb) {
            rb.linearVelocity = new Vec2(vx, vy);
        }
        // If there's no RigidBody2D, gameplay code / bullet script can
        // read the spawn position + infer a direction from the shooter's
        // orientation. We leave that integration to the project.
    }
}
"""

_TEMPLATES: dict[str, str] = {
    "patrol": _PATROL_TS,
    "chase": _CHASE_TS,
    "shoot": _SHOOT_TS,
}

_DEFAULT_REL_PATHS: dict[str, str] = {
    "patrol": "EnemyPatrol.ts",
    "chase": "EnemyChase.ts",
    "shoot": "EnemyShoot.ts",
}


def scaffold_enemy_ai(project_path: str | Path,
                      kind: str = "patrol",
                      rel_path: str | None = None) -> dict:
    """Generate Enemy{Patrol|Chase|Shoot}.ts — common enemy-behavior
    starter scripts. All three assume the target node has cc.RigidBody2D
    + cc.Collider2D already attached (or kinematic motion via direct
    _lpos manipulation where noted).

    kind values:

      "patrol" — oscillates between two @property Node anchors
          (patrolA, patrolB). Simple deterministic motion; good for
          platformer mooks. Flips a @property mirrorSprite Sprite
          component's _flipU on direction change so the sprite faces
          where it's walking. @property speed (units/sec).

      "chase" — moves toward @property target Node each frame while
          target is within @property chaseRadius. Stops / idles beyond
          that (prevents enemies bee-lining from off-screen). @property
          moveSpeed, loseAggroRadius. Uses kinematic _lpos update (not
          physics velocity) so aggro doesn't fight collision response.

      "shoot" — stationary turret. Each @property fireInterval seconds,
          if @property target is within @property range, instantiate
          @property bulletPrefab at this.node's world position with
          linearVelocity pointed at the target. Prefab is a cc.Prefab
          asset reference. Exposes @property cooldownTimer (starts at
          0, increments in update).

    ``rel_path`` defaults (per kind):
      patrol → "EnemyPatrol.ts"
      chase  → "EnemyChase.ts"
      shoot  → "EnemyShoot.ts"

    Returns {path, rel_path, uuid_standard, uuid_compressed}.
    """
    if kind not in _TEMPLATES:
        raise ValueError(
            f"unknown enemy kind {kind!r}; expected one of 'patrol', 'chase', 'shoot'"
        )
    source = _TEMPLATES[kind]
    target_rel = rel_path if rel_path is not None else _DEFAULT_REL_PATHS[kind]
    result = add_script(project_path, target_rel, source)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

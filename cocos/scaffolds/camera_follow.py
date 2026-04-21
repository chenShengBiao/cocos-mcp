"""Scaffold for a camera-follow script with deadzone + smoothing + bounds.

Every 2D/3D game ends up re-implementing the same "camera chases player"
logic, and the LLM tends to make the same mistakes each time: allocating
a fresh Vec3 every frame (GC churn), framerate-dependent lerp (fast on a
high-refresh monitor, sluggish on 30fps), no deadzone (jitter when the
player stands still near center), and no world-bounds clamp (camera
drifts off the level edge). Rather than let those land in every
generated scene, we ship a canonical version here: exponential
frame-rate-independent damping, per-axis deadzone, optional axis-clamped
world bounds, and a reusable ``_tmp`` scratch vector.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_TEMPLATE = """\
import { _decorator, Component, Node, Vec3 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * CameraFollow — attach to a Camera node (or any node acting as a
 * follow rig) so it trails `target` with deadzone + smoothing + bounds.
 *
 *   smoothing:  0  = snap instantly to target
 *               1  = never moves (degenerate)
 *               0.15 ~ smooth chase that reaches the target in ~1s
 *               (we use frame-rate-independent exponential damping:
 *                https://www.rorydriscoll.com/2016/03/07/frame-rate-independent-damping-using-lerp/ )
 *
 *   deadzone:   camera only moves on an axis when the target drifts
 *               farther than deadzoneWidth/2 (or deadzoneHeight/2) from
 *               the camera's current focus — eliminates sub-pixel drift
 *               when the player is idle near center.
 *
 *   bounds:     if useWorldBounds, camera.x is clamped to [minX, maxX]
 *               and y to [minY, maxY]. Use this to stop the camera from
 *               revealing the void past the level edge.
 *
 *   fixedZ:     -1 sentinel = z follows target.z (full 3D).
 *               any other number = z is locked to that value
 *               (typical for orthographic 2D where the camera sits at z=1000).
 */
@ccclass('CameraFollow')
export class CameraFollow extends Component {
    @property(Node)
    target: Node | null = null;

    @property
    offsetX: number = 0;

    @property
    offsetY: number = 0;

    @property({ tooltip: '0 = snap, 1 = frozen. ~0.15 feels nice.', range: [0, 1, 0.01] })
    smoothing: number = 0.15;

    @property
    deadzoneWidth: number = 0;

    @property
    deadzoneHeight: number = 0;

    @property
    useWorldBounds: boolean = false;

    @property
    worldBoundsMinX: number = -10000;

    @property
    worldBoundsMaxX: number = 10000;

    @property
    worldBoundsMinY: number = -10000;

    @property
    worldBoundsMaxY: number = 10000;

    @property({ tooltip: '-1 = z follows target; any other value locks z.' })
    fixedZ: number = -1;

    // Reused each frame — never allocate a Vec3 in lateUpdate, the GC
    // pressure is visible on low-end devices.
    private _tmp: Vec3 = new Vec3();
    private _desired: Vec3 = new Vec3();

    lateUpdate(dt: number) {
        // Null-check each frame — the target can be destroyed mid-scene
        // (e.g. player death) and we must not crash the camera.
        if (!this.target) return;

        // Desired pos = target + offset (z handled via fixedZ sentinel).
        const tp = this.target.getPosition(this._tmp);
        this._desired.set(
            tp.x + this.offsetX,
            tp.y + this.offsetY,
            this.fixedZ === -1 ? tp.z : this.fixedZ,
        );

        // Current pos (reuse _tmp now that we've consumed target pos).
        const cur = this.node.getPosition(this._tmp);
        let nx = cur.x;
        let ny = cur.y;
        let nz = cur.z;

        // Frame-rate-independent exponential damping. At dt = 1/60s with
        // smoothing=0.15, ~99% of the distance is covered in ~1 second
        // regardless of framerate. See Driscoll 2016.
        const t = 1 - Math.pow(this.smoothing, dt);

        // Per-axis deadzone: only chase if the target drifted past the
        // centered rectangle. Kills sub-pixel jitter when player is idle.
        const dzHalfX = this.deadzoneWidth * 0.5;
        const dzHalfY = this.deadzoneHeight * 0.5;

        const dx = this._desired.x - cur.x;
        if (Math.abs(dx) > dzHalfX) {
            // Target to approach is just past the deadzone edge, not the
            // full desired pos — this keeps the camera latched to the
            // deadzone boundary instead of centering past it.
            const edge = this._desired.x - Math.sign(dx) * dzHalfX;
            nx = cur.x + (edge - cur.x) * t;
        }

        const dy = this._desired.y - cur.y;
        if (Math.abs(dy) > dzHalfY) {
            const edge = this._desired.y - Math.sign(dy) * dzHalfY;
            ny = cur.y + (edge - cur.y) * t;
        }

        // Z: always track (no deadzone — z changes are usually intentional
        // like a level-transition dolly).
        nz = cur.z + (this._desired.z - cur.z) * t;

        // World-bounds clamp on x/y only. Camera z stays free.
        if (this.useWorldBounds) {
            nx = Math.max(this.worldBoundsMinX, Math.min(this.worldBoundsMaxX, nx));
            ny = Math.max(this.worldBoundsMinY, Math.min(this.worldBoundsMaxY, ny));
        }

        this.node.setPosition(nx, ny, nz);
    }
}
"""


def scaffold_camera_follow(project_path: str | Path,
                           rel_path: str = "CameraFollow.ts") -> dict:
    """Generate CameraFollow.ts — attach to a Camera (or any rig node) to
    follow ``target`` with per-axis deadzone, frame-rate-independent
    exponential smoothing, and optional world-bounds clamp.

    Inspector fields:
        target           (Node)     the entity to follow (usually Player)
        offsetX/Y        (number)   fixed offset from target
        smoothing        (number)   0=snap, 1=frozen, ~0.15 chases in ~1s
        deadzoneWidth/H  (number)   only move when target leaves this rect
        useWorldBounds   (bool)     clamp camera to min/max rect below
        worldBoundsMin/Max X/Y (number)
        fixedZ           (number)   -1 = follow target z, else lock

    Uses exponential damping ``lerp(cur, target, 1 - pow(smoothing, dt))``
    so behavior is identical at 30/60/120fps. Reuses a private Vec3 per
    frame — no per-frame allocation. Null-checks target each tick so the
    camera survives target destruction mid-scene.

    Same return shape as the other scaffolds:
    ``{path, rel_path, uuid_standard, uuid_compressed}``.
    """
    result = add_script(project_path, rel_path, _TEMPLATE)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

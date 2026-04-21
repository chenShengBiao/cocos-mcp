"""Scaffolds for prefab-spawner starter scripts.

Almost every 2D game has one or two spawners: either a time-triggered
meteor shower / star field, or a proximity-triggered wave spawner that
fires when the player wanders into a new area. Both are small but
fiddly to get right — cap concurrent actives, parent under the right
node (the spawner's *parent*, not the spawner itself, or transforms
stack), jitter the spawn point. Generating them here keeps the invariants
consistent across a project.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_TIME_TS = """\
import { _decorator, Component, Node, Prefab, Vec2, Vec3, instantiate } from 'cc';
const { ccclass, property } = _decorator;

/**
 * Interval-based spawner. Every ``interval`` seconds, instantiates
 * ``prefab`` and parents it under this spawner's *parent* (not under
 * the spawner itself — otherwise spawns inherit the spawner's scale /
 * rotation, which is almost never what you want for meteors / stars).
 * Position is jittered within a half-extent box so spawns aren't
 * stacked on top of each other.
 */
@ccclass('SpawnerTime')
export class SpawnerTime extends Component {
    @property(Prefab)
    prefab: Prefab | null = null;

    @property({ tooltip: 'Seconds between spawns.' })
    interval: number = 1.0;

    @property({ tooltip: 'Hard cap on concurrent alive instances.' })
    maxActive: number = 10;

    @property({ tooltip: 'Half-extents of the spawn jitter box (x,y).' })
    spawnBoxSize: Vec2 = new Vec2(50, 50);

    /**
     * Optional callback invoked with each freshly-spawned Node so
     * gameplay code can layer on setup (health, patrol targets, etc.)
     * without editing the spawner itself.
     */
    public onSpawn: ((spawned: Node) => void) | null = null;

    private _elapsed: number = 0;
    private _active: Node[] = [];

    update(dt: number) {
        this._elapsed += dt;
        if (this._elapsed < this.interval) return;
        this._elapsed = 0;
        if (!this.prefab || !this.node.parent) return;

        // Drop any instances that got destroyed externally from our list.
        this._active = this._active.filter(n => n && n.isValid);

        if (this._active.length >= this.maxActive) {
            // Over cap — despawn the oldest so the new spawn has room.
            const oldest = this._active.shift();
            if (oldest && oldest.isValid) oldest.destroy();
        }

        const spawned = instantiate(this.prefab);
        const center = this.node.getPosition();
        const x = center.x + (Math.random() - 0.5) * 2 * this.spawnBoxSize.x;
        const y = center.y + (Math.random() - 0.5) * 2 * this.spawnBoxSize.y;
        spawned.setPosition(new Vec3(x, y, center.z));
        this.node.parent.addChild(spawned);
        this._active.push(spawned);

        if (this.onSpawn) this.onSpawn(spawned);
    }
}
"""

_PROXIMITY_TS = """\
import { _decorator, Component, Node, Prefab, Vec3, instantiate } from 'cc';
const { ccclass, property } = _decorator;

/**
 * Proximity-triggered spawner. Fires whenever the player enters
 * triggerRadius AND we're under the maxActive cap AND not on cooldown.
 * The cooldown prevents a single dwell from spamming spawns every
 * frame; once fired, spawns are suppressed for ``cooldown`` seconds
 * even if the player stays inside the radius.
 */
@ccclass('SpawnerProximity')
export class SpawnerProximity extends Component {
    @property(Prefab)
    prefab: Prefab | null = null;

    @property(Node)
    player: Node | null = null;

    @property({ tooltip: 'Spawn triggers when player is within this radius.' })
    triggerRadius: number = 250;

    @property({ tooltip: 'Hard cap on concurrent alive instances.' })
    maxActive: number = 5;

    @property({ tooltip: 'Seconds to wait after each spawn before checking again.' })
    cooldown: number = 2.0;

    /**
     * Callback invoked with each freshly-spawned Node — project code
     * uses this to wire up health, assign patrol paths, etc.
     */
    public onSpawn: ((spawned: Node) => void) | null = null;

    private _cooldownLeft: number = 0;
    private _active: Node[] = [];

    update(dt: number) {
        if (this._cooldownLeft > 0) {
            this._cooldownLeft -= dt;
            return;
        }
        if (!this.prefab || !this.player || !this.node.parent) return;

        this._active = this._active.filter(n => n && n.isValid);
        if (this._active.length >= this.maxActive) return;

        const dist = Vec3.distance(
            this.node.getWorldPosition(),
            this.player.getWorldPosition(),
        );
        if (dist > this.triggerRadius) return;

        const spawned = instantiate(this.prefab);
        const center = this.node.getPosition();
        spawned.setPosition(new Vec3(center.x, center.y, center.z));
        this.node.parent.addChild(spawned);
        this._active.push(spawned);
        this._cooldownLeft = this.cooldown;

        if (this.onSpawn) this.onSpawn(spawned);
    }
}
"""

_TEMPLATES: dict[str, str] = {
    "time": _TIME_TS,
    "proximity": _PROXIMITY_TS,
}

_DEFAULT_REL_PATHS: dict[str, str] = {
    "time": "SpawnerTime.ts",
    "proximity": "SpawnerProximity.ts",
}


def scaffold_spawner(project_path: str | Path,
                     kind: str = "time",
                     rel_path: str | None = None) -> dict:
    """Generate Spawner{Time|Proximity}.ts — instantiates copies of
    a @property Prefab on a trigger.

    kind values:

      "time" — every @property interval seconds. @property maxActive
          caps concurrent spawns (tracks instances, despawns oldest if
          over cap). @property spawnBoxSize (Vec2 half-extents) lets
          spawn positions jitter within a rectangle relative to this
          spawner node — good for meteor showers, star fields.

      "proximity" — spawn whenever @property player is within
          @property triggerRadius AND currentActive < @property maxActive.
          @property cooldown seconds after each spawn before next
          proximity check fires. Useful for wave spawners triggered by
          exploration.

    Both kinds:
      @property prefab (cc.Prefab) — what to spawn
      @property maxActive (number)
      @property onSpawn callback — invoked with the spawned Node so
        game code can attach extra setup (health, patrol targets, etc).

    ``rel_path`` defaults:
      time       → "SpawnerTime.ts"
      proximity  → "SpawnerProximity.ts"

    Returns {path, rel_path, uuid_standard, uuid_compressed}.
    """
    if kind not in _TEMPLATES:
        raise ValueError(
            f"unknown spawner kind {kind!r}; expected one of 'time', 'proximity'"
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

"""Scaffold for a unified keyboard + touch input singleton.

Every small game re-derives the same thing: "give me a normalized move
vector + one-frame jump/fire triggers regardless of input device."
Rather than have the orchestrating LLM retype that skeleton each time
(and make subtly different decisions about diagonal normalization or
one-frame-flag reset timing), we generate a single canonical version
here. The runtime contract — ``InputManager.I.moveDir`` etc. — is
stable so downstream scripts can import this without coupling to the
specifics of the generator.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_TEMPLATE = """\
import { _decorator, Component, Input, input, EventKeyboard, EventTouch, KeyCode, Vec2 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * Unified input: keyboard arrows + WASD + touch swipes + single-tap fire.
 * Singleton — attach to one 'GameManager'-style persistent node.
 *
 *   InputManager.I.moveDir       normalized vec, x/y in -1..1
 *   InputManager.I.jumpPressed   one-frame trigger, reset end-of-frame
 *   InputManager.I.firePressed   one-frame trigger, reset end-of-frame
 */
@ccclass('InputManager')
export class InputManager extends Component {
    private static _instance: InputManager | null = null;
    static get I(): InputManager { return InputManager._instance!; }

    public moveDir: Vec2 = new Vec2(0, 0);
    public jumpPressed: boolean = false;
    public firePressed: boolean = false;

    private _keyState: Record<number, boolean> = {};

    onLoad() {
        if (InputManager._instance && InputManager._instance !== this) {
            this.destroy();
            return;
        }
        InputManager._instance = this;

        input.on(Input.EventType.KEY_DOWN, this._onKeyDown, this);
        input.on(Input.EventType.KEY_UP, this._onKeyUp, this);
        input.on(Input.EventType.TOUCH_START, this._onTouchStart, this);
        input.on(Input.EventType.TOUCH_END, this._onTouchEnd, this);
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this._onKeyDown, this);
        input.off(Input.EventType.KEY_UP, this._onKeyUp, this);
        input.off(Input.EventType.TOUCH_START, this._onTouchStart, this);
        input.off(Input.EventType.TOUCH_END, this._onTouchEnd, this);
        if (InputManager._instance === this) InputManager._instance = null;
    }

    lateUpdate() {
        // One-frame triggers reset at end of frame so consumers that
        // read in update() see them exactly once.
        this.jumpPressed = false;
        this.firePressed = false;

        // Recompute continuous moveDir from keyboard state.
        let dx = 0, dy = 0;
        if (this._keyState[KeyCode.KEY_A] || this._keyState[KeyCode.ARROW_LEFT]) dx -= 1;
        if (this._keyState[KeyCode.KEY_D] || this._keyState[KeyCode.ARROW_RIGHT]) dx += 1;
        if (this._keyState[KeyCode.KEY_S] || this._keyState[KeyCode.ARROW_DOWN]) dy -= 1;
        if (this._keyState[KeyCode.KEY_W] || this._keyState[KeyCode.ARROW_UP]) dy += 1;
        // Normalize diagonals so they're not 1.414x faster.
        if (dx !== 0 && dy !== 0) { dx *= 0.707; dy *= 0.707; }
        this.moveDir.set(dx, dy);
    }

    private _onKeyDown(e: EventKeyboard) {
        this._keyState[e.keyCode] = true;
        if (e.keyCode === KeyCode.SPACE) this.jumpPressed = true;
        if (e.keyCode === KeyCode.KEY_J) this.firePressed = true;
    }

    private _onKeyUp(e: EventKeyboard) {
        this._keyState[e.keyCode] = false;
    }

    private _onTouchStart(_e: EventTouch) {
        this.firePressed = true;
    }

    private _onTouchEnd(_e: EventTouch) {
        // Could add swipe detection; leaving minimal for now.
    }
}
"""


def scaffold_input_abstraction(project_path: str | Path,
                               rel_path: str = "scripts/InputManager.ts") -> dict:
    """Generate InputManager.ts — a singleton MonoBehaviour that unifies
    keyboard + touch + single-tap input under a simple API:

        InputManager.I.moveDir       // cc.Vec2, normalized
        InputManager.I.jumpPressed   // bool, one-frame flag
        InputManager.I.firePressed   // bool, one-frame flag

    The script expects to be attached to a single node in the scene
    (typically a persistent 'GameManager' node). Other scripts read
    the public fields each update() tick.

    Writes the .ts file + its .meta via cocos.project.assets.add_script.
    Returns {path, rel_path, uuid_standard, uuid_compressed} —
    uuid_compressed is what cocos_add_script (scene-mutation) needs.
    """
    result = add_script(project_path, rel_path, _TEMPLATE)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

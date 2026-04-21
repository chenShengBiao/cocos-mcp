"""Scaffold for a full-screen UI panel controller (menu / settings / pause / over).

Every small game re-derives the same four UI screens: a title/menu with
a Start button, a settings overlay that can be toggled closed, a pause
overlay that listens for Escape, and a game-over screen that reads the
final score. Each one is a 60-100 line TS controller that imports the
canonical ``GameLoop`` (and optionally ``GameScore`` / ``InputManager``)
singletons and flips ``rootNode.active`` based on state. Rather than have
the orchestrating LLM retype the shape each time — and make subtly
different decisions about subscription vs polling or null-guarding the
singletons — we generate one targeted controller per ``kind`` here.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_MENU = """\
import { _decorator, Component, Node, Button } from 'cc';
import { GameLoop } from './GameLoop';
const { ccclass, property } = _decorator;

/**
 * Title / menu screen.
 *
 * Auto-shown whenever GameLoop.I.current === 'menu'; hidden for every
 * other state. The Start button transitions the loop into 'play' and
 * hides this panel. Uses polling in update() rather than an event
 * subscription because our GameLoop scaffold doesn't expose an emitter —
 * a once-per-frame string compare is well inside the noise floor for UI.
 */
@ccclass('MenuScreen')
export class MenuScreen extends Component {
    @property(Node)
    rootNode: Node | null = null;

    @property(Button)
    startButton: Button | null = null;

    onLoad() {
        if (this.startButton) {
            this.startButton.node.on(Button.EventType.CLICK, this._onStart, this);
        }
    }

    onDestroy() {
        if (this.startButton) {
            this.startButton.node.off(Button.EventType.CLICK, this._onStart, this);
        }
    }

    update(_dt: number) {
        // Guard null-ref: the user may not have attached GameLoop yet.
        const loop = GameLoop.I;
        if (!loop) return;
        const shouldShow = loop.current === 'menu';
        if (this.rootNode) this.rootNode.active = shouldShow;
    }

    public show() {
        if (this.rootNode) this.rootNode.active = true;
    }

    public hide() {
        if (this.rootNode) this.rootNode.active = false;
    }

    private _onStart() {
        const loop = GameLoop.I;
        if (!loop) return;
        loop.go('play');
        this.hide();
    }
}
"""

_SETTINGS = """\
import { _decorator, Component, Node, Button } from 'cc';
import { GameLoop } from './GameLoop';
const { ccclass, property } = _decorator;

/**
 * Toggleable settings panel.
 *
 * Unlike the other screens this is NOT driven by GameLoop.current — it
 * can be opened on top of any state without disturbing the loop. The
 * close button simply hides the panel (we import GameLoop anyway so
 * callers can wire state-aware behaviours if desired). External callers
 * can drive it via the exposed .show() / .hide() / .toggle() API.
 */
@ccclass('SettingsScreen')
export class SettingsScreen extends Component {
    @property(Node)
    rootNode: Node | null = null;

    @property(Button)
    closeButton: Button | null = null;

    onLoad() {
        if (this.closeButton) {
            this.closeButton.node.on(Button.EventType.CLICK, this._onClose, this);
        }
        // Start hidden by default; caller flips this via toggle().
        if (this.rootNode) this.rootNode.active = false;
    }

    onDestroy() {
        if (this.closeButton) {
            this.closeButton.node.off(Button.EventType.CLICK, this._onClose, this);
        }
    }

    public show() {
        if (this.rootNode) this.rootNode.active = true;
    }

    public hide() {
        if (this.rootNode) this.rootNode.active = false;
    }

    public toggle() {
        if (!this.rootNode) return;
        this.rootNode.active = !this.rootNode.active;
    }

    private _onClose() {
        // Preserve any GameLoop state — don't touch loop.current here.
        const _loop = GameLoop.I;
        this.hide();
    }
}
"""

_PAUSE = """\
import { _decorator, Component, Node, Button, Input, input, EventKeyboard, KeyCode } from 'cc';
import { GameLoop } from './GameLoop';
const { ccclass, property } = _decorator;

/**
 * Pause overlay — listens for the Escape key directly.
 *
 * We DON'T route through InputManager because that singleton only
 * tracks jumpPressed/firePressed triggers; pause needs its own KEY_DOWN
 * handler. Each Escape press toggles between 'pause' and 'play' states
 * on the GameLoop. The overlay itself is shown while
 * GameLoop.I.current === 'pause' and hidden otherwise.
 */
@ccclass('PauseScreen')
export class PauseScreen extends Component {
    @property(Node)
    rootNode: Node | null = null;

    @property(Button)
    resumeButton: Button | null = null;

    onLoad() {
        input.on(Input.EventType.KEY_DOWN, this._onKeyDown, this);
        if (this.resumeButton) {
            this.resumeButton.node.on(Button.EventType.CLICK, this._onResume, this);
        }
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this._onKeyDown, this);
        if (this.resumeButton) {
            this.resumeButton.node.off(Button.EventType.CLICK, this._onResume, this);
        }
    }

    update(_dt: number) {
        const loop = GameLoop.I;
        if (!loop) return;
        const shouldShow = loop.current === 'pause';
        if (this.rootNode) this.rootNode.active = shouldShow;
    }

    public show() {
        if (this.rootNode) this.rootNode.active = true;
    }

    public hide() {
        if (this.rootNode) this.rootNode.active = false;
    }

    private _onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.ESCAPE) return;
        const loop = GameLoop.I;
        if (!loop) return;
        if (loop.current === 'pause') {
            loop.go('play');
        } else if (loop.current === 'play') {
            loop.go('pause');
        }
    }

    private _onResume() {
        const loop = GameLoop.I;
        if (!loop) return;
        loop.go('play');
    }
}
"""

_GAME_OVER = """\
import { _decorator, Component, Node, Button, Label } from 'cc';
import { GameLoop } from './GameLoop';
import { GameScore } from './GameScore';
const { ccclass, property } = _decorator;

/**
 * Game-over screen.
 *
 * Shown when GameLoop.I.current === 'over'. Reads GameScore.I.current +
 * GameScore.I.high to populate the two labels each frame while visible
 * (cheap and avoids a refresh-race if the score updates on the same
 * tick the state flips). The Restart button resets the score and
 * transitions back to 'play'.
 */
@ccclass('GameOverScreen')
export class GameOverScreen extends Component {
    @property(Node)
    rootNode: Node | null = null;

    @property(Label)
    scoreLabel: Label | null = null;

    @property(Label)
    highLabel: Label | null = null;

    @property(Button)
    restartButton: Button | null = null;

    onLoad() {
        if (this.restartButton) {
            this.restartButton.node.on(Button.EventType.CLICK, this._onRestart, this);
        }
    }

    onDestroy() {
        if (this.restartButton) {
            this.restartButton.node.off(Button.EventType.CLICK, this._onRestart, this);
        }
    }

    update(_dt: number) {
        const loop = GameLoop.I;
        if (!loop) return;
        const shouldShow = loop.current === 'over';
        if (this.rootNode) this.rootNode.active = shouldShow;

        if (shouldShow) {
            const score = GameScore.I;
            if (score) {
                if (this.scoreLabel) this.scoreLabel.string = `Score: ${score.current}`;
                if (this.highLabel) this.highLabel.string = `High: ${score.high}`;
            }
        }
    }

    public show() {
        if (this.rootNode) this.rootNode.active = true;
    }

    public hide() {
        if (this.rootNode) this.rootNode.active = false;
    }

    private _onRestart() {
        const loop = GameLoop.I;
        const score = GameScore.I;
        if (score) score.reset();
        if (!loop) return;
        loop.go('play');
    }
}
"""

_TEMPLATES: dict[str, str] = {
    "menu": _MENU,
    "settings": _SETTINGS,
    "pause": _PAUSE,
    "game_over": _GAME_OVER,
}

_DEFAULT_REL_PATHS: dict[str, str] = {
    "menu": "MenuScreen.ts",
    "settings": "SettingsScreen.ts",
    "pause": "PauseScreen.ts",
    "game_over": "GameOverScreen.ts",
}

_VALID_KINDS: tuple[str, ...] = ("menu", "settings", "pause", "game_over")


def scaffold_ui_screen(project_path: str | Path,
                       kind: str = "menu",
                       rel_path: str | None = None) -> dict:
    """Generate <Kind>Screen.ts — a controller that manages a full-screen
    UI panel's show/hide + event wiring for common screens.

    Kinds:

      "menu" — title screen. @property startButton (cc.Button).
          Clicking start → GameLoop.I.go('play') + hide self.
          Auto-shown when GameLoop.I.current === 'menu'.

      "settings" — toggleable settings panel. @property closeButton.
          Close button hides the panel (preserves any GameLoop state).
          Exposed .show() / .hide() / .toggle() for external callers.

      "pause" — overlay that listens for Escape key directly via cc.input
          (InputManager only carries jump/fire triggers). Toggles
          'pause' ↔ 'play' on GameLoop. @property resumeButton.

      "game_over" — shown when GameLoop.I.current === 'over'. Reads
          GameScore.I.current + GameScore.I.high to populate
          @property scoreLabel + @property highLabel. @property
          restartButton → GameScore.I.reset() + GameLoop.I.go('play').

    Default rel_path (per kind):
      menu → "MenuScreen.ts"
      settings → "SettingsScreen.ts"
      pause → "PauseScreen.ts"
      game_over → "GameOverScreen.ts"

    Every variant uses @property rootNode (cc.Node) — set in Inspector
    to the root of the visual panel — and toggles its .active flag
    for show/hide.

    Returns {path, rel_path, uuid_standard, uuid_compressed}.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"kind must be one of {_VALID_KINDS}, got {kind!r}"
        )
    if rel_path is None:
        rel_path = _DEFAULT_REL_PATHS[kind]
    source = _TEMPLATES[kind]
    result = add_script(project_path, rel_path, source)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

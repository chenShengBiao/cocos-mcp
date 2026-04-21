"""Scaffold for a current/high-score singleton with persistence.

Score tracking is the second most common "why doesn't MCP just give me
this" after input. The generated singleton handles the two things that
are easy to get wrong: persisting the high score across sessions (via
localStorage, with the private-browsing failure mode swallowed) and
keeping an optional Label node in sync without the caller having to
retype the 'Score: N' render every place they bump points.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_TEMPLATE = """\
import { _decorator, Component, Label } from 'cc';
const { ccclass, property } = _decorator;

const STORAGE_KEY = 'cocos-mcp-high-score';

@ccclass('GameScore')
export class GameScore extends Component {
    private static _instance: GameScore | null = null;
    static get I(): GameScore { return GameScore._instance!; }

    @property(Label)
    scoreLabel: Label | null = null;

    @property({ tooltip: 'Optional - set from inspector to show HIGH too' })
    highLabel: Label | null = null;

    public current: number = 0;
    public high: number = 0;

    onLoad() {
        if (GameScore._instance && GameScore._instance !== this) {
            this.destroy();
            return;
        }
        GameScore._instance = this;

        const stored = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
        this.high = isFinite(stored) ? stored : 0;
        this._render();
    }

    onDestroy() {
        if (GameScore._instance === this) GameScore._instance = null;
    }

    add(points: number) {
        this.current += points;
        if (this.current > this.high) {
            this.high = this.current;
            try {
                localStorage.setItem(STORAGE_KEY, String(this.high));
            } catch (_e) {
                // Private-browsing / WeChat / etc may block localStorage;
                // don't crash gameplay over a missing high-score save.
            }
        }
        this._render();
    }

    reset() {
        this.current = 0;
        this._render();
    }

    private _render() {
        if (this.scoreLabel) this.scoreLabel.string = `Score: ${this.current}`;
        if (this.highLabel) this.highLabel.string = `High: ${this.high}`;
    }
}
"""


def scaffold_score_system(project_path: str | Path,
                          rel_path: str = "GameScore.ts") -> dict:
    """Generate GameScore.ts — a singleton that tracks current + high score
    with localStorage persistence. Exposes:

        GameScore.I.add(points: number)
        GameScore.I.reset()
        GameScore.I.current   // number
        GameScore.I.high      // number (best ever, persisted)

    If you attach this to a Label node, the script's @property target
    'scoreLabel' can be wired via cocos_link_property — on each add/reset
    the label auto-updates with 'Score: N'.

    Same return shape as scaffold_input_abstraction.
    """
    result = add_script(project_path, rel_path, _TEMPLATE)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

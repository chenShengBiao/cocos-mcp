#!/usr/bin/env python3
"""One-command Click Counter game using cocos-mcp API."""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cocos import build as cb, project as cp, scene_builder as sb, uuid_util as uu

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    dst = Path(args.output).resolve()

    info = cp.init_project(str(dst), project_name="click-counter")
    print(f"[1] init: {dst}")

    scene = sb.create_empty_scene(dst / "assets/scenes/Game.scene")
    SP, C = scene["scene_path"], scene["canvas_node_id"]

    score_n = sb.add_node(SP, C, "Score", lpos=(0, 200, 0))
    sb.add_uitransform(SP, score_n, 600, 200)
    score_lbl = sb.add_label(SP, score_n, "0", font_size=160)

    tip_n = sb.add_node(SP, C, "Tip", lpos=(0, -100, 0))
    sb.add_uitransform(SP, tip_n, 800, 80)
    tip_lbl = sb.add_label(SP, tip_n, "...", font_size=44)

    gm = sb.add_node(SP, C, "GM")
    script = cp.add_script(str(dst), "ClickCounter", '''import { _decorator, Component, Label, input, Input } from 'cc';
const { ccclass, property } = _decorator;
@ccclass('ClickCounter')
export class ClickCounter extends Component {
    @property(Label) scoreLabel: Label | null = null;
    @property(Label) tipLabel: Label | null = null;
    private score = 0;
    onLoad() { if (this.tipLabel) this.tipLabel.string = 'Click anywhere!'; }
    start() { input.on(Input.EventType.MOUSE_DOWN, this.onClick, this); }
    onDestroy() { input.off(Input.EventType.MOUSE_DOWN, this.onClick, this); }
    onClick() {
        this.score++;
        if (this.scoreLabel) this.scoreLabel.string = String(this.score);
        if (this.tipLabel && this.score >= 5) this.tipLabel.string = `Nice! ${this.score} clicks!`;
    }
}''')
    short = uu.compress_uuid(script["uuid"])
    sb.add_script(SP, gm, short, props={"scoreLabel": score_lbl, "tipLabel": tip_lbl})

    v = sb.validate_scene(SP)
    print(f"[2] scene: {v['object_count']} objects, valid={v['valid']}")

    print("[3] building...")
    r = cb.cli_build(str(dst))
    print(f"    success={r['success']} {r['duration_sec']}s")
    if r['success']:
        p = cb.start_preview(str(dst), port=args.port)
        print(f"[4] {p.get('url')}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""One-command Flappy Bird builder using cocos-mcp API.

Usage:
    python build_flappy.py /path/to/output [--port 8080]

Creates a complete Flappy Bird game from scratch:
  - Init project from empty-2d template
  - Write 6 TypeScript scripts (GameHub/GameManager/Bird/Pipe/PipeSpawner/Ground)
  - Build 48-object scene (Canvas/UICamera/Ground/PipeContainer/Bird/UIRoot/GameManager)
  - Headless CLI build → web-mobile
  - Start local HTTP preview

Everything uses cocos-mcp modules — no hand-written scene JSON.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from cocos import build as cb, project as cp, scene_builder as sb, uuid_util as uu

SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"


def main():
    parser = argparse.ArgumentParser(description="Build Flappy Bird with cocos-mcp")
    parser.add_argument("output", help="Output project directory")
    parser.add_argument("--port", type=int, default=8080, help="Preview HTTP port")
    parser.add_argument("--no-build", action="store_true", help="Skip CLI build")
    parser.add_argument("--no-preview", action="store_true", help="Skip HTTP preview")
    args = parser.parse_args()

    dst = Path(args.output).expanduser().resolve()
    print(f"Building Flappy Bird at {dst}")

    # 1. Init project
    info = cp.init_project(str(dst), template="empty-2d", project_name="flappy-bird")
    print(f"[1] init: creator {info['creator_version']}")

    # 2. Write scripts + collect UUIDs
    scripts = {}
    for ts_file in sorted(SCRIPTS_DIR.glob("*.ts")):
        name = ts_file.stem
        source = ts_file.read_text()
        result = cp.add_script(str(dst), name, source)
        scripts[name] = {
            "uuid": result["uuid"],
            "short": uu.compress_uuid(result["uuid"]),
        }
        print(f"[2] script {name}: {result['uuid'][:12]}...")

    # 3. Create scene
    scene = sb.create_empty_scene(
        dst / "assets/scenes/Game.scene",
        canvas_width=960, canvas_height=640,
        clear_color=(135, 206, 235, 255),
    )
    SP = scene["scene_path"]
    CANVAS = scene["canvas_node_id"]
    print(f"[3] scene: canvas={CANVAS}")

    # 4. Ground node
    ground_n = sb.add_node(SP, CANVAS, "Ground", lpos=(0, -280, 0))
    sb.add_uitransform(SP, ground_n, 960, 80)
    sb.add_graphics(SP, ground_n)
    sb.add_script(SP, ground_n, scripts["Ground"]["short"], props={
        "width": 960.0, "height": 80.0, "speed": 160.0,
    })

    # 5. PipeContainer node
    pipe_ct = sb.add_node(SP, CANVAS, "PipeContainer")
    sb.add_uitransform(SP, pipe_ct, 100, 100)
    pipe_spawner_cmp = sb.add_script(SP, pipe_ct, scripts["PipeSpawner"]["short"], props={
        "spawnInterval": 1.6, "pipeSpeed": 160.0, "gap": 180.0,
        "pipeWidth": 80.0, "spawnX": 560.0, "despawnX": -560.0,
        "minGapY": -120.0, "maxGapY": 120.0,
    })

    # 6. Bird node
    bird_n = sb.add_node(SP, CANVAS, "Bird", lpos=(-200, 40, 0))
    sb.add_uitransform(SP, bird_n, 50, 50)
    sb.add_graphics(SP, bird_n)
    bird_cmp = sb.add_script(SP, bird_n, scripts["Bird"]["short"], props={
        "jumpVelocity": 520.0, "gravity": 1500.0, "radius": 22.0,
        "startY": 40.0, "ceilingY": 300.0, "floorY": -240.0,
    })

    # 7. UI Root
    ui_root = sb.add_node(SP, CANVAS, "UIRoot")
    sb.add_uitransform(SP, ui_root, 960, 640)

    # Score label
    score_n = sb.add_node(SP, ui_root, "ScoreLabel", lpos=(0, 240, 0))
    sb.add_uitransform(SP, score_n, 300, 100)
    score_lbl = sb.add_label(SP, score_n, "0", font_size=80)

    # Tip label
    tip_n = sb.add_node(SP, ui_root, "TipLabel", lpos=(0, -40, 0))
    sb.add_uitransform(SP, tip_n, 700, 80)
    tip_lbl = sb.add_label(SP, tip_n, "Tap / Space to Start", font_size=36)

    # GameOver panel (inactive)
    gop = sb.add_node(SP, ui_root, "GameOverPanel", lpos=(0, 20, 0), active=False)
    sb.add_uitransform(SP, gop, 700, 360)

    got_n = sb.add_node(SP, gop, "GameOverTitle", lpos=(0, 100, 0))
    sb.add_uitransform(SP, got_n, 700, 100)
    sb.add_label(SP, got_n, "GAME OVER", font_size=72, color=(255, 90, 80, 255))

    fsl_n = sb.add_node(SP, gop, "FinalScoreLabel", lpos=(0, 0, 0))
    sb.add_uitransform(SP, fsl_n, 700, 60)
    fsl_lbl = sb.add_label(SP, fsl_n, "Score 0   Best 0", font_size=42)

    rt_n = sb.add_node(SP, gop, "RestartTip", lpos=(0, -100, 0))
    sb.add_uitransform(SP, rt_n, 700, 60)
    sb.add_label(SP, rt_n, "Tap / Space to Restart", font_size=34)

    # 8. GameManager node
    gm_n = sb.add_node(SP, CANVAS, "GameManager")
    sb.add_script(SP, gm_n, scripts["GameManager"]["short"], props={
        "bird": bird_cmp,
        "pipeSpawner": pipe_spawner_cmp,
        "scoreLabel": score_lbl,
        "tipLabel": tip_lbl,
        "gameOverPanel": gop,
        "finalScoreLabel": fsl_lbl,
    })

    # 9. Validate
    v = sb.validate_scene(SP)
    print(f"[9] validate: {v['object_count']} objects, valid={v['valid']}, issues={len(v['issues'])}")
    if not v["valid"]:
        for issue in v["issues"][:10]:
            print(f"    {issue}")
        sys.exit(2)

    # 10. Build
    if not args.no_build:
        print("[10] building ...")
        result = cb.cli_build(str(dst), platform="web-mobile", debug=True)
        print(f"     exit={result['exit_code']} success={result['success']} {result['duration_sec']}s")
        if not result["success"]:
            print(result["log_tail"][-500:])
            sys.exit(3)
    else:
        print("[10] skipped (--no-build)")

    # 11. Preview
    if not args.no_build and not args.no_preview:
        cb.stop_preview(args.port)
        preview = cb.start_preview(str(dst), port=args.port)
        print(f"[11] preview: {preview.get('url')}")
    else:
        print("[11] skipped")

    print(f"\n✓ Flappy Bird ready at {dst}")


if __name__ == "__main__":
    main()

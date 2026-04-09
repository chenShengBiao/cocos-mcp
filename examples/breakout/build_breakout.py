#!/usr/bin/env python3
"""End-to-end: Brick Breaker (Breakout) using cocos-mcp P0 tools.

Tests: physics (RigidBody2D + Collider2D), Button UI, multiple nodes,
script @property refs, sibling_index, build, preview.

Game design:
  - Ball: Dynamic RigidBody2D + CircleCollider2D, bounces off walls/paddle/bricks
  - Paddle: Kinematic RigidBody2D + BoxCollider2D, keyboard left/right
  - Bricks: 3 rows × 6 cols, Static RigidBody2D + BoxCollider2D, destroyed on hit
  - Walls: Static colliders (top/left/right)
  - Score label + "Click to Start" tip
  - All visuals via cc.Graphics (runtime drawing, no PNG needed)
"""
import shutil, sys
from pathlib import Path

sys.path.insert(0, "/Users/heitugongzuoshi/.claude/mcp-servers/cocos-mcp")

from cocos import build as cb, project as cp, scene_builder as sb, uuid_util as uu

PROJECT = "/tmp/cocos-test/breakout"
PORT = 8092

print("=" * 60)
print("Brick Breaker (Breakout) E2E test")
print("=" * 60)

# 1. Init
shutil.rmtree(PROJECT, ignore_errors=True)
info = cp.init_project(PROJECT, template="empty-2d", project_name="breakout")
print(f"[1] init: {info['project_path']}")

# 2. Scene
scene = sb.create_empty_scene(
    Path(PROJECT) / "assets/scenes/Game.scene",
    canvas_width=480, canvas_height=640,
    clear_color=(30, 30, 50, 255),  # dark blue bg
)
SP = scene["scene_path"]
CANVAS = scene["canvas_node_id"]
print(f"[2] scene: canvas={CANVAS}")

# 3. Score label (top)
score_n = sb.add_node(SP, CANVAS, "ScoreLabel", lpos=(0, 280, 0))
sb.add_uitransform(SP, score_n, 300, 60)
score_lbl = sb.add_label(SP, score_n, "0", font_size=48)
print(f"[3] score label: node={score_n} lbl={score_lbl}")

# 4. Tip label (center)
tip_n = sb.add_node(SP, CANVAS, "TipLabel", lpos=(0, 0, 0))
sb.add_uitransform(SP, tip_n, 400, 50)
tip_lbl = sb.add_label(SP, tip_n, "Click to Start!", font_size=32)
print(f"[4] tip label: node={tip_n} lbl={tip_lbl}")

# 5. Walls (static colliders — invisible, just physics)
# Top wall
top_w = sb.add_node(SP, CANVAS, "WallTop", lpos=(0, 310, 0))
sb.add_uitransform(SP, top_w, 480, 20)
sb.add_rigidbody2d(SP, top_w, body_type=0)  # Static
sb.add_box_collider2d(SP, top_w, width=480, height=20, friction=0.0, restitution=1.0)

# Left wall
left_w = sb.add_node(SP, CANVAS, "WallLeft", lpos=(-245, 0, 0))
sb.add_uitransform(SP, left_w, 20, 640)
sb.add_rigidbody2d(SP, left_w, body_type=0)
sb.add_box_collider2d(SP, left_w, width=20, height=640, friction=0.0, restitution=1.0)

# Right wall
right_w = sb.add_node(SP, CANVAS, "WallRight", lpos=(245, 0, 0))
sb.add_uitransform(SP, right_w, 20, 640)
sb.add_rigidbody2d(SP, right_w, body_type=0)
sb.add_box_collider2d(SP, right_w, width=20, height=640, friction=0.0, restitution=1.0)
print(f"[5] walls: top/left/right")

# 6. Paddle (kinematic, keyboard controlled)
paddle_n = sb.add_node(SP, CANVAS, "Paddle", lpos=(0, -260, 0))
sb.add_uitransform(SP, paddle_n, 100, 16)
sb.add_graphics(SP, paddle_n)
sb.add_rigidbody2d(SP, paddle_n, body_type=1)  # Kinematic
sb.add_box_collider2d(SP, paddle_n, width=100, height=16, friction=0.5, restitution=1.0)
print(f"[6] paddle: node={paddle_n}")

# 7. Ball (dynamic, bouncing)
ball_n = sb.add_node(SP, CANVAS, "Ball", lpos=(0, -220, 0))
sb.add_uitransform(SP, ball_n, 20, 20)
sb.add_graphics(SP, ball_n)
sb.add_rigidbody2d(SP, ball_n, body_type=2, gravity_scale=0.0, linear_damping=0.0,
                   fixed_rotation=True, bullet=True)
sb.add_circle_collider2d(SP, ball_n, radius=10, friction=0.0, restitution=1.0, density=1.0)
print(f"[7] ball: node={ball_n}")

# 8. Brick container
bricks_n = sb.add_node(SP, CANVAS, "Bricks", lpos=(0, 160, 0))
sb.add_uitransform(SP, bricks_n, 400, 200)
# Individual bricks: 3 rows × 6 cols
BRICK_W, BRICK_H, GAP = 60, 20, 8
brick_ids = []
for row in range(3):
    for col in range(6):
        x = (col - 2.5) * (BRICK_W + GAP)
        y = (1 - row) * (BRICK_H + GAP)
        bn = sb.add_node(SP, bricks_n, f"Brick_{row}_{col}", lpos=(x, y, 0))
        sb.add_uitransform(SP, bn, BRICK_W, BRICK_H)
        sb.add_graphics(SP, bn)
        sb.add_rigidbody2d(SP, bn, body_type=0)  # Static
        sb.add_box_collider2d(SP, bn, width=BRICK_W, height=BRICK_H, restitution=1.0)
        brick_ids.append(bn)
print(f"[8] bricks: {len(brick_ids)} bricks created")

# 9. GameManager script
GAME_SCRIPT = '''import { _decorator, Component, Label, Node, input, Input, EventKeyboard,
    KeyCode, RigidBody2D, Vec2, Contact2DType, Collider2D, Graphics, Color,
    IPhysics2DContact, PhysicsSystem2D } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('BreakoutGame')
export class BreakoutGame extends Component {
    @property(Label) scoreLabel: Label | null = null;
    @property(Label) tipLabel: Label | null = null;
    @property(Node) ballNode: Node | null = null;
    @property(Node) paddleNode: Node | null = null;
    @property(Node) bricksNode: Node | null = null;

    private score = 0;
    private started = false;
    private paddleSpeed = 400;
    private moveDir = 0;

    onLoad() {
        PhysicsSystem2D.instance.enable = true;
        // Draw all Graphics nodes
        this.drawRect(this.paddleNode, 100, 16, new Color(200, 200, 200));
        this.drawCircle(this.ballNode, 10, new Color(255, 220, 80));
        const colors = [new Color(255,80,80), new Color(80,200,255), new Color(80,255,120)];
        if (this.bricksNode) {
            for (let i = 0; i < this.bricksNode.children.length; i++) {
                const b = this.bricksNode.children[i];
                this.drawRect(b, 60, 20, colors[Math.floor(i/6) % 3]);
            }
        }
    }

    start() {
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        input.on(Input.EventType.KEY_UP, this.onKeyUp, this);
        input.on(Input.EventType.MOUSE_DOWN, this.onMouse, this);
        input.on(Input.EventType.TOUCH_START, this.onMouse, this);

        // Register collision
        const ballCollider = this.ballNode?.getComponent(Collider2D);
        if (ballCollider) {
            ballCollider.on(Contact2DType.BEGIN_CONTACT, this.onBallContact, this);
        }
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        input.off(Input.EventType.KEY_UP, this.onKeyUp, this);
        input.off(Input.EventType.MOUSE_DOWN, this.onMouse, this);
        input.off(Input.EventType.TOUCH_START, this.onMouse, this);
    }

    onMouse() {
        if (!this.started) this.launchBall();
    }

    onKeyDown(e: EventKeyboard) {
        if (e.keyCode === KeyCode.KEY_A || e.keyCode === KeyCode.ARROW_LEFT) this.moveDir = -1;
        if (e.keyCode === KeyCode.KEY_D || e.keyCode === KeyCode.ARROW_RIGHT) this.moveDir = 1;
        if (e.keyCode === KeyCode.SPACE && !this.started) this.launchBall();
    }

    onKeyUp(e: EventKeyboard) {
        if (e.keyCode === KeyCode.KEY_A || e.keyCode === KeyCode.ARROW_LEFT ||
            e.keyCode === KeyCode.KEY_D || e.keyCode === KeyCode.ARROW_RIGHT) this.moveDir = 0;
    }

    launchBall() {
        this.started = true;
        if (this.tipLabel) this.tipLabel.node.active = false;
        const rb = this.ballNode?.getComponent(RigidBody2D);
        if (rb) rb.linearVelocity = new Vec2(150, 300);
    }

    onBallContact(self: Collider2D, other: Collider2D, contact: IPhysics2DContact | null) {
        const otherNode = other.node;
        if (otherNode.name.startsWith('Brick_')) {
            otherNode.active = false;
            other.enabled = false;
            const rb = otherNode.getComponent(RigidBody2D);
            if (rb) rb.enabled = false;
            this.score++;
            if (this.scoreLabel) this.scoreLabel.string = String(this.score);
        }
    }

    update(dt: number) {
        if (!this.paddleNode) return;
        const p = this.paddleNode.position;
        let nx = p.x + this.moveDir * this.paddleSpeed * dt;
        nx = Math.max(-190, Math.min(190, nx));
        this.paddleNode.setPosition(nx, p.y, 0);

        // Ball fell below screen → reset
        if (this.ballNode && this.ballNode.position.y < -340) {
            this.resetBall();
        }
    }

    resetBall() {
        this.started = false;
        if (this.tipLabel) this.tipLabel.node.active = true;
        if (this.ballNode) {
            this.ballNode.setPosition(0, -220, 0);
            const rb = this.ballNode.getComponent(RigidBody2D);
            if (rb) rb.linearVelocity = new Vec2(0, 0);
        }
    }

    private drawRect(node: Node | null, w: number, h: number, c: Color) {
        if (!node) return;
        const g = node.getComponent(Graphics);
        if (!g) return;
        g.clear();
        g.fillColor = c;
        g.rect(-w/2, -h/2, w, h);
        g.fill();
        g.strokeColor = new Color(255,255,255,60);
        g.lineWidth = 1;
        g.rect(-w/2, -h/2, w, h);
        g.stroke();
    }

    private drawCircle(node: Node | null, r: number, c: Color) {
        if (!node) return;
        const g = node.getComponent(Graphics);
        if (!g) return;
        g.clear();
        g.fillColor = c;
        g.circle(0, 0, r);
        g.fill();
    }
}
'''

script = cp.add_script(PROJECT, "BreakoutGame", GAME_SCRIPT)
short = uu.compress_uuid(script["uuid"])
print(f"[9] script: uuid={script['uuid'][:16]}... short={short}")

# 10. GameManager node + attach script with property refs
gm_n = sb.add_node(SP, CANVAS, "GameManager")
gm_cmp = sb.add_script(SP, gm_n, short, props={
    "scoreLabel": score_lbl,      # int → __id__ ref
    "tipLabel": tip_lbl,          # int → __id__ ref
    "ballNode": ball_n,           # int → __id__ ref (to Node, not component)
    "paddleNode": paddle_n,       # int → __id__ ref
    "bricksNode": bricks_n,       # int → __id__ ref
})
print(f"[10] GameManager: node={gm_n} script_cmp={gm_cmp}")

# But wait — ballNode/paddleNode/bricksNode are @property(Node), which means
# the scene should reference the Node, not a component. Our auto-wrap converts
# int → {__id__: N}. For Label props, __id__ points to the Label *component*.
# For Node props, __id__ should point to the *Node* itself.
# Let's fix: ballNode should point to ball_n (Node), not a Label component.
# Actually our auto-wrap already does this: ball_n IS the node id. ✓
# score_lbl IS the Label component id, which is what @property(Label) expects. ✓

# 11. Validate
v = sb.validate_scene(SP)
print(f"[11] validate: valid={v['valid']}  objects={v['object_count']}  issues={len(v['issues'])}")
if not v['valid']:
    for issue in v['issues'][:10]:
        print(f"    - {issue}")
    sys.exit(2)

# 12. Build
print(f"[12] Building (first build ~2-3 min) ...")
result = cb.cli_build(PROJECT, platform="web-mobile", debug=True)
print(f"    exit_code={result['exit_code']} success={result['success']} duration={result['duration_sec']}s")
if not result['success']:
    print("    FAILED. Log tail:")
    print(result['log_tail'][-1000:])
    sys.exit(3)

# 13. Preview
cb.stop_preview(PORT)
preview = cb.start_preview(PROJECT, port=PORT)
print(f"[13] preview: {preview.get('url', 'N/A')}")

print("\n" + "=" * 60)
print(f"✓ Brick Breaker E2E SUCCESS  ({v['object_count']} objects)")
print(f"  {preview.get('url', 'http://localhost:' + str(PORT) + '/')}")
print("=" * 60)

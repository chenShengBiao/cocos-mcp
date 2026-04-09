import { _decorator, Component, Label, Node, input, Input, EventKeyboard, KeyCode, profiler, Graphics, Color, UITransform } from 'cc';
import { GameHub, GameState } from './GameHub';
import { Bird } from './Bird';
import { PipeSpawner } from './PipeSpawner';
const { ccclass, property } = _decorator;

interface CloudInfo {
    node: Node;
    speed: number;
}

@ccclass('GameManager')
export class GameManager extends Component {

    @property(Bird)
    bird: Bird | null = null;

    @property(PipeSpawner)
    pipeSpawner: PipeSpawner | null = null;

    @property(Label)
    scoreLabel: Label | null = null;

    @property(Label)
    tipLabel: Label | null = null;

    @property(Node)
    gameOverPanel: Node | null = null;

    @property(Label)
    finalScoreLabel: Label | null = null;

    private _clouds: CloudInfo[] = [];

    onLoad() {
        GameHub.onScoreChanged = (s) => {
            if (this.scoreLabel) this.scoreLabel.string = s.toString();
        };
        GameHub.onStateChanged = (s) => this.onStateChanged(s);

        // 关闭调试性能面板
        try { profiler.hideStats(); } catch { /* ignore */ }
    }

    start() {
        input.on(Input.EventType.TOUCH_START, this.onInput, this);
        input.on(Input.EventType.MOUSE_DOWN, this.onInput, this);
        input.on(Input.EventType.KEY_DOWN, this.onKey, this);

        if (this.bird) GameHub.bird = this.bird;

        // 在 Canvas 下创建云朵层（动态生成，避免改动场景）
        this.createClouds();

        this.enterReady();
    }

    onDestroy() {
        input.off(Input.EventType.TOUCH_START, this.onInput, this);
        input.off(Input.EventType.MOUSE_DOWN, this.onInput, this);
        input.off(Input.EventType.KEY_DOWN, this.onKey, this);
        GameHub.onScoreChanged = null;
        GameHub.onStateChanged = null;
    }

    private onKey(event: EventKeyboard) {
        if (event.keyCode === KeyCode.SPACE || event.keyCode === KeyCode.ENTER || event.keyCode === KeyCode.ARROW_UP) {
            this.onInput();
        }
    }

    private onInput() {
        switch (GameHub.state) {
            case GameState.Ready:
                this.enterPlaying();
                this.bird?.flap();
                break;
            case GameState.Playing:
                this.bird?.flap();
                break;
            case GameState.Dead:
                this.enterReady();
                break;
        }
    }

    private enterReady() {
        GameHub.resetScore();
        GameHub.setState(GameState.Ready);
        this.bird?.reset();
        this.pipeSpawner?.reset();
        if (this.tipLabel) {
            this.tipLabel.node.active = true;
            this.tipLabel.string = 'Tap / Space to Start';
        }
        if (this.gameOverPanel) this.gameOverPanel.active = false;
    }

    private enterPlaying() {
        GameHub.setState(GameState.Playing);
        if (this.tipLabel) this.tipLabel.node.active = false;
    }

    private onStateChanged(s: GameState) {
        if (s === GameState.Dead) {
            if (this.gameOverPanel) this.gameOverPanel.active = true;
            if (this.finalScoreLabel) {
                this.finalScoreLabel.string = `Score ${GameHub.score}   Best ${GameHub.best}`;
            }
        }
    }

    // ---------- 云朵背景 ----------
    private createClouds() {
        const canvas = this.node.parent;
        if (!canvas) return;

        for (let i = 0; i < 6; i++) {
            const c = new Node('Cloud');
            c.layer = this.node.layer;
            canvas.addChild(c);
            // 把云朵层推到 UICamera 之后、其它游戏元素之前
            c.setSiblingIndex(1);

            c.addComponent(UITransform);
            c.setPosition(
                -500 + Math.random() * 1000,
                80 + Math.random() * 220,
                0
            );
            const scale = 0.6 + Math.random() * 0.8;
            c.setScale(scale, scale, 1);

            const g = c.addComponent(Graphics);
            this.drawCloud(g);

            this._clouds.push({
                node: c,
                speed: 12 + Math.random() * 18,
            });
        }
    }

    private drawCloud(g: Graphics) {
        const white = new Color(255, 255, 255, 230);
        const shadow = new Color(220, 235, 245, 230);
        g.fillColor = shadow;
        g.ellipse(-24, -6, 28, 14);
        g.fill();
        g.ellipse(22, -6, 26, 12);
        g.fill();
        g.ellipse(0, -8, 32, 14);
        g.fill();

        g.fillColor = white;
        g.circle(-22, 0, 20);
        g.fill();
        g.circle(0, 8, 26);
        g.fill();
        g.circle(22, 2, 22);
        g.fill();
        g.circle(-6, -4, 22);
        g.fill();
        g.circle(12, -6, 20);
        g.fill();
    }

    update(dt: number) {
        // 云朵在 Ready 和 Playing 都滚动；Dead 时停下
        if (GameHub.state === GameState.Dead) return;
        for (const c of this._clouds) {
            const p = c.node.position;
            let nx = p.x - c.speed * dt;
            if (nx < -560) nx = 560;
            c.node.setPosition(nx, p.y, 0);
        }
    }
}

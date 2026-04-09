import { _decorator, Component, Vec3, Graphics, Color, math } from 'cc';
import { GameHub, GameState, IBirdLike } from './GameHub';
const { ccclass, property } = _decorator;

@ccclass('Bird')
export class Bird extends Component implements IBirdLike {
    @property
    jumpVelocity: number = 520;

    @property
    gravity: number = 1500;

    @property
    radius: number = 22;

    @property
    startY: number = 40;

    @property
    ceilingY: number = 300;

    @property
    floorY: number = -240;

    private velocity: number = 0;
    private idleTimer: number = 0;
    private _alive: boolean = true;
    private _g: Graphics | null = null;
    private _wingTimer: number = 0;
    private _wingFrame: number = 0; // 0=中, 1=上, 2=中, 3=下

    onLoad() {
        this._g = this.getComponent(Graphics) || this.addComponent(Graphics);
        this.drawBird(0);
    }

    start() {
        this.reset();
    }

    private drawBird(wingFrame: number) {
        const g = this._g;
        if (!g) return;
        g.clear();

        // body (yellow)
        g.fillColor = new Color(255, 210, 80, 255);
        g.circle(0, 0, this.radius);
        g.fill();

        // belly highlight
        g.fillColor = new Color(255, 240, 180, 255);
        g.ellipse(-2, -6, 14, 8);
        g.fill();

        // body outline
        g.lineWidth = 3;
        g.strokeColor = new Color(60, 40, 10, 255);
        g.circle(0, 0, this.radius);
        g.stroke();

        // wing（扇动动画）
        const wingY = [-4, 4, -4, -12][wingFrame] ?? -4;
        const wingH = [6, 4, 6, 8][wingFrame] ?? 6;
        g.fillColor = new Color(240, 150, 40, 255);
        g.ellipse(-6, wingY, 12, wingH);
        g.fill();
        g.lineWidth = 1.5;
        g.strokeColor = new Color(120, 60, 0, 255);
        g.ellipse(-6, wingY, 12, wingH);
        g.stroke();

        // head crest
        g.fillColor = new Color(240, 150, 40, 255);
        g.moveTo(0, 18);
        g.lineTo(4, 26);
        g.lineTo(-4, 22);
        g.close();
        g.fill();

        // eye white
        g.fillColor = new Color(255, 255, 255, 255);
        g.circle(9, 7, 6);
        g.fill();
        g.strokeColor = new Color(60, 40, 10, 255);
        g.lineWidth = 1.5;
        g.circle(9, 7, 6);
        g.stroke();

        // pupil
        g.fillColor = new Color(0, 0, 0, 255);
        g.circle(11, 7, 2.6);
        g.fill();
        g.fillColor = new Color(255, 255, 255, 255);
        g.circle(12, 8, 0.8);
        g.fill();

        // beak
        g.fillColor = new Color(255, 140, 40, 255);
        g.moveTo(16, 2);
        g.lineTo(30, 6);
        g.lineTo(16, 10);
        g.close();
        g.fill();
        g.strokeColor = new Color(120, 60, 0, 255);
        g.lineWidth = 1.5;
        g.moveTo(16, 2);
        g.lineTo(30, 6);
        g.lineTo(16, 10);
        g.close();
        g.stroke();
    }

    public reset() {
        this.velocity = 0;
        this.idleTimer = 0;
        this._alive = true;
        this.node.setPosition(new Vec3(-200, this.startY, 0));
        this.node.angle = 0;
    }

    public flap() {
        if (!this._alive) return;
        this.velocity = this.jumpVelocity;
    }

    public kill() {
        this._alive = false;
    }

    public isAlive() {
        return this._alive;
    }

    public getRadius() {
        return this.radius;
    }

    private tickWing(dt: number, alive: boolean) {
        if (!alive) return;
        this._wingTimer += dt;
        if (this._wingTimer >= 0.1) {
            this._wingTimer = 0;
            this._wingFrame = (this._wingFrame + 1) % 4;
            this.drawBird(this._wingFrame);
        }
    }

    update(dt: number) {
        if (GameHub.state === GameState.Ready) {
            this.idleTimer += dt;
            const y = this.startY + Math.sin(this.idleTimer * 6) * 8;
            this.node.setPosition(-200, y, 0);
            this.node.angle = 0;
            this.tickWing(dt, true);
            return;
        }

        if (GameHub.state === GameState.Dead) {
            // 死亡后保持下落动画（无翅膀扇动）
            this.velocity -= this.gravity * dt;
            const p = this.node.position;
            let ny = p.y + this.velocity * dt;
            if (ny < this.floorY) ny = this.floorY;
            this.node.setPosition(p.x, ny, 0);
            this.node.angle = math.clamp(this.velocity / 8, -80, 30);
            return;
        }

        // Playing
        this.velocity -= this.gravity * dt;
        const p = this.node.position;
        let ny = p.y + this.velocity * dt;

        if (ny > this.ceilingY) {
            ny = this.ceilingY;
            this.velocity = 0;
        }

        this.node.setPosition(p.x, ny, 0);
        this.node.angle = math.clamp(this.velocity / 8, -80, 30);
        this.tickWing(dt, this._alive);

        if (ny <= this.floorY) {
            this.node.setPosition(p.x, this.floorY, 0);
            this._alive = false;
            GameHub.gameOver();
        }
    }
}

import { _decorator, Component, Node, Graphics, Color } from 'cc';
import { GameHub, GameState } from './GameHub';
const { ccclass, property } = _decorator;

/**
 * 一对水管（上+下）+ gap，运行时由 PipeSpawner 用 addComponent 创建，不依赖 Prefab。
 */
@ccclass('Pipe')
export class Pipe extends Component {
    public speed: number = 160;
    public width: number = 80;
    public gap: number = 180;
    public killY: number = -400;
    public ceilY: number = 400;
    public gapY: number = 0;
    public scored: boolean = false;

    public init(startX: number, gapY: number, speed: number, gap: number, width: number) {
        this.gapY = gapY;
        this.speed = speed;
        this.gap = gap;
        this.width = width;
        this.scored = false;
        this.node.setPosition(startX, 0, 0);
        this.draw();
    }

    private draw() {
        // 上水管
        let top = this.node.getChildByName('Top');
        if (!top) {
            top = new Node('Top');
            top.layer = this.node.layer;
            this.node.addChild(top);
        }
        const topG = top.getComponent(Graphics) || top.addComponent(Graphics);
        const topH = this.ceilY - (this.gapY + this.gap / 2);
        const topCenterY = this.gapY + this.gap / 2 + topH / 2;
        top.setPosition(0, topCenterY, 0);
        this.drawPipeRect(topG, topH, false);

        // 下水管
        let bot = this.node.getChildByName('Bot');
        if (!bot) {
            bot = new Node('Bot');
            bot.layer = this.node.layer;
            this.node.addChild(bot);
        }
        const botG = bot.getComponent(Graphics) || bot.addComponent(Graphics);
        const botH = (this.gapY - this.gap / 2) - this.killY;
        const botCenterY = this.killY + botH / 2;
        bot.setPosition(0, botCenterY, 0);
        this.drawPipeRect(botG, botH, true);
    }

    private drawPipeRect(g: Graphics, height: number, isBottom: boolean) {
        g.clear();
        const w = this.width;
        const h = height;

        // body
        g.fillColor = new Color(112, 196, 84, 255);
        g.rect(-w / 2, -h / 2, w, h);
        g.fill();

        // outline
        g.strokeColor = new Color(40, 80, 20, 255);
        g.lineWidth = 3;
        g.rect(-w / 2, -h / 2, w, h);
        g.stroke();

        // highlight stripe
        g.fillColor = new Color(160, 230, 120, 255);
        g.rect(-w / 2 + 6, -h / 2, 6, h);
        g.fill();

        // rim
        const rimH = 18;
        const rimW = w + 16;
        const rimY = isBottom ? (h / 2 - rimH / 2) : (-h / 2 + rimH / 2);
        g.fillColor = new Color(112, 196, 84, 255);
        g.rect(-rimW / 2, rimY - rimH / 2, rimW, rimH);
        g.fill();
        g.strokeColor = new Color(40, 80, 20, 255);
        g.lineWidth = 3;
        g.rect(-rimW / 2, rimY - rimH / 2, rimW, rimH);
        g.stroke();
        g.fillColor = new Color(160, 230, 120, 255);
        g.rect(-rimW / 2 + 6, rimY - rimH / 2, 6, rimH);
        g.fill();
    }

    update(dt: number) {
        if (GameHub.state !== GameState.Playing) return;

        const p = this.node.position;
        this.node.setPosition(p.x - this.speed * dt, p.y, p.z);

        const bird = GameHub.bird;
        if (!bird || !bird.isAlive()) return;
        const bp = bird.node.position;
        const br = bird.getRadius();

        const px = this.node.position.x;
        const halfW = this.width / 2 + 8;

        // 得分：鸟中心越过水管中心
        if (!this.scored && bp.x > px) {
            this.scored = true;
            GameHub.addScore();
        }

        // AABB vs 圆粗略碰撞
        if (Math.abs(bp.x - px) < halfW + br) {
            const topEdge = this.gapY + this.gap / 2;
            const botEdge = this.gapY - this.gap / 2;
            if (bp.y + br > topEdge || bp.y - br < botEdge) {
                bird.kill();
                GameHub.gameOver();
            }
        }
    }
}

import { _decorator, Component, Graphics, Color } from 'cc';
import { GameHub, GameState } from './GameHub';
const { ccclass, property } = _decorator;

@ccclass('Ground')
export class Ground extends Component {
    @property
    width: number = 960;

    @property
    height: number = 80;

    @property
    speed: number = 160;

    private offset: number = 0;
    private g: Graphics | null = null;

    onLoad() {
        this.g = this.getComponent(Graphics) || this.addComponent(Graphics);
        this.redraw();
    }

    private redraw() {
        if (!this.g) return;
        const g = this.g;
        g.clear();
        const w = this.width;
        const h = this.height;
        const halfW = w / 2;
        const halfH = h / 2;

        // 主地面（沙色）
        g.fillColor = new Color(222, 184, 100, 255);
        g.rect(-halfW, -halfH, w, h);
        g.fill();

        // 草带
        g.fillColor = new Color(112, 196, 84, 255);
        g.rect(-halfW, halfH - 14, w, 14);
        g.fill();
        g.fillColor = new Color(80, 160, 60, 255);
        g.rect(-halfW, halfH - 4, w, 4);
        g.fill();

        // 滚动条纹
        const stripeW = 40;
        const stripeCount = Math.ceil(w / stripeW) + 2;
        g.fillColor = new Color(195, 150, 70, 255);
        const startX = -halfW - stripeW + (this.offset % stripeW);
        for (let i = 0; i < stripeCount; i++) {
            const x = startX + i * stripeW;
            if (i % 2 === 0) {
                g.rect(x, -halfH + 6, stripeW - 4, h - 20);
                g.fill();
            }
        }

        // 下边线
        g.strokeColor = new Color(60, 30, 0, 255);
        g.lineWidth = 2;
        g.rect(-halfW, -halfH, w, h);
        g.stroke();
    }

    update(dt: number) {
        if (GameHub.state === GameState.Dead) return;
        this.offset += this.speed * dt;
        if (this.offset > 1000) this.offset -= 1000;
        this.redraw();
    }
}

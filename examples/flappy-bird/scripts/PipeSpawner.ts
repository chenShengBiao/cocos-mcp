import { _decorator, Component, Node } from 'cc';
import { GameHub, GameState } from './GameHub';
import { Pipe } from './Pipe';
const { ccclass, property } = _decorator;

@ccclass('PipeSpawner')
export class PipeSpawner extends Component {
    @property
    spawnInterval: number = 1.6;

    @property
    pipeSpeed: number = 160;

    @property
    gap: number = 180;

    @property
    pipeWidth: number = 80;

    @property
    spawnX: number = 560;

    @property
    despawnX: number = -560;

    @property
    minGapY: number = -120;

    @property
    maxGapY: number = 120;

    private timer: number = 0;
    private pipes: Pipe[] = [];

    public reset() {
        this.timer = 0;
        for (const p of this.pipes) {
            if (p && p.node && p.node.isValid) p.node.destroy();
        }
        this.pipes.length = 0;
    }

    update(dt: number) {
        if (GameHub.state !== GameState.Playing) return;

        const diff = GameHub.getDifficulty();
        const curInterval = this.spawnInterval * diff.intervalMul;

        this.timer += dt;
        if (this.timer >= curInterval) {
            this.timer = 0;
            this.spawnPipe();
        }

        // 动态调整已存在水管的速度（让老水管也跟着变快）
        const curSpeed = this.pipeSpeed * diff.speedMul;
        for (let i = this.pipes.length - 1; i >= 0; i--) {
            const p = this.pipes[i];
            if (!p || !p.node || !p.node.isValid) {
                this.pipes.splice(i, 1);
                continue;
            }
            p.speed = curSpeed;
            if (p.node.position.x < this.despawnX) {
                p.node.destroy();
                this.pipes.splice(i, 1);
            }
        }
    }

    private spawnPipe() {
        const diff = GameHub.getDifficulty();
        const node = new Node('Pipe');
        node.layer = this.node.layer;
        this.node.addChild(node);
        const pipe = node.addComponent(Pipe);
        const gapY = this.minGapY + Math.random() * (this.maxGapY - this.minGapY);
        const curGap = Math.max(110, this.gap - diff.gapShrink);
        pipe.init(this.spawnX, gapY, this.pipeSpeed * diff.speedMul, curGap, this.pipeWidth);
        this.pipes.push(pipe);
    }
}

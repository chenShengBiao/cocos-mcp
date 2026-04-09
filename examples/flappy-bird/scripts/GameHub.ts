/**
 * 跨脚本共享的运行时状态 + 游戏广播。
 * 不继承 Component，不走装饰器，避免任何循环依赖。
 * Bird/Pipe/PipeSpawner/Ground 都只依赖 GameHub，
 * GameManager 负责读写 GameHub 并联动 UI。
 */
import { sys } from 'cc';

export enum GameState {
    Ready = 0,
    Playing = 1,
    Dead = 2,
}

export interface IBirdLike {
    node: any;
    isAlive(): boolean;
    getRadius(): number;
    kill(): void;
    reset(): void;
    flap(): void;
}

const BEST_KEY = 'flappy_bird_best_v1';

function loadBest(): number {
    try {
        const s = sys.localStorage?.getItem?.(BEST_KEY);
        return s ? parseInt(s, 10) || 0 : 0;
    } catch {
        return 0;
    }
}

function saveBest(v: number) {
    try {
        sys.localStorage?.setItem?.(BEST_KEY, String(v));
    } catch {
        /* ignore */
    }
}

export const GameHub = {
    state: GameState.Ready as GameState,
    score: 0,
    best: loadBest(),
    bird: null as IBirdLike | null,

    // 事件钩子：GameManager 订阅以更新 UI
    onScoreChanged: null as ((s: number) => void) | null,
    onStateChanged: null as ((s: GameState) => void) | null,

    setState(s: GameState) {
        if (this.state === s) return;
        this.state = s;
        this.onStateChanged?.(s);
    },

    addScore() {
        this.score++;
        this.onScoreChanged?.(this.score);
    },

    resetScore() {
        this.score = 0;
        this.onScoreChanged?.(0);
    },

    gameOver() {
        if (this.state !== GameState.Playing) return;
        if (this.score > this.best) {
            this.best = this.score;
            saveBest(this.best);
        }
        this.setState(GameState.Dead);
    },

    /** 当前分数对应的难度倍率，speed *= m.speedMul, gap = baseGap - m.gapShrink */
    getDifficulty() {
        const lvl = Math.floor(this.score / 5);  // 每 5 分升一级
        const capped = Math.min(lvl, 6);
        return {
            speedMul: 1 + capped * 0.08,
            gapShrink: capped * 10,
            intervalMul: Math.max(0.65, 1 - capped * 0.06),
        };
    },
};

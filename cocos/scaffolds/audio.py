"""Scaffold for a BGM + SFX audio controller singleton.

Audio is another "every game does this" chore that goes wrong in
predictable ways: BGM gets restarted on scene re-enter, playSFX
interrupts the previous SFX (so rapid-fire gun shots sound like one),
volume never persists across sessions, and the whole thing crashes in
WeChat private storage the first time anyone calls setItem. The generated
AudioController fixes all four: idempotent playBGM, playOneShot-based
SFX overlap, localStorage with swallowed write failures, and a tween-based
cross-fade between BGM tracks.
"""
from __future__ import annotations

from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_TEMPLATE = """\
import { _decorator, Component, AudioSource, AudioClip, tween } from 'cc';
const { ccclass, property } = _decorator;

const STORAGE_KEY = 'cocos-mcp-audio';

/**
 * AudioController — singleton BGM + SFX manager.
 *
 *   AudioController.I.playBGM(name)     // cross-fade if another BGM is playing
 *   AudioController.I.stopBGM()
 *   AudioController.I.playSFX(name)     // overlapping one-shots, no interrupt
 *   AudioController.I.setBGMVolume(v)   // 0..1, persisted to localStorage
 *   AudioController.I.setSFXVolume(v)   // 0..1, persisted
 *   AudioController.I.bgmVolume / sfxVolume   // read current
 *
 * Clip lookup is by `clip.name` — drag your AudioClips into bgmClips /
 * sfxClips in the Inspector, then call playBGM('theme') from code.
 */
@ccclass('AudioController')
export class AudioController extends Component {
    private static _instance: AudioController | null = null;
    static get I(): AudioController { return AudioController._instance!; }

    @property({ type: [AudioClip], tooltip: 'Each clip.name is the key for playBGM(name).' })
    bgmClips: AudioClip[] = [];

    @property({ type: [AudioClip], tooltip: 'Each clip.name is the key for playSFX(name).' })
    sfxClips: AudioClip[] = [];

    @property({ tooltip: 'Seconds to cross-fade between BGM tracks. 0 = hard cut.' })
    bgmFadeDuration: number = 0.5;

    public bgmVolume: number = 1.0;
    public sfxVolume: number = 1.0;

    private _bgmSource: AudioSource | null = null;
    private _sfxSource: AudioSource | null = null;
    private _currentBGMName: string = '';

    onLoad() {
        if (AudioController._instance && AudioController._instance !== this) {
            this.destroy();
            return;
        }
        AudioController._instance = this;

        // Read persisted volumes. Private-browsing / WeChat may refuse
        // access; default to 1.0 on any failure.
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (typeof parsed.bgm === 'number') this.bgmVolume = Math.max(0, Math.min(1, parsed.bgm));
                if (typeof parsed.sfx === 'number') this.sfxVolume = Math.max(0, Math.min(1, parsed.sfx));
            }
        } catch (_e) {
            // Swallow — gameplay doesn't depend on saved volume.
        }

        // Auto-attach two AudioSources on this node. We don't require the
        // user to add them manually — one less "why is audio silent?" issue.
        this._bgmSource = this.getComponent(AudioSource);
        if (!this._bgmSource) this._bgmSource = this.addComponent(AudioSource);
        this._bgmSource.loop = true;
        this._bgmSource.volume = this.bgmVolume;

        // The second AudioSource is for one-shot SFX. getComponents returns
        // all of them; we grab the second or add one.
        const sources = this.getComponents(AudioSource);
        if (sources.length >= 2) {
            this._sfxSource = sources[1];
        } else {
            this._sfxSource = this.addComponent(AudioSource);
        }
        this._sfxSource.loop = false;
        this._sfxSource.volume = this.sfxVolume;
    }

    onDestroy() {
        if (AudioController._instance === this) AudioController._instance = null;
    }

    /**
     * Play (or cross-fade to) a BGM track by clip.name. Calling with the
     * already-playing clip name is a no-op — no restart, no re-fade.
     */
    playBGM(name: string) {
        if (!this._bgmSource) return;
        if (name === this._currentBGMName && this._bgmSource.playing) return;

        const clip = this.bgmClips.find(c => c && c.name === name);
        if (!clip) return;  // clip missing — don't crash, just skip

        const src = this._bgmSource;
        const targetVol = this.bgmVolume;

        if (this.bgmFadeDuration > 0 && src.playing) {
            // Fade the current track down, then swap + play the new one
            // at target volume. Tween operates on AudioSource directly.
            tween(src)
                .to(this.bgmFadeDuration, { volume: 0 })
                .call(() => {
                    src.stop();
                    src.clip = clip;
                    src.volume = 0;
                    src.play();
                    tween(src).to(this.bgmFadeDuration, { volume: targetVol }).start();
                })
                .start();
        } else {
            src.stop();
            src.clip = clip;
            src.volume = targetVol;
            src.play();
        }

        this._currentBGMName = name;
    }

    stopBGM() {
        if (this._bgmSource) {
            this._bgmSource.stop();
        }
        this._currentBGMName = '';
    }

    /**
     * Play an overlapping one-shot SFX. Multiple SFX can play concurrently
     * without interrupting each other (playOneShot spawns an internal
     * playback instead of replacing the source's current clip).
     */
    playSFX(name: string) {
        if (!this._sfxSource) return;
        const clip = this.sfxClips.find(c => c && c.name === name);
        if (!clip) return;  // silently skip — common when a clip is renamed
        this._sfxSource.playOneShot(clip, this.sfxVolume);
    }

    setBGMVolume(v: number) {
        this.bgmVolume = Math.max(0, Math.min(1, v));
        if (this._bgmSource) this._bgmSource.volume = this.bgmVolume;
        this._persist();
    }

    setSFXVolume(v: number) {
        this.sfxVolume = Math.max(0, Math.min(1, v));
        if (this._sfxSource) this._sfxSource.volume = this.sfxVolume;
        this._persist();
    }

    private _persist() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                bgm: this.bgmVolume,
                sfx: this.sfxVolume,
            }));
        } catch (_e) {
            // Private-browsing / WeChat storage refused — ignore.
        }
    }
}
"""


def scaffold_audio_controller(project_path: str | Path,
                              rel_path: str = "AudioController.ts") -> dict:
    """Generate AudioController.ts — a singleton BGM + SFX manager.

    Runtime API::

        AudioController.I.playBGM(name)       # cross-fade if one already plays
        AudioController.I.stopBGM()
        AudioController.I.playSFX(name)       # overlapping one-shot
        AudioController.I.setBGMVolume(v)     # 0..1, persisted
        AudioController.I.setSFXVolume(v)     # 0..1, persisted

    Inspector:
        bgmClips         (AudioClip[])  lookup by clip.name
        sfxClips         (AudioClip[])  lookup by clip.name
        bgmFadeDuration  (number)       seconds, 0 = hard cut

    The component auto-adds two AudioSource components on its own node —
    one looping for BGM, one for SFX playOneShots — so the designer
    doesn't have to manually wire them. Volumes persist to localStorage
    under ``cocos-mcp-audio``; write failures are swallowed (private
    browsing / WeChat mini-program storage quirks).

    Same return shape as the other scaffolds:
    ``{path, rel_path, uuid_standard, uuid_compressed}``.
    """
    result = add_script(project_path, rel_path, _TEMPLATE)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

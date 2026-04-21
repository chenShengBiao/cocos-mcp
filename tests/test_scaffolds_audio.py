"""Tests for ``scaffold_audio_controller``.

Imports directly from ``cocos.scaffolds.audio`` rather than via
``cocos.scaffolds`` so the test file is self-contained and does not
require the module's ``__init__.py`` re-export to be merged first.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scaffolds.audio import scaffold_audio_controller
from cocos.scene_builder import add_node, add_script as scene_add_script, create_empty_scene
from cocos.uuid_util import compress_uuid


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "p"
    (p / "assets").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


def _tmp_scene() -> tuple[str, dict]:
    f = tempfile.NamedTemporaryFile(suffix=".scene", delete=False)
    f.close()
    info = create_empty_scene(f.name)
    return f.name, info


def test_audio_controller_writes_ts_and_meta(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))

    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith("AudioController.ts")
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]


def test_audio_controller_returns_all_four_keys(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


def test_audio_controller_uuid_forms_consistent(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    assert len(res["uuid_standard"]) == 36
    assert res["uuid_standard"].count("-") == 4
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


def test_audio_controller_custom_rel_path(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj), rel_path="assets/audio/Ac.ts")
    assert res["rel_path"] == "assets/audio/Ac.ts"
    assert (proj / res["rel_path"]).exists()


def test_audio_controller_has_class_decorator(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()
    assert "@ccclass('AudioController')" in source


def test_audio_controller_singleton_accessor(tmp_path: Path):
    """Same singleton shape as GameScore / InputManager: `static get I`."""
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()
    assert "static get I" in source
    # Dedup guard in onLoad — same pattern as other singletons.
    assert "if (AudioController._instance" in source


def test_audio_controller_inspector_props(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()
    assert "bgmClips" in source
    assert "sfxClips" in source


def test_audio_controller_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # The five public methods that downstream code will call.
    assert "playBGM" in source
    assert "stopBGM" in source
    assert "playSFX" in source
    assert "setBGMVolume" in source
    assert "setSFXVolume" in source


def test_audio_controller_uses_AudioSource(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # Imports + uses cc.AudioSource under the hood.
    assert "AudioSource" in source


def test_audio_controller_auto_attaches_sources(tmp_path: Path):
    """Don't require the user to manually add AudioSources to the node —
    the component must addComponent(AudioSource) itself in onLoad."""
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()
    assert "addComponent(AudioSource)" in source


def test_audio_controller_sfx_uses_playOneShot(tmp_path: Path):
    """SFX overlap: multiple concurrent fires mustn't interrupt each
    other — that means playOneShot, not `source.clip = x; source.play()`."""
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()
    assert "playOneShot" in source


def test_audio_controller_persists_to_localstorage(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # Both reads (onLoad) and writes (setBGMVolume/setSFXVolume) must exist.
    assert "localStorage" in source
    assert "cocos-mcp-audio" in source
    # Write failure swallowed (private-browsing / WeChat) — same pattern
    # as GameScore.
    assert "try" in source and "catch" in source


def test_audio_controller_idempotent_recall_preserves_uuid(tmp_path: Path):
    """Bug A fix: re-scaffolding preserves the UUID so the caller can
    regenerate the file (e.g. after tweaking a constant in the source
    template) without breaking any already-attached scene components."""
    proj = _make_project(tmp_path)
    first = scaffold_audio_controller(str(proj))
    second = scaffold_audio_controller(str(proj))
    assert first["uuid_standard"] == second["uuid_standard"]
    assert first["uuid_compressed"] == second["uuid_compressed"]


def test_audio_controller_attaches_to_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_audio_controller(str(proj))

    scene_path, info = _tmp_scene()
    audio_node = add_node(scene_path, info["canvas_node_id"], "Audio")
    cid = scene_add_script(scene_path, audio_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

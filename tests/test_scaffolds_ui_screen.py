"""Tests for the full-screen UI controller scaffolds.

Each ``kind`` (menu / settings / pause / game_over) emits its own
<Kind>Screen.ts. The suite verifies the file + meta land on disk, the
dict shape, UUID consistency, per-kind @ccclass name, the four
kind-specific API strings embedded in the TS, invalid-kind ValueError,
custom rel_path handling, default-rel-path uniqueness per kind, and a
scene-attach integration check so a caller can wire the emitted UUID
directly into a scene node.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scaffolds.ui_screen import scaffold_ui_screen
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


# ---- expected facts per kind ---------------------------------------------
_KINDS = ["menu", "settings", "pause", "game_over"]
_DEFAULT_FILENAME = {
    "menu": "MenuScreen.ts",
    "settings": "SettingsScreen.ts",
    "pause": "PauseScreen.ts",
    "game_over": "GameOverScreen.ts",
}
_CCCLASS = {
    "menu": "@ccclass('MenuScreen')",
    "settings": "@ccclass('SettingsScreen')",
    "pause": "@ccclass('PauseScreen')",
    "game_over": "@ccclass('GameOverScreen')",
}


# ============================================================
#  per-kind: file + meta + UUID + return-dict shape
# ============================================================

@pytest.mark.parametrize("kind", _KINDS)
def test_ui_screen_writes_ts_and_meta(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind=kind)

    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith(_DEFAULT_FILENAME[kind])
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]


@pytest.mark.parametrize("kind", _KINDS)
def test_ui_screen_returns_all_four_keys(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind=kind)
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


@pytest.mark.parametrize("kind", _KINDS)
def test_ui_screen_uuid_forms_consistent(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind=kind)
    assert len(res["uuid_standard"]) == 36
    assert res["uuid_standard"].count("-") == 4
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


# ============================================================
#  per-kind: class name
# ============================================================

@pytest.mark.parametrize("kind", _KINDS)
def test_ui_screen_ts_has_expected_class_name(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind=kind)
    source = (proj / res["rel_path"]).read_text()
    assert _CCCLASS[kind] in source


# ============================================================
#  every kind imports GameLoop
# ============================================================

@pytest.mark.parametrize("kind", _KINDS)
def test_ui_screen_imports_game_loop(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind=kind)
    source = (proj / res["rel_path"]).read_text()
    assert "import { GameLoop } from './GameLoop'" in source


# ============================================================
#  per-kind: specific content checks
# ============================================================

def test_menu_references_start_button_and_go_play(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind="menu")
    source = (proj / res["rel_path"]).read_text()
    assert "startButton" in source
    assert "GameLoop.I.go('play')" in source or "loop.go('play')" in source


def test_settings_references_close_button_and_toggle(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind="settings")
    source = (proj / res["rel_path"]).read_text()
    assert "closeButton" in source
    assert ".toggle(" in source


def test_pause_references_key_down_and_escape(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind="pause")
    source = (proj / res["rel_path"]).read_text()
    assert "KEY_DOWN" in source
    assert "ESCAPE" in source
    # Pause toggles loop state.
    assert "GameLoop" in source
    assert ".go(" in source


def test_game_over_references_score_restart_and_reset(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind="game_over")
    source = (proj / res["rel_path"]).read_text()
    assert "scoreLabel" in source
    assert "restartButton" in source
    # Restart wipes the score counter via the GameScore singleton.
    assert "GameScore" in source
    assert ".reset()" in source


def test_game_over_imports_game_score(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind="game_over")
    source = (proj / res["rel_path"]).read_text()
    assert "import { GameScore } from './GameScore'" in source


# ============================================================
#  validation + defaults
# ============================================================

def test_unknown_kind_raises_listing_valid_options(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError) as ei:
        scaffold_ui_screen(str(proj), kind="victory")
    msg = str(ei.value)
    # Error message should mention the four valid options so the caller
    # can immediately see which form was mistyped.
    for k in _KINDS:
        assert k in msg


@pytest.mark.parametrize("kind", _KINDS)
def test_ui_screen_custom_rel_path_honored(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(
        str(proj), kind=kind, rel_path="assets/ui/Screen.ts"
    )
    assert res["rel_path"] == "assets/ui/Screen.ts"
    assert (proj / res["rel_path"]).exists()


def test_ui_screen_default_rel_path_differs_per_kind(tmp_path: Path):
    proj = _make_project(tmp_path)
    seen: set[str] = set()
    for kind in _KINDS:
        res = scaffold_ui_screen(str(proj), kind=kind)
        base = Path(res["rel_path"]).name
        assert base == _DEFAULT_FILENAME[kind]
        seen.add(base)
    # All four defaults must be distinct.
    assert len(seen) == 4


# ============================================================
#  integration: scaffold + attach to scene
# ============================================================

@pytest.mark.parametrize("kind", _KINDS)
def test_ui_screen_attaches_to_scene(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_ui_screen(str(proj), kind=kind)

    scene_path, info = _tmp_scene()
    screen_node = add_node(scene_path, info["canvas_node_id"], "Screen")
    cid = scene_add_script(scene_path, screen_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

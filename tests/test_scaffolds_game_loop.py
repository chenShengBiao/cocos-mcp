"""Tests for the GameLoop state-machine scaffold.

Covers default-states rendering, custom state names (including snake_case
being PascalCased into the callback field name), the state-name
validator (empty list, duplicates, invalid-identifier cases), the
generated runtime-API surface (``static get I()``, ``go``, ``reset``,
``_dispatchEnter``, ``_dispatchExit``), and a scene-attach integration
smoke test.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scaffolds.game_loop import scaffold_game_loop
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


# ============================================================
#  file + meta + return shape
# ============================================================

def test_game_loop_writes_ts_and_meta(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj))

    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith("GameLoop.ts")
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]


def test_game_loop_returns_all_four_keys(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj))
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


def test_game_loop_uuid_forms_consistent(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj))
    assert len(res["uuid_standard"]) == 36
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


# ============================================================
#  default states
# ============================================================

def test_default_states_render_menu_play_over(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj))
    source = (proj / res["rel_path"]).read_text()

    assert "@ccclass('GameLoop')" in source
    # Pair of callback fields for every default state.
    assert "onEnterMenu" in source
    assert "onExitMenu" in source
    assert "onEnterPlay" in source
    assert "onExitPlay" in source
    assert "onEnterOver" in source
    assert "onExitOver" in source
    # The internal state list is concretely baked into the generated TS.
    assert '_states: string[] = ["menu", "play", "over"]' in source


# ============================================================
#  custom states
# ============================================================

def test_custom_states_render_expected_callbacks(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj), states=["idle", "attack", "dead"])
    source = (proj / res["rel_path"]).read_text()

    assert "onEnterIdle" in source
    assert "onExitIdle" in source
    assert "onEnterAttack" in source
    assert "onExitAttack" in source
    assert "onEnterDead" in source
    assert "onExitDead" in source
    assert '_states: string[] = ["idle", "attack", "dead"]' in source
    # Default states should NOT leak into a custom-state file.
    assert "onEnterMenu" not in source
    assert "onEnterPlay" not in source


def test_snake_case_state_becomes_pascal_case_callback(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj), states=["menu", "game_over"])
    source = (proj / res["rel_path"]).read_text()

    # "game_over" → onEnterGameOver / onExitGameOver
    assert "onEnterGameOver" in source
    assert "onExitGameOver" in source
    # But the raw string must still flow through to the state list + switch.
    assert '"game_over"' in source
    # Double-underscore / weird capitalization should not appear.
    assert "onEnterGame_Over" not in source
    assert "onEnterGame_over" not in source


# ============================================================
#  runtime API surface
# ============================================================

def test_runtime_api_surface_always_present(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # Singleton accessor — lenient whitespace so a reformat doesn't break us.
    assert "static get I()" in source
    assert "go(state: string)" in source
    assert "reset()" in source
    assert "_dispatchEnter" in source
    assert "_dispatchExit" in source


def test_runtime_api_present_for_custom_states(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj), states=["a", "b"])
    source = (proj / res["rel_path"]).read_text()
    assert "static get I()" in source
    assert "go(state: string)" in source
    assert "reset()" in source
    assert "_dispatchEnter" in source
    assert "_dispatchExit" in source


# ============================================================
#  validation
# ============================================================

def test_empty_states_list_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError):
        scaffold_game_loop(str(proj), states=[])


def test_duplicate_state_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError) as ei:
        scaffold_game_loop(str(proj), states=["menu", "play", "menu"])
    assert "menu" in str(ei.value)


def test_invalid_identifier_spaces_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError):
        scaffold_game_loop(str(proj), states=["game over"])


def test_invalid_identifier_leading_digit_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError):
        scaffold_game_loop(str(proj), states=["1menu"])


def test_invalid_identifier_special_chars_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError):
        scaffold_game_loop(str(proj), states=["menu!"])


def test_empty_string_state_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError):
        scaffold_game_loop(str(proj), states=["menu", ""])


# ============================================================
#  custom rel_path + integration
# ============================================================

def test_custom_rel_path_honored(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj), rel_path="assets/core/Loop.ts")
    assert res["rel_path"] == "assets/core/Loop.ts"
    assert (proj / res["rel_path"]).exists()


def test_game_loop_attaches_to_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_game_loop(str(proj))

    scene_path, info = _tmp_scene()
    gm_node = add_node(scene_path, info["canvas_node_id"], "GameLoop")
    cid = scene_add_script(scene_path, gm_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

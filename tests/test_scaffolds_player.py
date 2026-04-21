"""Tests for the game-type-specific player-controller scaffolds.

Each ``kind`` emits its own Player{Flavor}.ts. The suite verifies the
file + meta land on disk, the dict shape, UUID consistency, per-kind TS
content (class name, InputManager import, kind-specific @property
fields), the default-vs-custom rel_path behaviour, the invalid-kind
ValueError, and a scene-attach integration check so the caller can wire
the emitted UUID straight into a scene node.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scaffolds.player import scaffold_player_controller
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
_KINDS = ["platformer", "topdown", "flappy", "click_only"]
_DEFAULT_FILENAME = {
    "platformer": "PlayerPlatformer.ts",
    "topdown": "PlayerTopdown.ts",
    "flappy": "PlayerFlappy.ts",
    "click_only": "PlayerClick.ts",
}
_CCCLASS = {
    "platformer": "@ccclass('PlayerPlatformer')",
    "topdown": "@ccclass('PlayerTopdown')",
    "flappy": "@ccclass('PlayerFlappy')",
    "click_only": "@ccclass('PlayerClick')",
}


# ============================================================
#  per-kind: file + meta + UUID + return-dict shape
# ============================================================

@pytest.mark.parametrize("kind", _KINDS)
def test_player_writes_ts_and_meta(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind=kind)

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
def test_player_returns_all_four_keys(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind=kind)
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


@pytest.mark.parametrize("kind", _KINDS)
def test_player_uuid_forms_consistent(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind=kind)
    assert len(res["uuid_standard"]) == 36
    assert res["uuid_standard"].count("-") == 4
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


# ============================================================
#  per-kind: class name
# ============================================================

@pytest.mark.parametrize("kind", _KINDS)
def test_player_ts_has_expected_class_name(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind=kind)
    source = (proj / res["rel_path"]).read_text()
    assert _CCCLASS[kind] in source


# ============================================================
#  per-kind: specific content checks
# ============================================================

def test_platformer_imports_input_manager(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind="platformer")
    source = (proj / res["rel_path"]).read_text()
    assert "import { InputManager } from './InputManager'" in source


def test_platformer_references_jumpforce_movespeed_doublejump(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind="platformer")
    source = (proj / res["rel_path"]).read_text()
    assert "jumpForce" in source
    assert "moveSpeed" in source
    assert "doubleJumpEnabled" in source


def test_topdown_imports_input_manager(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind="topdown")
    source = (proj / res["rel_path"]).read_text()
    assert "import { InputManager } from './InputManager'" in source


def test_topdown_references_movespeed_and_linearvelocity_no_jumpforce(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind="topdown")
    source = (proj / res["rel_path"]).read_text()
    assert "moveSpeed" in source
    assert "linearVelocity" in source
    assert "jumpForce" not in source


def test_flappy_imports_input_manager(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind="flappy")
    source = (proj / res["rel_path"]).read_text()
    assert "import { InputManager } from './InputManager'" in source


def test_flappy_references_flapforce_and_no_horizontal(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind="flappy")
    source = (proj / res["rel_path"]).read_text()
    assert "flapForce" in source
    # horizontal-movement bookkeeping should be absent in a jump-only controller
    assert "moveDir.x" not in source
    assert "moveSpeed" not in source


def test_click_only_uses_tween(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind="click_only")
    source = (proj / res["rel_path"]).read_text()
    # Either the named import or the call site must be present — both
    # indicate the click controller is using cc.tween for the ease.
    assert "tween" in source
    assert "tween(this.node)" in source


# ============================================================
#  validation + defaults
# ============================================================

def test_unknown_kind_raises_listing_valid_options(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError) as ei:
        scaffold_player_controller(str(proj), kind="metroidvania")
    msg = str(ei.value)
    # Error message should list the four valid options so the caller
    # can immediately see which form was mistyped.
    for k in _KINDS:
        assert k in msg


@pytest.mark.parametrize("kind", _KINDS)
def test_player_custom_rel_path_honored(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(
        str(proj), kind=kind, rel_path="assets/gameplay/Hero.ts"
    )
    assert res["rel_path"] == "assets/gameplay/Hero.ts"
    assert (proj / res["rel_path"]).exists()


def test_player_default_rel_path_differs_per_kind(tmp_path: Path):
    proj = _make_project(tmp_path)
    seen: set[str] = set()
    for kind in _KINDS:
        res = scaffold_player_controller(str(proj), kind=kind)
        # Fresh project for each so we're only comparing default filenames.
        base = Path(res["rel_path"]).name
        assert base == _DEFAULT_FILENAME[kind]
        seen.add(base)
    # All four defaults must be distinct.
    assert len(seen) == 4


# ============================================================
#  integration: scaffold + attach to scene
# ============================================================

@pytest.mark.parametrize("kind", _KINDS)
def test_player_attaches_to_scene(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_player_controller(str(proj), kind=kind)

    scene_path, info = _tmp_scene()
    player_node = add_node(scene_path, info["canvas_node_id"], "Player")
    cid = scene_add_script(scene_path, player_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

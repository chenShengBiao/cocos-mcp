"""Tests for the gameplay-code scaffolds.

Each scaffold is a small .ts generator: it writes a canonical starter
script + its meta and returns both UUID forms. The tests verify the
file layout (lands under ``assets/scripts/``), the meta sidecar, the
dict shape, the UUID consistency (standard <-> compressed), that key
runtime-API strings actually made it into the generated code, and that
the generated script can be attached to a scene via the scene-mutation
``add_script``.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import scaffolds as sc
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
#  scaffold_input_abstraction
# ============================================================

def test_scaffold_input_writes_ts_and_meta(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_input_abstraction(str(proj))

    # File + sidecar landed under assets/ with the right filename
    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith("InputManager.ts")
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]


def test_scaffold_input_returns_all_four_keys(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_input_abstraction(str(proj))
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


def test_scaffold_input_uuid_forms_consistent(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_input_abstraction(str(proj))
    assert len(res["uuid_standard"]) == 36
    assert res["uuid_standard"].count("-") == 4
    assert len(res["uuid_compressed"]) == 23
    # Compressed must be the deterministic derivation of standard
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


def test_scaffold_input_embeds_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_input_abstraction(str(proj))
    source = (proj / res["rel_path"]).read_text()
    # Class name + key public-API strings that downstream scripts read
    assert "@ccclass('InputManager')" in source
    assert "moveDir" in source
    assert "jumpPressed" in source
    assert "firePressed" in source


def test_scaffold_input_custom_rel_path(tmp_path: Path):
    proj = _make_project(tmp_path)
    # Fully-qualified paths (starting with assets/) are honored verbatim by
    # add_script — bare names get the default assets/scripts/ prefix. We
    # pass the fully-qualified form to prove the custom rel_path is respected.
    res = sc.scaffold_input_abstraction(str(proj), rel_path="assets/core/Inputs.ts")
    assert res["rel_path"] == "assets/core/Inputs.ts"
    assert (proj / res["rel_path"]).exists()


def test_scaffold_input_idempotent_recall_gets_new_uuid(tmp_path: Path):
    """add_script mints a fresh UUID on every call; regenerating the scaffold
    to the same rel_path must therefore return a DIFFERENT uuid each time."""
    proj = _make_project(tmp_path)
    first = sc.scaffold_input_abstraction(str(proj))
    second = sc.scaffold_input_abstraction(str(proj))
    assert first["uuid_standard"] != second["uuid_standard"]
    assert first["uuid_compressed"] != second["uuid_compressed"]


def test_scaffold_input_attaches_to_scene(tmp_path: Path):
    """Integration: generate + attach; the resulting scene component's
    __type__ must be the 23-char compressed UUID."""
    proj = _make_project(tmp_path)
    res = sc.scaffold_input_abstraction(str(proj))

    scene_path, info = _tmp_scene()
    gm_node = add_node(scene_path, info["canvas_node_id"], "GameManager")
    cid = scene_add_script(scene_path, gm_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23


# ============================================================
#  scaffold_score_system
# ============================================================

def test_scaffold_score_writes_ts_and_meta(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_score_system(str(proj))

    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith("GameScore.ts")
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]


def test_scaffold_score_returns_all_four_keys(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_score_system(str(proj))
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


def test_scaffold_score_uuid_forms_consistent(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_score_system(str(proj))
    assert len(res["uuid_standard"]) == 36
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


def test_scaffold_score_embeds_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_score_system(str(proj))
    source = (proj / res["rel_path"]).read_text()
    assert "@ccclass('GameScore')" in source
    assert "add(" in source
    assert "reset()" in source
    assert "STORAGE_KEY" in source


def test_scaffold_score_custom_rel_path(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_score_system(str(proj), rel_path="assets/gameplay/Score.ts")
    assert res["rel_path"] == "assets/gameplay/Score.ts"
    assert (proj / res["rel_path"]).exists()


def test_scaffold_score_idempotent_recall_gets_new_uuid(tmp_path: Path):
    proj = _make_project(tmp_path)
    first = sc.scaffold_score_system(str(proj))
    second = sc.scaffold_score_system(str(proj))
    assert first["uuid_standard"] != second["uuid_standard"]
    assert first["uuid_compressed"] != second["uuid_compressed"]


def test_scaffold_score_attaches_to_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = sc.scaffold_score_system(str(proj))

    scene_path, info = _tmp_scene()
    ui_node = add_node(scene_path, info["canvas_node_id"], "ScoreUI")
    cid = scene_add_script(scene_path, ui_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

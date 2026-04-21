"""Tests for the spawner scaffolds (time / proximity).

Mirrors tests/test_scaffolds.py: file + meta land under
assets/scripts/, return dict shape, UUID round-trip, the expected
runtime-API strings are present, and the generated script can be
attached to a scene node.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scaffolds.spawner import scaffold_spawner
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
#  File + meta per kind
# ============================================================

@pytest.mark.parametrize("kind,filename,classname", [
    ("time", "SpawnerTime.ts", "SpawnerTime"),
    ("proximity", "SpawnerProximity.ts", "SpawnerProximity"),
])
def test_spawner_writes_ts_and_meta(tmp_path: Path, kind: str, filename: str, classname: str):
    proj = _make_project(tmp_path)
    res = scaffold_spawner(str(proj), kind=kind)

    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith(filename)
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]

    source = ts_path.read_text()
    assert f"@ccclass('{classname}')" in source


@pytest.mark.parametrize("kind", ["time", "proximity"])
def test_spawner_returns_all_four_keys(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_spawner(str(proj), kind=kind)
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


@pytest.mark.parametrize("kind", ["time", "proximity"])
def test_spawner_uuid_forms_consistent(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_spawner(str(proj), kind=kind)
    assert len(res["uuid_standard"]) == 36
    assert res["uuid_standard"].count("-") == 4
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


# ============================================================
#  Per-kind runtime API strings + structural invariants
# ============================================================

def test_spawner_time_embeds_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_spawner(str(proj), kind="time")
    source = (proj / res["rel_path"]).read_text()
    assert "interval" in source
    assert "maxActive" in source
    assert "spawnBoxSize" in source
    # Despawn-oldest logic: an active list + destroy() + shift-or-splice.
    assert "_active" in source
    assert ".destroy()" in source
    assert "shift()" in source


def test_spawner_proximity_embeds_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_spawner(str(proj), kind="proximity")
    source = (proj / res["rel_path"]).read_text()
    assert "player" in source
    assert "triggerRadius" in source
    assert "cooldown" in source
    assert "_cooldownLeft" in source


def test_spawner_both_parent_under_spawner_parent_not_self(tmp_path: Path):
    """Spawns must attach to ``this.node.parent.addChild`` — parenting
    under the spawner itself would stack the spawner's transform onto
    each spawn, which is nearly always a bug for star/meteor spawners."""
    proj = _make_project(tmp_path)
    for kind in ("time", "proximity"):
        res = scaffold_spawner(str(proj), kind=kind)
        source = (proj / res["rel_path"]).read_text()
        assert "instantiate" in source
        assert "this.node.parent.addChild" in source
        # And conspicuously NOT the spawner itself as parent.
        assert "this.node.addChild" not in source


def test_spawner_both_emit_onspawn_callback(tmp_path: Path):
    proj = _make_project(tmp_path)
    for kind in ("time", "proximity"):
        res = scaffold_spawner(str(proj), kind=kind)
        source = (proj / res["rel_path"]).read_text()
        # onSpawn is declared and invoked with the spawned Node.
        assert "onSpawn" in source
        assert "this.onSpawn(spawned)" in source


# ============================================================
#  Validation
# ============================================================

def test_spawner_unknown_kind_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError) as exc:
        scaffold_spawner(str(proj), kind="random")
    msg = str(exc.value)
    assert "time" in msg
    assert "proximity" in msg


# ============================================================
#  rel_path default + custom
# ============================================================

def test_spawner_default_rel_paths_per_kind(tmp_path: Path):
    proj = _make_project(tmp_path)
    t = scaffold_spawner(str(proj), kind="time")
    p = scaffold_spawner(str(proj), kind="proximity")
    assert t["rel_path"] == "assets/scripts/SpawnerTime.ts"
    assert p["rel_path"] == "assets/scripts/SpawnerProximity.ts"


def test_spawner_custom_rel_path_honored(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_spawner(str(proj), kind="time",
                           rel_path="assets/gameplay/MeteorSpawner.ts")
    assert res["rel_path"] == "assets/gameplay/MeteorSpawner.ts"
    assert (proj / res["rel_path"]).exists()


# ============================================================
#  Integration: attach to scene
# ============================================================

@pytest.mark.parametrize("kind", ["time", "proximity"])
def test_spawner_attaches_to_scene(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_spawner(str(proj), kind=kind)

    scene_path, info = _tmp_scene()
    spawner_node = add_node(scene_path, info["canvas_node_id"], f"Spawner_{kind}")
    cid = scene_add_script(scene_path, spawner_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

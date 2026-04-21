"""Tests for the enemy-AI scaffolds (patrol / chase / shoot).

Mirrors the shape of tests/test_scaffolds.py: file + meta land under
assets/scripts/, the return dict has the full 4-key shape, UUIDs round-
trip, runtime-API strings made it into the generated TS, and the
generated script can actually be attached to a scene.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scaffolds.enemy import scaffold_enemy_ai
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
    ("patrol", "EnemyPatrol.ts", "EnemyPatrol"),
    ("chase", "EnemyChase.ts", "EnemyChase"),
    ("shoot", "EnemyShoot.ts", "EnemyShoot"),
])
def test_enemy_writes_ts_and_meta(tmp_path: Path, kind: str, filename: str, classname: str):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind=kind)

    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith(filename)
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]

    # Class name matches kind.
    source = ts_path.read_text()
    assert f"@ccclass('{classname}')" in source


@pytest.mark.parametrize("kind", ["patrol", "chase", "shoot"])
def test_enemy_returns_all_four_keys(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind=kind)
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


@pytest.mark.parametrize("kind", ["patrol", "chase", "shoot"])
def test_enemy_uuid_forms_consistent(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind=kind)
    assert len(res["uuid_standard"]) == 36
    assert res["uuid_standard"].count("-") == 4
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


# ============================================================
#  Per-kind runtime API strings present in TS
# ============================================================

def test_enemy_patrol_embeds_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind="patrol")
    source = (proj / res["rel_path"]).read_text()
    assert "patrolA" in source
    assert "patrolB" in source
    assert "speed" in source
    assert "mirrorSprite" in source
    # Short-form decorators per the prompt, not @property({ type: Node })
    assert "@property(Node)" in source
    assert "@property(Sprite)" in source


def test_enemy_chase_embeds_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind="chase")
    source = (proj / res["rel_path"]).read_text()
    assert "chaseRadius" in source
    assert "loseAggroRadius" in source
    assert "Vec3.distance" in source
    assert "setPosition" in source  # kinematic update, not physics velocity
    assert "@property(Node)" in source


def test_enemy_shoot_embeds_runtime_api(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind="shoot")
    source = (proj / res["rel_path"]).read_text()
    assert "fireInterval" in source
    assert "bulletPrefab" in source
    assert "instantiate" in source
    assert "this.node.parent.addChild" in source
    assert "cooldownTimer" in source
    assert "@property(Prefab)" in source


# ============================================================
#  Validation
# ============================================================

def test_enemy_unknown_kind_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError) as exc:
        scaffold_enemy_ai(str(proj), kind="sniper")
    msg = str(exc.value)
    # Message should mention all 3 valid options.
    assert "patrol" in msg
    assert "chase" in msg
    assert "shoot" in msg


# ============================================================
#  rel_path default + custom
# ============================================================

def test_enemy_default_rel_paths_differ_per_kind(tmp_path: Path):
    proj = _make_project(tmp_path)
    p = scaffold_enemy_ai(str(proj), kind="patrol")
    c = scaffold_enemy_ai(str(proj), kind="chase")
    s = scaffold_enemy_ai(str(proj), kind="shoot")
    assert p["rel_path"].endswith("EnemyPatrol.ts")
    assert c["rel_path"].endswith("EnemyChase.ts")
    assert s["rel_path"].endswith("EnemyShoot.ts")
    # Defaults are bare filenames — add_script routes to assets/scripts/
    assert p["rel_path"] == "assets/scripts/EnemyPatrol.ts"
    assert c["rel_path"] == "assets/scripts/EnemyChase.ts"
    assert s["rel_path"] == "assets/scripts/EnemyShoot.ts"


def test_enemy_custom_rel_path_honored(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind="chase",
                            rel_path="assets/gameplay/ai/Hunter.ts")
    assert res["rel_path"] == "assets/gameplay/ai/Hunter.ts"
    assert (proj / res["rel_path"]).exists()


# ============================================================
#  Integration: attach to scene
# ============================================================

@pytest.mark.parametrize("kind", ["patrol", "chase", "shoot"])
def test_enemy_attaches_to_scene(tmp_path: Path, kind: str):
    proj = _make_project(tmp_path)
    res = scaffold_enemy_ai(str(proj), kind=kind)

    scene_path, info = _tmp_scene()
    enemy_node = add_node(scene_path, info["canvas_node_id"], f"Enemy_{kind}")
    cid = scene_add_script(scene_path, enemy_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

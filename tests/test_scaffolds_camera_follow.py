"""Tests for ``scaffold_camera_follow``.

Imports directly from ``cocos.scaffolds.camera_follow`` rather than via
``cocos.scaffolds`` so the test file is self-contained and does not
require the module's ``__init__.py`` re-export to be merged first.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scaffolds.camera_follow import scaffold_camera_follow
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


def test_camera_follow_writes_ts_and_meta(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))

    assert res["rel_path"].startswith("assets/")
    assert res["rel_path"].endswith("CameraFollow.ts")
    ts_path = proj / res["rel_path"]
    assert ts_path.exists()
    meta_path = Path(f"{ts_path}.meta")
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid_standard"]


def test_camera_follow_returns_all_four_keys(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    assert set(res.keys()) == {"path", "rel_path", "uuid_standard", "uuid_compressed"}


def test_camera_follow_uuid_forms_consistent(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    assert len(res["uuid_standard"]) == 36
    assert res["uuid_standard"].count("-") == 4
    assert len(res["uuid_compressed"]) == 23
    assert res["uuid_compressed"] == compress_uuid(res["uuid_standard"])


def test_camera_follow_custom_rel_path(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj), rel_path="assets/cam/Cam.ts")
    assert res["rel_path"] == "assets/cam/Cam.ts"
    assert (proj / res["rel_path"]).exists()


def test_camera_follow_embeds_class_and_properties(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # @ccclass decorator + class props that the Inspector will render.
    assert "@ccclass('CameraFollow')" in source
    assert "target" in source
    assert "smoothing" in source
    assert "deadzoneWidth" in source
    assert "useWorldBounds" in source
    assert "worldBoundsMinX" in source
    assert "fixedZ" in source


def test_camera_follow_uses_lateUpdate_and_Vec3(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # Camera must run AFTER gameplay updates so it sees final target pos.
    assert "lateUpdate" in source
    # Full 3D Vec3 (not cc.Vec2) — supports 3D games too.
    assert "Vec3" in source


def test_camera_follow_frame_rate_independent_lerp(tmp_path: Path):
    """Smoothing must use exponential damping, not raw lerp — that means
    a ``Math.pow(smoothing, dt)`` term in the source. Raw ``lerp(a, b, smoothing)``
    would be framerate-dependent."""
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    source = (proj / res["rel_path"]).read_text()

    assert "Math.pow" in source
    assert "smoothing" in source
    # Spot-check the formula shape: `Math.pow(this.smoothing, dt)` must appear
    # together on one line.
    assert "Math.pow(this.smoothing, dt)" in source


def test_camera_follow_has_deadzone_check(tmp_path: Path):
    """Deadzone must gate position updates — verify the generated code
    actually tests against deadzoneHalf/Width inside a conditional."""
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # Either explicit `deadzoneWidth` usage or a derived `dzHalfX` must
    # appear in a conditional (Math.abs > threshold).
    assert "Math.abs" in source
    assert ("dzHalfX" in source) or ("deadzoneWidth" in source)
    assert ("dzHalfY" in source) or ("deadzoneHeight" in source)


def test_camera_follow_null_checks_target(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # target can be destroyed mid-scene; the script must not crash.
    assert "if (!this.target)" in source


def test_camera_follow_bounds_clamp(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))
    source = (proj / res["rel_path"]).read_text()

    # Per-axis Math.max/min clamp against the world bounds.
    assert "useWorldBounds" in source
    assert "Math.max" in source and "Math.min" in source


def test_camera_follow_idempotent_recall_gets_new_uuid(tmp_path: Path):
    proj = _make_project(tmp_path)
    first = scaffold_camera_follow(str(proj))
    second = scaffold_camera_follow(str(proj))
    assert first["uuid_standard"] != second["uuid_standard"]
    assert first["uuid_compressed"] != second["uuid_compressed"]


def test_camera_follow_attaches_to_scene(tmp_path: Path):
    """Integration: generate + attach the script to a scene node; the
    resulting scene component's ``__type__`` must be the 23-char
    compressed UUID."""
    proj = _make_project(tmp_path)
    res = scaffold_camera_follow(str(proj))

    scene_path, info = _tmp_scene()
    cam_node = add_node(scene_path, info["canvas_node_id"], "FollowCam")
    cid = scene_add_script(scene_path, cam_node, res["uuid_compressed"])

    with open(scene_path) as f:
        data = json.load(f)
    assert data[cid]["__type__"] == res["uuid_compressed"]
    assert len(data[cid]["__type__"]) == 23

"""Tests for cocos.project — the IO-only paths that don't need Cocos Creator installed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp

# ----------- helpers -----------

def _make_project_skeleton(root: Path, name: str = "demo") -> Path:
    """Create the minimal package.json + assets/ layout that project.py expects."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(json.dumps({
        "name": name, "uuid": "00000000-0000-0000-0000-000000000000",
        "creator": {"version": "3.8.6"},
    }))
    (root / "assets").mkdir(exist_ok=True)
    return root


def _make_png(path: Path, w: int = 4, h: int = 4) -> None:
    Image.new("RGBA", (w, h), (0, 255, 0, 255)).save(path)


# ----------- add_script -----------

def test_add_script_writes_ts_and_meta(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    res = cp.add_script(str(proj), "Foo", "export class Foo {}")

    assert res["rel_path"] == "assets/scripts/Foo.ts"
    assert Path(res["path"]).read_text() == "export class Foo {}"

    meta = json.loads(Path(res["path"] + ".meta").read_text())
    assert meta["importer"] == "typescript"
    assert meta["uuid"] == res["uuid"]
    assert len(res["uuid"]) == 36


def test_add_script_respects_explicit_path(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    res = cp.add_script(str(proj), "assets/sub/dir/Bar.ts", "// b")
    assert res["rel_path"] == "assets/sub/dir/Bar.ts"
    assert (proj / "assets/sub/dir/Bar.ts").exists()


def test_add_script_appends_ts_extension(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    res = cp.add_script(str(proj), "Baz", "// b")
    assert res["rel_path"].endswith(".ts")


# ----------- add_image -----------

def test_add_image_default_textures_dir(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    src = tmp_path / "src.png"
    _make_png(src)

    res = cp.add_image(str(proj), str(src))
    assert res["rel_path"].startswith("assets/textures/")
    assert Path(res["path"]).exists()
    assert res["sprite_frame_uuid"] == f"{res['main_uuid']}@f9941"
    assert res["texture_uuid"] == f"{res['main_uuid']}@6c48a"


def test_add_image_as_resource(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    src = tmp_path / "icon.png"
    _make_png(src)

    res = cp.add_image(str(proj), str(src), as_resource=True)
    assert res["rel_path"].startswith("assets/resources/")


def test_add_image_missing_source(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    with pytest.raises(FileNotFoundError):
        cp.add_image(str(proj), str(tmp_path / "nope.png"))


# ----------- list_assets / get_project_info -----------

def test_list_assets_finds_added_resources(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    cp.add_script(str(proj), "S", "// s")
    src = tmp_path / "img.png"
    _make_png(src)
    cp.add_image(str(proj), str(src))

    listed = cp.list_assets(str(proj))
    assert any(s["rel"].endswith("S.ts") for s in listed["scripts"])
    assert any(i["rel"].endswith("img.png") for i in listed["images"])


def test_get_project_info_reads_package_json(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p", name="demo-x")
    info = cp.get_project_info(str(proj))
    assert info["package"]["name"] == "demo-x"
    assert info["assets_exists"] is True
    assert info["library_built"] is False


# ----------- creator detection error path -----------

def test_find_creator_with_unmatched_prefix(monkeypatch):
    monkeypatch.setattr(cp, "list_creator_installs", lambda: [
        {"version": "3.8.6", "exe": "/fake", "template_dir": "/fake/t"},
    ])
    with pytest.raises(RuntimeError, match=r"3\.99"):
        cp.find_creator("3.99")


def test_find_creator_picks_highest_version(monkeypatch):
    monkeypatch.setattr(cp, "list_creator_installs", lambda: [
        {"version": "3.8.0", "exe": "/a", "template_dir": "/a/t"},
        {"version": "3.8.6", "exe": "/b", "template_dir": "/b/t"},
        {"version": "3.7.0", "exe": "/c", "template_dir": "/c/t"},
    ])
    chosen = cp.find_creator()
    assert chosen["version"] == "3.8.6"


def test_find_creator_raises_with_no_installs(monkeypatch):
    monkeypatch.setattr(cp, "list_creator_installs", lambda: [])
    with pytest.raises(RuntimeError, match="no Cocos Creator install"):
        cp.find_creator()

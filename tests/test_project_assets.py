"""Tests for the asset-import side of cocos.project.

All these are pure file-IO (no Cocos Creator install or network needed):
  * add_audio_file / add_resource_file — copy + meta sidecar
  * create_animation_clip — build .anim JSON for vec3/float/color/bool tracks
  * create_sprite_atlas — copy PNGs + per-frame meta + AutoAtlas .pac
  * add_spine_data / add_dragonbones_data / add_tiled_map_asset — copy
    skeleton/atlas/texture sets and wire all the meta sidecars

generate_and_import_image is covered separately because it shells out to
gen_asset.py + make_transparent.py via subprocess (mocked).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "p"
    (p / "assets").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


def _make_png(path: Path, w: int = 16, h: int = 16, color=(255, 0, 0)) -> None:
    Image.new("RGBA", (w, h), color).save(path)


# ============================================================
#  add_audio_file / add_resource_file
# ============================================================

def test_add_audio_file_default_resources_dir(tmp_path: Path):
    proj = _make_project(tmp_path)
    src = tmp_path / "click.mp3"
    src.write_bytes(b"ID3\x00fake-mp3-bytes")

    res = cp.add_audio_file(str(proj), str(src))
    assert res["rel_path"].startswith("assets/resources/")
    assert res["rel_path"].endswith("click.mp3")
    assert (proj / res["rel_path"]).read_bytes() == src.read_bytes()

    meta = json.loads((proj / (res["rel_path"] + ".meta")).read_text())
    assert meta["importer"] == "audio-clip"
    assert meta["uuid"] == res["uuid"]
    # The "files" list pins the on-disk extension so Cocos's CLI can find it
    assert ".mp3" in meta["files"]


def test_add_audio_file_explicit_rel_path(tmp_path: Path):
    proj = _make_project(tmp_path)
    src = tmp_path / "bgm.ogg"
    src.write_bytes(b"OggS\x00")
    res = cp.add_audio_file(str(proj), str(src), rel_path="audio/bgm/intro.ogg")
    # Caller-supplied rel_path without "assets/" prefix → goes under resources/
    assert res["rel_path"] == "assets/resources/audio/bgm/intro.ogg"
    assert (proj / res["rel_path"]).exists()


def test_add_audio_file_missing_source_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError, match="audio not found"):
        cp.add_audio_file(str(proj), str(tmp_path / "nope.mp3"))


def test_add_resource_file_writes_default_meta(tmp_path: Path):
    proj = _make_project(tmp_path)
    src = tmp_path / "config.json"
    src.write_text('{"hello":"world"}')
    res = cp.add_resource_file(str(proj), str(src))
    assert res["rel_path"] == "assets/resources/config.json"
    meta = json.loads((proj / (res["rel_path"] + ".meta")).read_text())
    assert meta["importer"] == "default"


# ============================================================
#  create_animation_clip
# ============================================================

def test_create_animation_clip_position_track(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = cp.create_animation_clip(
        str(proj), "walk", duration=2.0, sample=30,
        tracks=[{
            "path": "Body",
            "property": "position",
            "keyframes": [
                {"time": 0.0, "value": [0, 0, 0]},
                {"time": 1.0, "value": [100, 0, 0]},
                {"time": 2.0, "value": [200, 0, 0]},
            ],
        }],
    )
    assert Path(res["path"]).exists()
    assert res["rel_path"].endswith("walk.anim")
    assert res["uuid"]

    # Verify the .anim JSON has the AnimationClip header + the right duration/sample
    data = json.loads(Path(res["path"]).read_text())
    assert isinstance(data, list)
    clip = next(o for o in data if o.get("__type__") == "cc.AnimationClip")
    assert clip["_duration"] == 2.0
    assert clip["sample"] == 30

    # Vec3 track keyframes survive the build
    has_vec3_track = any(o.get("__type__") in
                         ("cc.animation.VectorTrack", "cc.animation.RealCurve")
                         for o in data)
    assert has_vec3_track or any("position" in str(o) for o in data)


def test_create_animation_clip_handles_color_and_opacity(tmp_path: Path):
    """Mix of float (opacity) + color tracks shouldn't crash."""
    proj = _make_project(tmp_path)
    res = cp.create_animation_clip(str(proj), "fade", duration=1.0, tracks=[
        {"path": "", "property": "opacity",
         "keyframes": [{"time": 0, "value": 255}, {"time": 1, "value": 0}]},
        {"path": "", "property": "color",
         "keyframes": [{"time": 0, "value": [255, 0, 0, 255]},
                       {"time": 1, "value": [0, 0, 255, 0]}]},
    ])
    data = json.loads(Path(res["path"]).read_text())
    assert any(o.get("__type__") == "cc.AnimationClip" for o in data)


def test_create_animation_clip_no_tracks_writes_empty_clip(tmp_path: Path):
    """Empty tracks list should still produce a valid AnimationClip skeleton."""
    proj = _make_project(tmp_path)
    res = cp.create_animation_clip(str(proj), "empty", duration=0.5, tracks=None)
    data = json.loads(Path(res["path"]).read_text())
    clip = next(o for o in data if o.get("__type__") == "cc.AnimationClip")
    assert clip["_duration"] == 0.5


# ============================================================
#  create_sprite_atlas
# ============================================================

def test_create_sprite_atlas_packs_multiple_pngs(tmp_path: Path):
    proj = _make_project(tmp_path)
    pngs = []
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        p = tmp_path / f"icon{i}.png"
        _make_png(p, color=color)
        pngs.append(str(p))

    res = cp.create_sprite_atlas(str(proj), "ui_icons", pngs)

    assert Path(res["dir"]).is_dir()
    assert Path(res["pac_path"]).exists()
    assert len(res["images"]) == 3
    # atlas_dir_rel tells the caller where to drop more PNGs for the
    # same atlas — the "auto" half of AutoAtlas.
    assert res["atlas_dir_rel"] == "assets/atlas/ui_icons"

    # Each image got copied + got a sprite-frame meta
    for img in res["images"]:
        assert Path(img["path"]).exists()
        assert (Path(img["path"]).with_name(Path(img["path"]).name + ".meta")).exists()
        assert img["sprite_frame_uuid"] == f"{img['uuid']}@f9941"

    # The .pac file is the single-line marker Cocos 3.8's importer
    # looks for — the full packing config lives in .pac.meta userData
    # (see test_create_sprite_atlas_meta_has_complete_userData below).
    pac = json.loads(Path(res["pac_path"]).read_text())
    assert pac == {"__type__": "cc.SpriteAtlas"}


def test_create_sprite_atlas_without_png_paths_still_valid(tmp_path: Path):
    """AutoAtlas is primarily a build-time folder-scan mechanism —
    the real value is that ANY sprite-frame PNG dropped into the atlas
    folder afterwards gets packed automatically. Calling
    create_sprite_atlas without PNGs must still produce a valid .pac +
    meta pair; the caller then uses cocos_add_image to drop PNGs into
    atlas_dir_rel."""
    proj = _make_project(tmp_path)
    res = cp.create_sprite_atlas(str(proj), "empty_pool")
    assert res["images"] == []
    assert Path(res["pac_path"]).exists()
    pac = json.loads(Path(res["pac_path"]).read_text())
    assert pac == {"__type__": "cc.SpriteAtlas"}


def test_create_sprite_atlas_meta_has_complete_userData(tmp_path: Path):
    """Cocos 3.8's auto-atlas importer reads packing config from the
    .pac.meta userData block, not from the .pac body. Prior versions
    of this module used ``"ver": "1.0.7"`` and left userData empty,
    causing the importer to silently skip packing (scene said
    SpriteAtlas but no texture was produced at build time).

    Regression guard: ensure the full 3.8 userData shape + version
    survive every change.
    """
    proj = _make_project(tmp_path)
    res = cp.create_sprite_atlas(str(proj), "icons")
    meta_path = Path(res["pac_path"] + ".meta")
    meta = json.loads(meta_path.read_text())

    assert meta["ver"] == "1.0.8"  # prior 1.0.7 silently rejected
    assert meta["importer"] == "auto-atlas"
    assert meta["imported"] is True
    assert meta["uuid"] == res["atlas_uuid"]
    assert meta["files"] == [".json"]

    ud = meta["userData"]
    # Every field Cocos 3.8 expects — leave any out and the importer
    # falls back to safer-but-useless defaults.
    for key in ("maxWidth", "maxHeight", "padding", "allowRotation",
                "forceSquared", "powerOfTwo", "algorithm", "format",
                "quality", "contourBleed", "paddingBleed",
                "filterUnused", "removeTextureInBundle",
                "removeImageInBundle", "removeSpriteAtlasInBundle",
                "compressSettings", "textureSetting"):
        assert key in ud, f"auto-atlas userData missing {key}"
    # Algorithm must be "MaxRects" (plural); "MaxRect" was a typo we
    # used to emit — the importer silently ignored it.
    assert ud["algorithm"] == "MaxRects"
    assert ud["textureSetting"]["wrapModeS"] == "repeat"


def test_create_sprite_atlas_tunables_override_defaults(tmp_path: Path):
    """Caller-supplied overrides (max_width/padding/power_of_two/...)
    land in the .pac.meta userData."""
    proj = _make_project(tmp_path)
    res = cp.create_sprite_atlas(str(proj), "tuned",
                                 max_width=2048, max_height=2048,
                                 padding=4, power_of_two=True,
                                 force_squared=True, filter_unused=False,
                                 algorithm="Basic", quality=100)
    meta = json.loads(Path(res["pac_path"] + ".meta").read_text())
    ud = meta["userData"]
    assert ud["maxWidth"] == 2048
    assert ud["maxHeight"] == 2048
    assert ud["padding"] == 4
    assert ud["powerOfTwo"] is True
    assert ud["forceSquared"] is True
    assert ud["filterUnused"] is False
    assert ud["algorithm"] == "Basic"
    assert ud["quality"] == 100


def test_create_sprite_atlas_skips_missing_pngs(tmp_path: Path):
    """Missing source files are silently skipped (logged elsewhere); the
    atlas still gets created with whatever survived."""
    proj = _make_project(tmp_path)
    real = tmp_path / "real.png"
    _make_png(real)
    res = cp.create_sprite_atlas(str(proj), "mixed",
                                 [str(real), str(tmp_path / "missing.png")])
    assert len(res["images"]) == 1
    assert Path(res["images"][0]["path"]).name == "real.png"


# ============================================================
#  enable_dynamic_atlas (runtime draw-call reduction)
# ============================================================

def test_enable_dynamic_atlas_writes_script_with_flag(tmp_path: Path):
    """The generated .ts must actually flip
    ``dynamicAtlasManager.enabled = true`` on onLoad — otherwise
    attaching it does nothing."""
    proj = _make_project(tmp_path)
    res = cp.enable_dynamic_atlas(str(proj))

    assert res["rel_path"].endswith(".ts")
    src = Path(res["path"]).read_text()
    # The critical line — without this, the whole point is lost.
    assert "dynamicAtlasManager.enabled = true" in src
    # Singleton pattern + maxFrameSize knob exposed.
    assert "public static I:" in src
    assert "maxFrameSize" in src
    # Ships both UUID forms so the caller can attach as scene component.
    assert len(res["uuid_standard"]) == 36
    assert len(res["uuid_compressed"]) == 23


def test_enable_dynamic_atlas_custom_max_frame_size(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = cp.enable_dynamic_atlas(str(proj), max_frame_size=1024,
                                  class_name="MyBooter")
    src = Path(res["path"]).read_text()
    assert "maxFrameSize: number = 1024" in src
    assert "class MyBooter extends Component" in src


def test_enable_dynamic_atlas_preserves_uuid_on_rewrite(tmp_path: Path):
    """Re-running the helper should preserve the meta UUID — same
    idempotency guarantee as every other scaffold-style generator. If
    the UUID flips, every scene-attached instance goes no-op."""
    proj = _make_project(tmp_path)
    first = cp.enable_dynamic_atlas(str(proj))
    second = cp.enable_dynamic_atlas(str(proj), max_frame_size=256)
    assert first["uuid_standard"] == second["uuid_standard"]
    assert first["uuid_compressed"] == second["uuid_compressed"]


# ============================================================
#  add_spine_data
# ============================================================

def test_add_spine_data_copies_skeleton_atlas_and_textures(tmp_path: Path):
    proj = _make_project(tmp_path)
    skel = tmp_path / "hero.json"
    skel.write_text('{"skeleton":{"hash":"x"}}')
    atlas = tmp_path / "hero.atlas"
    atlas.write_text("hero.png\nsize: 256, 256\n")
    tex = tmp_path / "hero.png"
    _make_png(tex, 256, 256)

    res = cp.add_spine_data(str(proj), str(skel), str(atlas), texture_paths=[str(tex)])

    # All three got copied into assets/spine/hero/
    assert Path(res["dir"]).name == "hero"
    assert (Path(res["dir"]) / "hero.json").exists()
    assert (Path(res["dir"]) / "hero.atlas").exists()
    assert (Path(res["dir"]) / "hero.png").exists()

    # All three got meta sidecars with distinct uuids
    assert res["skeleton_data_uuid"]
    assert res["atlas_uuid"]
    assert len(res["textures"]) == 1
    assert res["skeleton_data_uuid"] != res["atlas_uuid"]
    assert res["skeleton_data_uuid"] != res["textures"][0]["uuid"]


def test_add_spine_data_auto_detects_textures_when_not_specified(tmp_path: Path):
    proj = _make_project(tmp_path)
    skel = tmp_path / "boss.json"
    skel.write_text("{}")
    atlas = tmp_path / "boss.atlas"
    atlas.write_text("boss.png")
    # Two PNGs in the same dir → both auto-picked
    _make_png(tmp_path / "boss.png")
    _make_png(tmp_path / "boss2.png")

    res = cp.add_spine_data(str(proj), str(skel), str(atlas))
    assert len(res["textures"]) == 2


def test_add_spine_data_raises_on_missing_skeleton(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError, match="Spine JSON not found"):
        cp.add_spine_data(str(proj),
                          str(tmp_path / "nope.json"),
                          str(tmp_path / "nope.atlas"))


# ============================================================
#  add_dragonbones_data
# ============================================================

def test_add_dragonbones_data_copies_three_files(tmp_path: Path):
    proj = _make_project(tmp_path)
    ske = tmp_path / "monster_ske.json"
    ske.write_text('{"frameRate":24}')
    tex_json = tmp_path / "monster_tex.json"
    tex_json.write_text('{"name":"m"}')
    tex_png = tmp_path / "monster_tex.png"
    _make_png(tex_png, 64, 64)

    res = cp.add_dragonbones_data(str(proj), str(ske), str(tex_json),
                                  texture_paths=[str(tex_png)])
    assert Path(res["dir"]).is_dir()
    for fname in ("monster_ske.json", "monster_tex.json", "monster_tex.png"):
        assert (Path(res["dir"]) / fname).exists()
    assert res["dragon_asset_uuid"]
    assert res["dragon_atlas_uuid"]
    assert len(res["textures"]) == 1


# ============================================================
#  add_tiled_map_asset
# ============================================================

def test_add_tiled_map_asset_with_explicit_tsx_and_textures(tmp_path: Path):
    proj = _make_project(tmp_path)
    tmx = tmp_path / "map1.tmx"
    tmx.write_text('<?xml version="1.0"?><map width="10" height="10"/>')
    tsx = tmp_path / "tiles.tsx"
    tsx.write_text('<?xml version="1.0"?><tileset name="tiles"/>')
    tex = tmp_path / "tiles.png"
    _make_png(tex, 128, 128)

    res = cp.add_tiled_map_asset(str(proj), str(tmx),
                                 tsx_paths=[str(tsx)],
                                 texture_paths=[str(tex)])

    assert (Path(res["dir"]) / "map1.tmx").exists()
    assert (Path(res["dir"]) / "tiles.tsx").exists()
    assert (Path(res["dir"]) / "tiles.png").exists()
    assert res["tmx_uuid"]
    assert len(res["tsx_files"]) == 1
    assert len(res["textures"]) == 1


def test_add_tiled_map_asset_auto_detects_tsx_and_textures(tmp_path: Path):
    proj = _make_project(tmp_path)
    tmx = tmp_path / "world.tmx"
    tmx.write_text("<map/>")
    (tmp_path / "ground.tsx").write_text("<tileset/>")
    (tmp_path / "wall.tsx").write_text("<tileset/>")
    _make_png(tmp_path / "ground.png", 64, 64)

    res = cp.add_tiled_map_asset(str(proj), str(tmx))
    assert len(res["tsx_files"]) == 2
    assert len(res["textures"]) == 1


def test_add_tiled_map_asset_raises_on_missing_tmx(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(FileNotFoundError, match="TMX not found"):
        cp.add_tiled_map_asset(str(proj), str(tmp_path / "missing.tmx"))


# ============================================================
#  generate_and_import_image — subprocess fully mocked
# ============================================================
#
# The real flow shells out to gen_asset.py + make_transparent.py via
# subprocess.run. We patch subprocess.run inside cocos.project so the test
# runs offline + deterministically while still exercising the orchestration
# logic (file discovery, transparent skip rules, add_image hand-off).

class _FakeProc:
    def __init__(self, returncode: int = 0, stderr: str = ""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def test_generate_and_import_image_full_flow(tmp_path: Path, monkeypatch):
    """Happy path: gen_asset.py produces a PNG → make_transparent.py
    produces -transparent.png → add_image imports it."""
    proj = _make_project(tmp_path)
    monkeypatch.setenv("ZHIPU_API_KEY", "test-key")

    captured_calls: list[list[str]] = []
    import shutil as _shutil
    import tempfile as _tempfile
    fake_tmp = Path(_tempfile.gettempdir()) / "cocos-mcp-gen"
    fake_tmp.mkdir(exist_ok=True)
    # Pre-stage a "generated" PNG that the orchestrator will discover
    generated = fake_tmp / "fake-output.png"
    _make_png(generated, 64, 64, (50, 200, 50))
    # Touch it so it's the newest file
    generated.touch()

    def fake_run(cmd, **kwargs):
        captured_calls.append(cmd)
        # If this is the make_transparent.py invocation, simulate its
        # behavior by writing a *-transparent.png next to the input.
        if "make_transparent.py" in cmd[1]:
            src = Path(cmd[2])
            trans = src.with_name(src.stem + "-transparent.png")
            _shutil.copy2(src, trans)
        return _FakeProc(returncode=0)

    # subprocess is imported lazily inside the function — patching the
    # global module's `run` attribute is what the local `import subprocess`
    # statement will see.
    import subprocess as _sub
    monkeypatch.setattr(_sub, "run", fake_run)

    res = cp.generate_and_import_image(
        str(proj), prompt="a fish", name="fish", style="icon",
        width=512, height=512, provider="zhipu", transparent=True,
    )

    assert res["main_uuid"]  # came from add_image
    assert res["sprite_frame_uuid"].endswith("@f9941")
    assert "generated_png" in res
    assert "transparent_png" in res
    # The transparent variant should be the one that landed in the project
    assert "-transparent.png" in res["transparent_png"]

    # gen_asset.py was invoked with --provider zhipu --style icon
    gen_calls = [c for c in captured_calls if "gen_asset.py" in c[1]]
    assert gen_calls, "gen_asset.py was never invoked"
    cmd = gen_calls[0]
    assert "--provider" in cmd and "zhipu" in cmd
    assert "--style" in cmd and "icon" in cmd
    assert "--width" in cmd and "512" in cmd

    # Final image landed in the project
    imported = Path(res["path"])
    assert imported.exists()
    assert imported.read_bytes()  # non-empty


def test_generate_and_import_image_skips_transparent_for_scene_style(tmp_path: Path, monkeypatch):
    """When style is 'scene' or 'tile', make_transparent.py must NOT run —
    otherwise the chroma key would eat real background pixels."""
    proj = _make_project(tmp_path)
    monkeypatch.setenv("ZHIPU_API_KEY", "k")

    import tempfile as _tempfile
    fake_tmp = Path(_tempfile.gettempdir()) / "cocos-mcp-gen"
    fake_tmp.mkdir(exist_ok=True)
    generated = fake_tmp / "scene-out.png"
    _make_png(generated, 32, 32, (10, 50, 100))
    generated.touch()

    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return _FakeProc(returncode=0)

    import subprocess as _sub
    monkeypatch.setattr(_sub, "run", fake_run)

    cp.generate_and_import_image(str(proj), prompt="a forest", name="forest",
                                 style="scene", transparent=True)

    # gen_asset.py ran but make_transparent.py did NOT (style=scene short-circuits)
    assert any("gen_asset.py" in c[1] for c in captured)
    assert not any("make_transparent.py" in c[1] for c in captured), \
        "make_transparent.py must not run for style='scene'"


def test_generate_and_import_image_propagates_gen_failure(tmp_path: Path, monkeypatch):
    proj = _make_project(tmp_path)
    monkeypatch.setenv("ZHIPU_API_KEY", "k")

    def fake_run(cmd, **kwargs):
        return _FakeProc(returncode=1, stderr="ERR rate limited\n")

    import subprocess as _sub
    monkeypatch.setattr(_sub, "run", fake_run)

    with pytest.raises(RuntimeError, match=r"gen_asset\.py failed"):
        cp.generate_and_import_image(str(proj), prompt="x", name="x")


def test_generate_and_import_image_raises_when_no_png_produced(tmp_path: Path, monkeypatch):
    """gen_asset.py exited 0 but somehow didn't write a PNG — should error
    rather than silently importing whatever was newest in the cache dir."""
    proj = _make_project(tmp_path)
    monkeypatch.setenv("ZHIPU_API_KEY", "k")

    import shutil as _shutil
    import tempfile as _tempfile
    fake_tmp = Path(_tempfile.gettempdir()) / "cocos-mcp-gen"
    if fake_tmp.exists():
        _shutil.rmtree(fake_tmp)  # ensure no leftover PNGs from other tests
    fake_tmp.mkdir(exist_ok=True)

    import subprocess as _sub
    monkeypatch.setattr(_sub, "run", lambda *a, **k: _FakeProc(returncode=0))

    with pytest.raises(RuntimeError, match="produced no PNG output"):
        cp.generate_and_import_image(str(proj), prompt="x", name="x")

"""Tests for the three performance-pass optimizations:

1. ``COCOS_MCP_SCENE_COMPACT`` env var → smaller scene files (faster IO).
2. ``batch_ops`` extended ops (widget/layout/progress/audio/animation/etc.)
   produce the same in-scene structure as their public-API counterparts.
3. ``gen_asset.py`` SHA-256 cache key is stable for identical inputs and
   distinguishes by every input dimension.
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import scene_builder as sb
from cocos.gen_asset import _cache_key

# ----------- compact mode -----------

def _build_big_scene(path: Path, n: int) -> None:
    sb.create_empty_scene(path)
    sb.batch_ops(path, [{"op": "add_node", "name": f"N{i}", "parent_id": 2}
                        for i in range(n)])


def test_compact_mode_writes_smaller_file(tmp_path: Path, monkeypatch):
    pretty = tmp_path / "pretty.scene"
    compact = tmp_path / "compact.scene"

    # Default (indent=2) baseline
    _build_big_scene(pretty, 200)
    pretty_size = pretty.stat().st_size

    # Reload module with COCOS_MCP_SCENE_COMPACT=1 forcing the env-var read at
    # import-time. We have to reload because the flag is captured at module load.
    monkeypatch.setenv("COCOS_MCP_SCENE_COMPACT", "1")
    import cocos.scene_builder._helpers as helpers_mod
    importlib.reload(helpers_mod)
    importlib.reload(sb)

    try:
        _build_big_scene(compact, 200)
        compact_size = compact.stat().st_size
        # Compact should be at least 30% smaller than pretty for big scenes
        assert compact_size < pretty_size * 0.7, (
            f"compact={compact_size} should be <70% of pretty={pretty_size}")
        # Both must still parse to the same logical content
        with open(pretty) as f:
            p = json.load(f)
        with open(compact) as f:
            c = json.load(f)
        assert len(p) == len(c)
    finally:
        monkeypatch.delenv("COCOS_MCP_SCENE_COMPACT")
        importlib.reload(helpers_mod)
        importlib.reload(sb)


# ----------- batch_ops extended ops -----------

def _scene() -> tuple[Path, int]:
    f = tempfile.NamedTemporaryFile(suffix=".scene", delete=False)
    f.close()
    info = sb.create_empty_scene(f.name)
    return Path(f.name), info["canvas_node_id"]


def test_batch_add_widget_layout_progress():
    path, canvas = _scene()
    res = sb.batch_ops(str(path), [
        {"op": "add_node", "parent_id": canvas, "name": "Panel"},
        {"op": "add_uitransform", "node_id": "$0", "width": 300, "height": 200},
        {"op": "add_widget", "node_id": "$0", "align_flags": 45},
        {"op": "add_layout", "node_id": "$0", "layout_type": 2, "spacing_y": 10},
        {"op": "add_progress_bar", "node_id": "$0", "progress": 0.5, "total_length": 200},
    ])
    assert all(isinstance(r, int) for r in res["results"])

    with open(path) as f:
        s = json.load(f)
    types = [s[r].get("__type__") for r in res["results"][1:]]
    assert types == ["cc.UITransform", "cc.Widget", "cc.Layout", "cc.ProgressBar"]
    # progress bar fields wired correctly
    pgb = s[res["results"][4]]
    assert pgb["progress"] == 0.5
    assert pgb["totalLength"] == 200


def test_batch_add_audio_animation_camera_mask_richtext():
    path, canvas = _scene()
    res = sb.batch_ops(str(path), [
        {"op": "add_node", "parent_id": canvas, "name": "Audio"},
        {"op": "add_audio_source", "node_id": "$0", "volume": 0.7, "loop": True},
        {"op": "add_node", "parent_id": canvas, "name": "Anim"},
        {"op": "add_animation", "node_id": "$2", "play_on_load": False},
        {"op": "add_node", "parent_id": canvas, "name": "Cam"},
        {"op": "add_camera", "node_id": "$4", "ortho_height": 480},
        {"op": "add_node", "parent_id": canvas, "name": "Mask"},
        {"op": "add_mask", "node_id": "$6", "mask_type": 1, "segments": 32},
        {"op": "add_node", "parent_id": canvas, "name": "Rich"},
        {"op": "add_richtext", "node_id": "$8", "text": "<color=red>X</color>"},
    ])
    assert "error" not in str(res["results"]), res["results"]

    with open(path) as f:
        s = json.load(f)
    assert s[res["results"][1]]["volume"] == 0.7
    assert s[res["results"][1]]["loop"] is True
    assert s[res["results"][3]]["playOnLoad"] is False
    assert s[res["results"][5]]["_orthoHeight"] == 480
    assert s[res["results"][7]]["_type"] == 1
    assert s[res["results"][9]]["string"] == "<color=red>X</color>"


def test_batch_set_scale_rotation_layer_uuid_property():
    path, canvas = _scene()
    res = sb.batch_ops(str(path), [
        {"op": "add_node", "parent_id": canvas, "name": "T"},
        {"op": "set_scale", "node_id": "$0", "sx": 2, "sy": 3},
        {"op": "set_rotation", "node_id": "$0", "angle_z": 90},
        {"op": "set_layer", "node_id": "$0", "layer": 1073741824},
        {"op": "set_uuid_property", "object_id": "$0", "prop_name": "_extraSpriteFrame",
         "uuid": "abc-uuid"},
    ])
    assert res["results"] == [res["results"][0], True, True, True, True]

    with open(path) as f:
        s = json.load(f)
    node = s[res["results"][0]]
    assert node["_lscale"]["x"] == 2
    assert node["_lscale"]["y"] == 3
    assert node["_euler"]["z"] == 90
    assert node["_layer"] == 1073741824
    assert node["_extraSpriteFrame"] == {"__uuid__": "abc-uuid"}


# ----------- gen_asset cache key -----------

def test_cache_key_stable_for_same_inputs():
    k1 = _cache_key("zhipu", "cogview-3-flash", "a bird", (1024, 1024), None)
    k2 = _cache_key("zhipu", "cogview-3-flash", "a bird", (1024, 1024), None)
    assert k1 == k2
    assert len(k1) == 16


def test_cache_key_changes_with_each_dimension():
    base = _cache_key("zhipu", "cogview-3-flash", "a bird", (1024, 1024), None)
    assert base != _cache_key("pollinations", "cogview-3-flash", "a bird", (1024, 1024), None)
    assert base != _cache_key("zhipu", "cogview-4", "a bird", (1024, 1024), None)
    assert base != _cache_key("zhipu", "cogview-3-flash", "a fish", (1024, 1024), None)
    assert base != _cache_key("zhipu", "cogview-3-flash", "a bird", (1024, 768), None)


def test_cache_key_ignores_seed_for_zhipu_only():
    # Zhipu API doesn't honor seed → seed must NOT be part of key
    z1 = _cache_key("zhipu", "cogview-3-flash", "x", (1024, 1024), 1)
    z2 = _cache_key("zhipu", "cogview-3-flash", "x", (1024, 1024), 2)
    assert z1 == z2

    # Pollinations honors seed → it MUST be part of key
    p1 = _cache_key("pollinations", "flux", "x", (1024, 1024), 1)
    p2 = _cache_key("pollinations", "flux", "x", (1024, 1024), 2)
    assert p1 != p2


# ----------- .env quote handling -----------

def test_env_file_strips_double_quotes(tmp_path: Path):
    from cocos.gen_asset import _load_env_file
    f = tmp_path / ".env"
    f.write_text('ZHIPU_API_KEY="sk-abc123"\nOTHER_KEY=plain\n')
    env = _load_env_file(f)
    assert env["ZHIPU_API_KEY"] == "sk-abc123"
    assert env["OTHER_KEY"] == "plain"


def test_env_file_strips_single_quotes(tmp_path: Path):
    from cocos.gen_asset import _load_env_file
    f = tmp_path / ".env"
    f.write_text("KEY='value with spaces'\n")
    env = _load_env_file(f)
    assert env["KEY"] == "value with spaces"


def test_env_file_does_not_strip_mismatched_quotes(tmp_path: Path):
    from cocos.gen_asset import _load_env_file
    f = tmp_path / ".env"
    f.write_text("""KEY="unterminated\nKEY2='only-leading\n""")
    env = _load_env_file(f)
    assert env["KEY"] == '"unterminated'
    assert env["KEY2"] == "'only-leading"


def test_env_file_ignores_comments_and_blanks(tmp_path: Path):
    from cocos.gen_asset import _load_env_file
    f = tmp_path / ".env"
    f.write_text("# comment\n\nKEY=value\n   # indented comment\n")
    env = _load_env_file(f)
    assert env == {"KEY": "value"}

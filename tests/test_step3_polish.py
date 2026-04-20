"""Tests for Step 3 additions: set_fog, add_webview, add_scroll_bar,
add_page_view_indicator, and the cli_build options extension.

Field defaults against cocos-engine v3.8.6 sources (cc.FogInfo,
cc.WebView, cc.ScrollBar, cc.PageViewIndicator). If the engine bumps
default values later, fix the assertions from the source — don't relax
them to whatever our code emits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import build as cb
from cocos import scene_builder as sb


def _tmp_scene(tmp_path: Path) -> tuple[Path, dict]:
    path = tmp_path / "s.scene"
    info = sb.create_empty_scene(path)
    return path, info


def _make_project_skeleton(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(json.dumps({"name": "demo"}))
    return root


# ----------- set_fog -----------

def test_set_fog_lazy_creates_fog_info_when_missing(tmp_path: Path):
    """create_empty_scene doesn't emit a FogInfo yet — set_fog must
    inject one + wire it under SceneGlobals.fog."""
    path, _ = _tmp_scene(tmp_path)
    # Pre-condition: no FogInfo and no fog link yet.
    with open(path) as f:
        before = json.load(f)
    assert not any(isinstance(o, dict) and o.get("__type__") == "cc.FogInfo" for o in before)

    sb.set_fog(path, enabled=True, fog_type=sb.FOG_EXP, density=0.2)

    with open(path) as f:
        after = json.load(f)
    fog = next((o for o in after if isinstance(o, dict) and o.get("__type__") == "cc.FogInfo"), None)
    assert fog is not None, "FogInfo should have been lazy-created"
    assert fog["_enabled"] is True
    assert fog["_type"] == sb.FOG_EXP
    assert fog["_fogDensity"] == 0.2

    # SceneGlobals must now link to it via the `fog` field
    globals_obj = next((o for o in after if o.get("__type__") == "cc.SceneGlobals"), None)
    fog_idx = after.index(fog)
    assert globals_obj["fog"] == {"__id__": fog_idx}


def test_set_fog_defaults_match_engine(tmp_path: Path):
    """Freshly-created FogInfo must carry cocos-engine v3.8.6 defaults."""
    path, _ = _tmp_scene(tmp_path)
    # Call with all None overrides — we only want to create + inspect defaults.
    sb.set_fog(path)
    with open(path) as f:
        scene = json.load(f)
    fog = next(o for o in scene if o.get("__type__") == "cc.FogInfo")
    # From cocos/scene-graph/scene-globals.ts FogInfo
    assert fog["_type"] == 0  # LINEAR
    assert fog["_enabled"] is False
    assert fog["_fogDensity"] == 0.3
    assert fog["_fogStart"] == 0.5
    assert fog["_fogEnd"] == 300
    assert fog["_fogAtten"] == 5
    assert fog["_fogTop"] == 1.5
    assert fog["_fogRange"] == 1.2
    assert fog["_accurate"] is False


def test_set_fog_is_idempotent_no_duplicates(tmp_path: Path):
    """Calling set_fog twice must NOT create two FogInfo objects."""
    path, _ = _tmp_scene(tmp_path)
    sb.set_fog(path, enabled=True)
    sb.set_fog(path, density=0.1)
    with open(path) as f:
        scene = json.load(f)
    fog_count = sum(1 for o in scene if o.get("__type__") == "cc.FogInfo")
    assert fog_count == 1, f"expected 1 FogInfo, got {fog_count}"
    # Second call's density write must be visible, first call's enabled preserved
    fog = next(o for o in scene if o.get("__type__") == "cc.FogInfo")
    assert fog["_enabled"] is True
    assert fog["_fogDensity"] == 0.1


def test_set_fog_leaves_scene_valid(tmp_path: Path):
    path, _ = _tmp_scene(tmp_path)
    sb.set_fog(path, enabled=True, fog_type=sb.FOG_LAYERED, top=2.0, fog_range=1.5)
    v = sb.validate_scene(path)
    assert v["valid"], f"scene invalid: {v['issues']}"


# ----------- add_webview -----------

def test_webview_default_url_matches_engine(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Terms")
    cid = sb.add_webview(str(path), n)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.WebView"
    # Engine default URL
    assert obj["_url"] == "https://cocos.com"
    assert obj["webviewEvents"] == []


def test_webview_custom_url(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "ActivityPage")
    cid = sb.add_webview(str(path), n, url="https://example.com/promo")
    assert sb.get_object(path, cid)["_url"] == "https://example.com/promo"


# ----------- add_scroll_bar -----------

def test_scroll_bar_defaults_and_refs(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Bar")
    handle = sb.add_node(path, n, "Handle")
    sv = sb.add_node(path, info["canvas_node_id"], "ScrollContainer")
    cid = sb.add_scroll_bar(str(path), n,
                            handle_sprite_id=handle,
                            scroll_view_id=sv,
                            direction=sb.SCROLLBAR_VERTICAL,
                            enable_auto_hide=True,
                            auto_hide_time=2.5)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.ScrollBar"
    assert obj["_direction"] == 1  # VERTICAL
    assert obj["_enableAutoHide"] is True
    assert obj["_autoHideTime"] == 2.5
    # Both refs are __id__ pointers (not uuids)
    assert obj["_handle"] == {"__id__": handle}
    assert obj["_scrollView"] == {"__id__": sv}


def test_scroll_bar_omits_null_refs(tmp_path: Path):
    """When caller doesn't provide handle/scroll_view, those keys must
    not appear at all — the engine treats missing keys as null."""
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Unwired")
    cid = sb.add_scroll_bar(str(path), n)
    obj = sb.get_object(path, cid)
    assert "_handle" not in obj
    assert "_scrollView" not in obj


# ----------- add_page_view_indicator -----------

def test_page_view_indicator_cell_size_and_spacing(tmp_path: Path):
    path, info = _tmp_scene(tmp_path)
    n = sb.add_node(path, info["canvas_node_id"], "Dots")
    cid = sb.add_page_view_indicator(str(path), n,
                                     sprite_frame_uuid="dot-uuid",
                                     cell_width=16, cell_height=16,
                                     spacing=8)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.PageViewIndicator"
    assert obj["_cellSize"] == {"__type__": "cc.Size", "width": 16, "height": 16}
    assert obj["spacing"] == 8
    # spriteFrame ref carries the expected-type hint
    assert obj["_spriteFrame"] == {"__uuid__": "dot-uuid", "__expectedType__": "cc.SpriteFrame"}


# ----------- cli_build options extension -----------

def test_cli_build_passthrough_opts_appear_in_command(tmp_path: Path, monkeypatch):
    """Explicit convenience params + build_options dict should be joined
    into the Cocos --build "k=v;..." string."""
    proj = _make_project_skeleton(tmp_path / "p")
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    captured_cmd: list[str] = []

    class _FakeProc:
        returncode = 36

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        captured_cmd.extend(cmd)
        return _FakeProc()

    monkeypatch.setattr(cb.subprocess, "run", _fake_run)

    # Make the build_dir look non-empty so the success check passes
    build_dir = proj / "build" / "web-mobile"
    build_dir.mkdir(parents=True)
    (build_dir / "index.html").write_text("<html/>")

    cb.cli_build(str(proj), clean_temp=False,
                 source_maps=True, md5_cache=True,
                 skip_compress_texture=False,
                 build_options={"customFlag": "xyz"})

    # The --build arg is the string right after "--build" in captured_cmd
    assert "--build" in captured_cmd
    build_flag = captured_cmd[captured_cmd.index("--build") + 1]
    # Order-independent checks — we don't pin the dict iteration order
    assert "platform=web-mobile" in build_flag
    assert "debug=true" in build_flag
    assert "sourceMaps=true" in build_flag
    assert "md5Cache=true" in build_flag
    assert "skipCompressTexture=false" in build_flag
    assert "customFlag=xyz" in build_flag


def test_cli_build_convenience_param_wins_over_dict(tmp_path: Path, monkeypatch):
    """source_maps=True should override build_options={'sourceMaps': False}."""
    proj = _make_project_skeleton(tmp_path / "p")
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    captured_cmd: list[str] = []
    monkeypatch.setattr(cb.subprocess, "run",
                        lambda cmd, stdout=None, stderr=None, timeout=None:
                        (captured_cmd.extend(cmd), type("P", (), {"returncode": 36})())[1])

    cb.cli_build(str(proj), clean_temp=False,
                 source_maps=True,
                 build_options={"sourceMaps": False, "extra": 1})

    build_flag = captured_cmd[captured_cmd.index("--build") + 1]
    assert "sourceMaps=true" in build_flag
    assert "sourceMaps=false" not in build_flag
    assert "extra=1" in build_flag


def test_cli_build_rejects_unsafe_option_value(tmp_path: Path, monkeypatch):
    """Values containing ';' or '=' break Cocos CLI parsing — must raise."""
    proj = _make_project_skeleton(tmp_path / "p")
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })
    with pytest.raises(ValueError, match="';' or '='"):
        cb.cli_build(str(proj), clean_temp=False,
                     build_options={"sneaky": "a;b=c"})

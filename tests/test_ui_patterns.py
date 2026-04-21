"""Tests for the UI composite patterns and animation presets.

Each composite is a sequence of primitive add_* calls producing a
known set of components; we check shape (all expected nodes + types
created, buttons themed via tokens, widgets anchored correctly) more
than pixel-perfect layout math — layout values change with theme
spacing and would be brittle to assert exactly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp
from cocos import scene_builder as sb


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    (p / "assets").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


def _scene_in_project(proj: Path, theme: str = "dark_game") -> tuple[Path, dict]:
    cp.set_ui_theme(str(proj), theme=theme)
    scene = proj / "assets" / "scenes" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    return scene, info


def _components_on_node(scene_path: Path, node_id: int) -> list[dict]:
    with open(scene_path) as f:
        data = json.load(f)
    return [data[ref["__id__"]]
            for ref in data[node_id].get("_components", [])
            if isinstance(ref, dict)]


def _component_types_on(scene_path: Path, node_id: int) -> set[str]:
    return {c.get("__type__") for c in _components_on_node(scene_path, node_id)}


# ======================================== #
# Dialog modal
# ======================================== #

def test_dialog_modal_basic_shape(tmp_path: Path):
    """One call produces backdrop + panel + title + buttons — and all
    the IDs come back in the return dict for follow-up wiring."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    res = sb.add_dialog_modal(str(scene), info["canvas_node_id"],
                              title="Game Over", body="Score: 1200",
                              buttons=[{"text": "Retry", "variant": "primary"},
                                       {"text": "Menu", "variant": "ghost"}])
    assert set(res.keys()) >= {
        "backdrop_node_id", "panel_node_id", "title_node_id",
        "body_node_id", "button_row_node_id", "button_ids",
    }
    assert res["body_node_id"] is not None  # body given, so body node exists
    assert len(res["button_ids"]) == 2


def test_dialog_modal_backdrop_blocks_input(tmp_path: Path):
    """A dialog that doesn't block underlying touches is worse than
    no dialog — regression guard."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_dialog_modal(str(scene), info["canvas_node_id"], "Test")
    types = _component_types_on(scene, res["backdrop_node_id"])
    assert "cc.BlockInputEvents" in types
    assert "cc.Sprite" in types
    assert "cc.Widget" in types  # backdrop stretches to fullscreen


def test_dialog_modal_buttons_use_theme_colors(tmp_path: Path):
    """primary button should carry the theme's primary color, not
    the hardcoded white."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    res = sb.add_dialog_modal(str(scene), info["canvas_node_id"],
                              title="X",
                              buttons=[{"text": "Go", "variant": "primary"}])
    btn_node = res["button_ids"][0]["node_id"]
    btn_cmp = next(c for c in _components_on_node(scene, btn_node)
                   if c["__type__"] == "cc.Button")
    # dark_game.primary = #6366f1 = rgb(99,102,241)
    nc = btn_cmp["_normalColor"]
    assert (nc["r"], nc["g"], nc["b"]) == (99, 102, 241)


def test_dialog_modal_no_body_skips_body_node(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_dialog_modal(str(scene), info["canvas_node_id"], "Just title")
    assert res["body_node_id"] is None


def test_dialog_modal_validates_scene(tmp_path: Path):
    """Composite must produce a structurally valid scene — no dangling
    refs, all UI nodes under Canvas."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    sb.add_dialog_modal(str(scene), info["canvas_node_id"],
                        title="V", body="body", buttons=[
                            {"text": "A", "variant": "primary"},
                            {"text": "B", "variant": "ghost"},
                            {"text": "C", "variant": "danger"},
                        ])
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ======================================== #
# Main menu
# ======================================== #

def test_main_menu_shape_and_buttons(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_main_menu(str(scene), info["canvas_node_id"],
                           title="Flappy",
                           buttons=[{"text": "Start", "variant": "primary"},
                                    {"text": "Help", "variant": "secondary"},
                                    {"text": "Quit", "variant": "danger"}])
    assert len(res["button_ids"]) == 3
    # Title is a direct child of the stack, with a Label component
    types = _component_types_on(scene, res["title_node_id"])
    assert "cc.Label" in types


def test_main_menu_bg_uses_theme_bg_color(tmp_path: Path):
    """bg color comes from theme.bg preset, not arbitrary."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="light_minimal")
    res = sb.add_main_menu(str(scene), info["canvas_node_id"], title="X")
    bg_sprite = next(c for c in _components_on_node(scene, res["bg_node_id"])
                     if c["__type__"] == "cc.Sprite")
    # light_minimal.bg = #ffffff
    assert (bg_sprite["_color"]["r"], bg_sprite["_color"]["g"],
            bg_sprite["_color"]["b"]) == (255, 255, 255)


def test_main_menu_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    sb.add_main_menu(str(scene), info["canvas_node_id"], title="OK")
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ======================================== #
# HUD bar
# ======================================== #

def test_hud_bar_top_side_default(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_hud_bar(str(scene), info["canvas_node_id"])
    types = _component_types_on(scene, res["bar_node_id"])
    assert "cc.Widget" in types
    assert "cc.Layout" in types
    # Default items include 2 labels
    assert len(res["item_node_ids"]) == 2


def test_hud_bar_custom_items_and_spacer(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_hud_bar(str(scene), info["canvas_node_id"], items=[
        {"kind": "label", "text": "Coins: 42", "width": 200, "color_preset": "warn"},
        {"kind": "spacer", "width": 60},
        {"kind": "label", "text": "♥♥♥", "width": 120, "color_preset": "danger"},
    ])
    # Only labels land in item_node_ids; spacers are invisible padding
    assert len(res["item_node_ids"]) == 2
    assert res["item_node_ids"][0]["text"] == "Coins: 42"


def test_hud_bar_bottom_side(tmp_path: Path):
    """side='bottom' should anchor the bar to the bottom via align_flags."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_hud_bar(str(scene), info["canvas_node_id"], side="bottom")
    widget = next(c for c in _components_on_node(scene, res["bar_node_id"])
                  if c["__type__"] == "cc.Widget")
    # Serialized widget carries alignFlags as an int field
    # align_flags 14 = bottom(2) + left(4) + right(8); 13 = top(1)+l+r
    flags = widget.get("_alignFlags", widget.get("alignFlags"))
    assert flags == 14


# ======================================== #
# Animation presets — fade_in
# ======================================== #

def test_fade_in_creates_anim_clip_and_attaches_components(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Title")

    res = sb.add_fade_in(scene, n, duration=0.5)
    # Clip file exists inside the project
    clip = Path(res["clip_path"])
    assert clip.exists() and clip.suffix == ".anim"
    # Node gained UIOpacity + Animation components
    types = _component_types_on(scene, n)
    assert "cc.UIOpacity" in types
    assert "cc.Animation" in types


def test_fade_in_uiopacity_starts_at_zero(tmp_path: Path):
    """Without setting UIOpacity=0, the first rendered frame would
    flash at full opacity before the clip's first keyframe lands."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Fader")
    sb.add_fade_in(scene, n)

    opacity_cmp = next(c for c in _components_on_node(scene, n)
                       if c["__type__"] == "cc.UIOpacity")
    assert opacity_cmp["_opacity"] == 0  # backing field (protected)


def test_fade_in_clip_uuid_wired_to_animation(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    res = sb.add_fade_in(scene, n)
    anim_cmp = next(c for c in _components_on_node(scene, n)
                    if c["__type__"] == "cc.Animation")
    # Both _defaultClip and _clips reference the new anim by UUID
    assert anim_cmp["_defaultClip"]["__uuid__"] == res["clip_uuid"]
    assert anim_cmp["_clips"][0]["__uuid__"] == res["clip_uuid"]


def test_fade_in_with_delay_holds_at_zero(tmp_path: Path):
    """delay=0.2 means opacity stays at 0 for the first 0.2s. Check
    by inspecting the .anim file's keyframe times."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    res = sb.add_fade_in(scene, n, duration=0.4, delay=0.2)
    with open(res["clip_path"]) as f:
        clip_data = json.load(f)
    # Clip duration = delay + duration
    clip_obj = clip_data[0]
    assert clip_obj["_duration"] == pytest.approx(0.6)
    # The first RealCurve has 3 time samples: [0.0, 0.2, 0.6]
    curve = next(o for o in clip_data if o.get("__type__") == "cc.animation.RealCurve")
    times = curve["_times"]
    assert times[0] == 0.0
    assert times[1] == pytest.approx(0.2)
    assert times[-1] == pytest.approx(0.6)


def test_fade_in_requires_project(tmp_path: Path):
    """Scene outside a Cocos project layout can't host an .anim asset —
    presets should point the caller at the fix rather than fall over."""
    scene = tmp_path / "floating.scene"
    info = sb.create_empty_scene(scene)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(FileNotFoundError, match="project"):
        sb.add_fade_in(scene, n)


# ======================================== #
# Animation presets — slide_in
# ======================================== #

def test_slide_in_from_bottom_preserves_end_position(tmp_path: Path):
    """The end pose must equal the node's pre-animate _lpos, not (0,0,0).
    Otherwise the clip snaps everything to origin at end."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Panel", lpos=(100, 200, 0))

    res = sb.add_slide_in(scene, n, from_side="bottom",
                          distance=150, duration=0.3)

    with open(res["clip_path"]) as f:
        clip_data = json.load(f)
    # Three RealCurves (one per x/y/z channel). End values at the last
    # keyframe should match the original lpos.
    curves = [o for o in clip_data if o.get("__type__") == "cc.animation.RealCurve"]
    assert len(curves) == 3
    # x at last keyframe
    assert curves[0]["_values"][-1]["value"] == 100
    # y at last keyframe
    assert curves[1]["_values"][-1]["value"] == 200
    # x at first keyframe = 100 (no x offset for bottom slide)
    assert curves[0]["_values"][0]["value"] == 100
    # y at first keyframe = 200 - 150 (bottom slide = negative Y offset)
    assert curves[1]["_values"][0]["value"] == 50


def test_slide_in_from_left_offsets_x(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Panel", lpos=(0, 0, 0))
    res = sb.add_slide_in(scene, n, from_side="left", distance=300, duration=0.3)

    with open(res["clip_path"]) as f:
        clip_data = json.load(f)
    curves = [o for o in clip_data if o.get("__type__") == "cc.animation.RealCurve"]
    # x starts at -300, ends at 0
    assert curves[0]["_values"][0]["value"] == -300
    assert curves[0]["_values"][-1]["value"] == 0
    # y stays at 0 throughout
    assert curves[1]["_values"][0]["value"] == 0
    assert curves[1]["_values"][-1]["value"] == 0


def test_slide_in_rejects_bad_side(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="from_side"):
        sb.add_slide_in(scene, n, from_side="diagonal")


# ======================================== #
# Scene validation across patterns
# ======================================== #

def test_hud_bar_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    sb.add_hud_bar(str(scene), info["canvas_node_id"])
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]

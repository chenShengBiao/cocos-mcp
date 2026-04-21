"""Tests for the fourth UI/UX batch:

* ``add_toast`` — transient notification with 3-phase fade clip
* ``add_loading_spinner`` — rotating icon + optional caption
* ``derive_theme_from_seed`` — programmatic palette from a brand color
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp
from cocos import scene_builder as sb
from cocos.project import ui_tokens as tok


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


def _component_on(scene_path: Path, node_id: int, type_name: str) -> dict | None:
    with open(scene_path) as f:
        data = json.load(f)
    for ref in data[node_id].get("_components", []):
        if isinstance(ref, dict):
            cmp = data[ref["__id__"]]
            if cmp.get("__type__") == type_name:
                return cmp
    return None


# ================================================ #
# 1. add_toast
# ================================================ #

def test_toast_three_phase_fade_keyframes(tmp_path: Path):
    """Toast fade clip must have exactly 4 keyframes: 0, fade-in-end,
    fade-out-start, duration (values 0, 255, 255, 0)."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_toast(scene, info["canvas_node_id"], "Saved", duration=2.0)

    with open(scene) as f:
        scene_data = json.load(f)
    anim_cmp = scene_data[res["animation_component_id"]]
    clip_path = proj / "assets/animations/toast_info_*.anim"
    # Find it by glob
    clip_files = list(clip_path.parent.glob(clip_path.name))
    assert len(clip_files) == 1
    with open(clip_files[0]) as f:
        clip = json.load(f)

    curve = next(o for o in clip if o.get("__type__") == "cc.animation.RealCurve")
    times = curve["_times"]
    values = [v["value"] for v in curve["_values"]]
    assert len(times) == 4
    assert times[0] == 0.0
    assert times[1] == pytest.approx(0.25)  # fade-in end
    assert times[2] == pytest.approx(1.75)  # fade-out start (duration - 0.25)
    assert times[3] == pytest.approx(2.0)
    assert values == [0, 255, 255, 0]


def test_toast_variant_info_uses_surface_bg(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    res = sb.add_toast(scene, info["canvas_node_id"], "ok", variant="info")
    sprite = _component_on(scene, res["toast_node_id"], "cc.Sprite")
    # dark_game.surface = #1e293b
    assert (sprite["_color"]["r"], sprite["_color"]["g"],
            sprite["_color"]["b"]) == (0x1e, 0x29, 0x3b)


def test_toast_danger_variant_uses_danger_bg_and_contrast_text(tmp_path: Path):
    """Danger toast needs red bg + bg-colored (near-black/white) text so
    the message reads against the saturated background."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    res = sb.add_toast(scene, info["canvas_node_id"],
                       "Invalid input", variant="danger")
    bg = _component_on(scene, res["toast_node_id"], "cc.Sprite")
    assert (bg["_color"]["r"], bg["_color"]["g"],
            bg["_color"]["b"]) == (0xef, 0x44, 0x44)  # dark_game.danger

    label = _component_on(scene, res["label_node_id"], "cc.Label")
    # Label uses "bg" color preset when variant is colored — dark_game.bg = #0f172a
    assert (label["_color"]["r"], label["_color"]["g"],
            label["_color"]["b"]) == (0x0f, 0x17, 0x2a)


def test_toast_rejects_too_short_duration(tmp_path: Path):
    """< 0.6s leaves no time for the user to read the message — fail
    loudly instead of producing a toast that flashes and vanishes."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    with pytest.raises(ValueError, match=">=.*0.6"):
        sb.add_toast(scene, info["canvas_node_id"], "x", duration=0.3)


def test_toast_rejects_bad_variant(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    with pytest.raises(ValueError, match="variant"):
        sb.add_toast(scene, info["canvas_node_id"], "x", variant="purple")


def test_toast_starts_invisible(tmp_path: Path):
    """UIOpacity=0 initial prevents first-frame flash at full opacity
    before the clip's first keyframe lands."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_toast(scene, info["canvas_node_id"], "x")
    opacity = _component_on(scene, res["toast_node_id"], "cc.UIOpacity")
    # UIOpacity.opacity → _opacity backing field (protected).
    assert opacity["_opacity"] == 0


def test_toast_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    sb.add_toast(scene, info["canvas_node_id"], "Hi", variant="success")
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ================================================ #
# 2. add_loading_spinner
# ================================================ #

def test_spinner_without_sprite_has_text_only(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_loading_spinner(scene, info["canvas_node_id"],
                                 text="Please wait")
    assert res["icon_node_id"] is None
    assert res["rotation_component_id"] is None
    assert res["label_node_id"] is not None
    label = _component_on(scene, res["label_node_id"], "cc.Label")
    assert label["_string"] == "Please wait"


def test_spinner_with_sprite_creates_rotation_clip(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_loading_spinner(scene, info["canvas_node_id"],
                                 sprite_frame_uuid="fake-spinner@f9941",
                                 text="Loading...",
                                 rotation_period=0.8)
    assert res["icon_node_id"] is not None
    assert res["rotation_component_id"] is not None
    # Icon has the sprite we passed
    sprite = _component_on(scene, res["icon_node_id"], "cc.Sprite")
    sf = sprite.get("_spriteFrame") or {}
    assert sf.get("__uuid__") == "fake-spinner@f9941"

    # Rotation clip goes 0 → -360 and loops
    anim_cmp = _component_on(scene, res["icon_node_id"], "cc.Animation")
    assert anim_cmp is not None
    clips = list((proj / "assets/animations").glob("spinner_rot_*.anim"))
    assert len(clips) == 1
    with open(clips[0]) as f:
        clip = json.load(f)
    assert clip[0]["wrapMode"] == 4  # Loop
    assert clip[0]["_duration"] == pytest.approx(0.8)
    curve = next(o for o in clip if o.get("__type__") == "cc.animation.RealCurve")
    values = [v["value"] for v in curve["_values"]]
    assert values == [0, -360]


def test_spinner_no_text_no_label(tmp_path: Path):
    """Passing text=None produces a pure icon spinner."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_loading_spinner(scene, info["canvas_node_id"],
                                 sprite_frame_uuid="fake@f9941", text=None)
    assert res["label_node_id"] is None


def test_spinner_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    sb.add_loading_spinner(scene, info["canvas_node_id"])
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ================================================ #
# 3. derive_theme_from_seed
# ================================================ #

def test_derive_theme_dark_mode_produces_low_luminance_bg(tmp_path: Path):
    """A dark-mode theme must have bg that's visibly dark (L < 0.15)."""
    palette = tok.derive_theme_from_seed("#6366f1", mode="dark")
    bg = palette["color"]["bg"]
    _, _, L = tok._hex_to_hsl(bg)
    assert L < 0.15, f"dark bg L={L} too bright"
    # Text should be light so it reads on dark bg
    _, _, text_L = tok._hex_to_hsl(palette["color"]["text"])
    assert text_L > 0.85


def test_derive_theme_light_mode_produces_high_luminance_bg():
    palette = tok.derive_theme_from_seed("#2563eb", mode="light")
    _, _, bg_L = tok._hex_to_hsl(palette["color"]["bg"])
    assert bg_L > 0.95
    _, _, text_L = tok._hex_to_hsl(palette["color"]["text"])
    assert text_L < 0.15


def test_derive_theme_secondary_is_complementary_hue():
    """Secondary hue should be ~180° off from primary (mod 360)."""
    palette = tok.derive_theme_from_seed("#6366f1", mode="dark")
    h_primary, _, _ = tok._hex_to_hsl("#6366f1")
    h_secondary, _, _ = tok._hex_to_hsl(palette["color"]["secondary"])
    # Normalize the positive wraparound then measure distance from the
    # ideal 180° gap. Small tolerance for RGB-int quantization.
    raw_diff = (h_secondary - h_primary) % 360
    assert abs(raw_diff - 180) < 5, (
        f"secondary hue {h_secondary} not complementary to primary {h_primary}")


def test_derive_theme_keeps_semantic_colors_fixed():
    """success/warn/danger don't drift per-brand — severity > brand."""
    p1 = tok.derive_theme_from_seed("#6366f1", mode="dark")
    p2 = tok.derive_theme_from_seed("#ff0000", mode="dark")
    for name in ("success", "warn", "danger"):
        assert p1["color"][name] == p2["color"][name], (
            f"{name} must not depend on seed; got different values across seeds")


def test_derive_theme_primary_is_seed_verbatim():
    palette = tok.derive_theme_from_seed("#6366f1", mode="dark")
    assert palette["color"]["primary"] == "#6366f1"


def test_derive_theme_rejects_bad_mode():
    with pytest.raises(ValueError, match="mode"):
        tok.derive_theme_from_seed("#ffffff", mode="auto")


def test_derive_theme_end_to_end_with_set_ui_theme(tmp_path: Path):
    """Integration: derive → set → get should round-trip the palette."""
    proj = _make_project(tmp_path)
    palette = tok.derive_theme_from_seed("#22d3ee", mode="dark")
    cp.set_ui_theme(str(proj), custom=palette)
    tokens = cp.get_ui_tokens(str(proj))
    assert tokens["source"] == "registry"
    assert tokens["resolved"]["color"]["primary"] == "#22d3ee"
    # Font-size / spacing fell through to dark_game defaults since we
    # only supplied colors in the derived palette
    assert tokens["resolved"]["font_size"]["title"] == 72


def test_derive_theme_colors_all_resolve_via_set(tmp_path: Path):
    """Every standard color preset name must be in the derived palette
    so ``color_preset='border'`` doesn't 404 after set_ui_theme."""
    proj = _make_project(tmp_path)
    palette = tok.derive_theme_from_seed("#6366f1", mode="dark")
    cp.set_ui_theme(str(proj), custom=palette)

    scene = proj / "assets/scenes/x.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    n = sb.add_node(scene, info["canvas_node_id"], "T")

    # Should not raise for any of the 10 preset names
    for color_name in tok.COLOR_NAMES:
        sb.add_label(scene, sb.add_node(scene, n, f"L_{color_name}"),
                     f"test {color_name}", color_preset=color_name)

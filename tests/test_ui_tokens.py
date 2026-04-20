"""Tests for the UI design-token system + preset plumbing through
add_label / add_button / add_sprite / add_richtext + cocos_lint_ui.

The token registry is our own (``settings/v2/packages/ui-tokens.json``)
so these tests need only a project skeleton, no Cocos install.
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


def _scene_in_project(proj: Path) -> tuple[Path, dict]:
    scene = proj / "assets" / "scenes" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    return scene, info


# ========================================= #
# 1. Token registry: set / get / list
# ========================================= #

def test_set_ui_theme_defaults_to_dark_game(tmp_path: Path):
    proj = _make_project(tmp_path)
    res = cp.set_ui_theme(str(proj))
    assert res["theme"] == "dark_game"
    # Every standard preset name must resolve
    for name in tok.COLOR_NAMES:
        assert name in res["resolved"]["color"]
    for name in tok.SIZE_NAMES:
        assert name in res["resolved"]["font_size"]
    for name in tok.SPACING_NAMES:
        assert name in res["resolved"]["spacing"]
    for name in tok.RADIUS_NAMES:
        assert name in res["resolved"]["radius"]


def test_set_ui_theme_accepts_all_builtins(tmp_path: Path):
    for theme_name in tok.BUILTIN_THEMES:
        proj = _make_project(tmp_path / theme_name)
        res = cp.set_ui_theme(str(proj), theme=theme_name)
        assert res["theme"] == theme_name
        assert "primary" in res["resolved"]["color"]


def test_set_ui_theme_rejects_unknown_builtin(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError, match="unknown theme"):
        cp.set_ui_theme(str(proj), theme="bogus")


def test_custom_theme_merges_with_dark_game_defaults(tmp_path: Path):
    """A custom theme that only overrides a few names should still
    have every standard preset resolve — missing ones fall through to
    dark_game defaults so ``color_preset='border'`` never 404s."""
    proj = _make_project(tmp_path)
    res = cp.set_ui_theme(str(proj), custom={
        "color": {"primary": "#ff0000"},
        "font_size": {"title": 100},
    })
    # Overrides applied
    assert res["resolved"]["color"]["primary"] == "#ff0000"
    assert res["resolved"]["font_size"]["title"] == 100
    # Dark-game defaults fill the gaps
    assert res["resolved"]["color"]["border"] == "#334155"  # from dark_game
    assert res["resolved"]["font_size"]["body"] == 32


def test_custom_theme_rejects_bad_shape(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError, match="hex string"):
        cp.set_ui_theme(str(proj), custom={"color": {"primary": 0x6366f1}})
    with pytest.raises(ValueError, match="number"):
        cp.set_ui_theme(str(proj), custom={"font_size": {"title": "big"}})


def test_get_ui_tokens_falls_back_when_no_registry(tmp_path: Path):
    """Un-themed project → get should still return a full theme,
    sourced from the bundled dark_game defaults."""
    proj = _make_project(tmp_path)
    res = cp.get_ui_tokens(str(proj))
    assert res["source"] == "fallback"
    assert res["theme"] == "dark_game"
    assert res["resolved"]["color"]["primary"] == "#6366f1"


def test_get_ui_tokens_registry_wins(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.set_ui_theme(str(proj), theme="neon_arcade")
    res = cp.get_ui_tokens(str(proj))
    assert res["source"] == "registry"
    assert res["theme"] == "neon_arcade"
    assert res["resolved"]["color"]["primary"] == "#22d3ee"


def test_list_builtin_themes_has_all_five(tmp_path: Path):
    res = tok.list_builtin_themes()
    assert res["default"] == "dark_game"
    assert set(res["themes"].keys()) == {
        "dark_game", "light_minimal", "neon_arcade", "pastel_cozy", "corporate",
    }


# ========================================= #
# 2. hex_to_rgba
# ========================================= #

def test_hex_to_rgba_six_digit():
    assert tok.hex_to_rgba("#6366f1") == (99, 102, 241, 255)
    # Without leading '#' also works
    assert tok.hex_to_rgba("6366f1") == (99, 102, 241, 255)


def test_hex_to_rgba_three_digit_shorthand():
    # #f0a → #ff00aa
    assert tok.hex_to_rgba("#f0a") == (0xff, 0x00, 0xaa, 255)


def test_hex_to_rgba_eight_digit_includes_alpha():
    assert tok.hex_to_rgba("#6366f180") == (99, 102, 241, 128)


def test_hex_to_rgba_alpha_override():
    r, g, b, a = tok.hex_to_rgba("#ffffff", alpha=200)
    assert (r, g, b, a) == (255, 255, 255, 200)


def test_hex_to_rgba_bad_input_raises():
    with pytest.raises(ValueError, match="bad hex"):
        tok.hex_to_rgba("red")
    with pytest.raises(ValueError):
        tok.hex_to_rgba("#12345")


# ========================================= #
# 3. Preset plumbing into UI building functions
# ========================================= #

def test_add_label_color_preset_resolves_to_theme_color(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.set_ui_theme(str(proj), theme="dark_game")
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Title")
    cid = sb.add_label(str(scene), n, "Main Menu",
                       color_preset="primary", size_preset="title")
    obj = sb.get_object(scene, cid)
    # dark_game primary = #6366f1 = rgb(99, 102, 241)
    assert obj["_color"]["r"] == 99
    assert obj["_color"]["g"] == 102
    assert obj["_color"]["b"] == 241
    # title in dark_game = 72
    assert obj["_fontSize"] == 72


def test_add_label_explicit_args_win_when_no_preset(tmp_path: Path):
    """Backward-compat: old code path with explicit RGBA + font_size
    must continue to work identically."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Legacy")
    cid = sb.add_label(str(scene), n, "Hi", font_size=36,
                       color=(200, 100, 50, 255))
    obj = sb.get_object(scene, cid)
    assert obj["_color"]["r"] == 200
    assert obj["_fontSize"] == 36


def test_add_label_presets_fall_back_to_dark_game_without_theme(tmp_path: Path):
    """No registry yet → presets still resolve (dark_game default)."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Title")
    cid = sb.add_label(str(scene), n, "x",
                       color_preset="danger", size_preset="caption")
    obj = sb.get_object(scene, cid)
    # danger in dark_game = #ef4444
    assert obj["_color"]["r"] == 0xef
    assert obj["_fontSize"] == 24  # caption in dark_game


def test_add_label_unknown_preset_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="unknown color preset"):
        sb.add_label(str(scene), n, "x", color_preset="not_a_real_name")


def test_add_sprite_color_preset(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.set_ui_theme(str(proj), theme="light_minimal")
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Panel")
    cid = sb.add_sprite(str(scene), n, color_preset="surface")
    obj = sb.get_object(scene, cid)
    # light_minimal.surface = #f8fafc
    assert obj["_color"]["r"] == 0xf8


def test_add_button_color_preset_auto_derives_states(tmp_path: Path):
    """The motivating win: one color_preset= gives four visually-coherent
    button states. AI doesn't have to pick four RGBA quadruples that
    happen to look good together."""
    proj = _make_project(tmp_path)
    cp.set_ui_theme(str(proj), theme="dark_game")
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "StartBtn")
    cid = sb.add_button(str(scene), n, color_preset="primary")
    obj = sb.get_object(scene, cid)

    normal = obj["_N$normalColor"]
    hover = obj["_N$hoverColor"]
    pressed = obj["pressedColor"]
    disabled = obj["_N$disabledColor"]

    # Normal = primary = #6366f1
    assert (normal["r"], normal["g"], normal["b"]) == (99, 102, 241)
    # Hover is lighter (~1.12×), pressed is darker (~0.78×)
    assert hover["r"] > normal["r"] and hover["g"] > normal["g"]
    assert pressed["r"] < normal["r"] and pressed["b"] < normal["b"]
    # Disabled is a neutral gray (r==g==b)
    assert disabled["r"] == disabled["g"] == disabled["b"]


def test_add_button_explicit_hover_wins_over_derivation(tmp_path: Path):
    """If the caller passes color_preset AND an explicit hover_color
    different from the legacy default, respect the explicit one."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Btn")
    cid = sb.add_button(str(scene), n,
                        color_preset="primary",
                        hover_color=(200, 0, 0, 255))
    obj = sb.get_object(scene, cid)
    h = obj["_N$hoverColor"]
    assert (h["r"], h["g"], h["b"]) == (200, 0, 0)


def test_add_richtext_size_preset(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.set_ui_theme(str(proj), theme="pastel_cozy")
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    cid = sb.add_richtext(str(scene), n, size_preset="heading")
    obj = sb.get_object(scene, cid)
    # pastel_cozy.font_size.heading = 44
    assert obj["fontSize"] == 44
    # line_height auto-set to 1.25×
    assert obj["_lineHeight"] == int(44 * 1.25)


# ========================================= #
# 4. cocos_lint_ui
# ========================================= #

def test_lint_flags_button_below_touch_target(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "TinyBtn")
    sb.add_uitransform(str(scene), n, 20, 20)  # below 44×44
    sb.add_button(str(scene), n)

    report = sb.lint_ui(scene)
    assert report["ok"] is False
    rules = {w["rule"] for w in report["warnings"]}
    assert "button_touch_target" in rules
    # Message should name the actual dimensions to guide the fix
    msg = next(w["message"] for w in report["warnings"]
               if w["rule"] == "button_touch_target")
    assert "20" in msg


def test_lint_passes_for_appropriately_sized_button(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "BigBtn")
    sb.add_uitransform(str(scene), n, 200, 60)
    sb.add_button(str(scene), n)

    report = sb.lint_ui(scene)
    btn_warnings = [w for w in report["warnings"] if w["rule"] == "button_touch_target"]
    assert btn_warnings == []


def test_lint_flags_narrow_label_with_overflow_none(tmp_path: Path):
    """Long text + no wrap + small UITransform + overflow=NONE is the
    single most common "text gets cut off" bug in AI-built UIs."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "ClippedTitle")
    sb.add_uitransform(str(scene), n, 100, 40)
    sb.add_label(str(scene), n,
                 "This is a very long title that will clip",
                 overflow=0, enable_wrap=False)

    report = sb.lint_ui(scene)
    assert any(w["rule"] == "label_overflow_risk" for w in report["warnings"])


def test_lint_layer_mismatch_warns(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    # Node on the WRONG layer (Default=1073741824 instead of UI_2D)
    n = sb.add_node(scene, info["canvas_node_id"], "WrongLayer",
                    layer=1073741824)
    sb.add_uitransform(str(scene), n, 100, 100)
    sb.add_sprite(str(scene), n)

    report = sb.lint_ui(scene)
    assert any(w["rule"] == "ui_layer_mismatch" for w in report["warnings"])


def test_lint_ok_on_a_healthy_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    btn = sb.add_node(scene, info["canvas_node_id"], "OkBtn")
    sb.add_uitransform(str(scene), btn, 200, 60)
    sb.add_button(str(scene), btn)
    label = sb.add_node(scene, info["canvas_node_id"], "OkLabel")
    sb.add_uitransform(str(scene), label, 400, 80)
    sb.add_label(str(scene), label, "Title", overflow=2)  # SHRINK

    report = sb.lint_ui(scene)
    assert report["ok"] is True, f"unexpected warnings: {report['warnings']}"

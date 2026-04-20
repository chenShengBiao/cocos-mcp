"""Tests for the fifth UI/UX batch:

* ``add_card_grid`` — level select / shop / character picker pattern.
* ``lint_ui`` gains two rules:
    - ``contrast_too_low`` (WCAG AA text-on-bg contrast)
    - ``overlapping_buttons`` (same-parent Button UITransforms intersect)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp
from cocos import scene_builder as sb
from cocos.scene_builder import ui_lint


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
# 1. add_card_grid
# ================================================ #

def test_card_grid_returns_one_entry_per_card(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_card_grid(scene, info["canvas_node_id"], cards=[
        {"title": f"L{i}", "subtitle": f"Stage {i}"} for i in range(6)
    ], columns=3)
    assert len(res["cards"]) == 6
    # All cards have title nodes; subtitle present because we supplied it
    for c in res["cards"]:
        assert c["title_node_id"] is not None
        assert c["subtitle_node_id"] is not None


def test_card_grid_layout_math_6_cards_2_rows(tmp_path: Path):
    """6 cards in 3 columns should produce 2 rows, with cards horizontally
    centered on the grid origin."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_card_grid(scene, info["canvas_node_id"],
                           cards=[{"title": f"L{i}"} for i in range(6)],
                           columns=3, card_width=100, card_height=100, spacing=10)

    with open(scene) as f:
        data = json.load(f)

    card_xs = []
    card_ys = []
    for c in res["cards"]:
        pos = data[c["node_id"]]["_lpos"]
        card_xs.append(pos["x"])
        card_ys.append(pos["y"])

    # 3 distinct columns × 2 rows
    assert len(set(card_xs)) == 3
    assert len(set(card_ys)) == 2
    # First row y > second row y (y grows upward)
    assert card_ys[0] > card_ys[3]
    # Grid is centered on x=0: middle column should be at x=0
    assert 0 in card_xs


def test_card_grid_rejects_empty_and_zero_columns(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    with pytest.raises(ValueError, match="non-empty"):
        sb.add_card_grid(scene, info["canvas_node_id"], cards=[])
    with pytest.raises(ValueError, match="columns"):
        sb.add_card_grid(scene, info["canvas_node_id"],
                         cards=[{"title": "x"}], columns=0)


def test_card_grid_primary_variant_flips_text_color(tmp_path: Path):
    """A primary-variant card has bg=primary color so the title must use
    color_preset='bg' to stay readable. Test the resulting Label color."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    res = sb.add_card_grid(scene, info["canvas_node_id"],
                           cards=[{"title": "Featured", "variant": "primary"}])
    title_label = _component_on(scene, res["cards"][0]["title_node_id"], "cc.Label")
    # dark_game.bg = #0f172a → rgb(15, 23, 42)
    assert (title_label["_color"]["r"], title_label["_color"]["g"],
            title_label["_color"]["b"]) == (15, 23, 42)


def test_card_grid_each_card_is_tappable(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_card_grid(scene, info["canvas_node_id"],
                           cards=[{"title": f"C{i}"} for i in range(3)])
    for c in res["cards"]:
        btn = _component_on(scene, c["node_id"], "cc.Button")
        assert btn is not None


def test_card_grid_icon_only_when_uuid_given(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = sb.add_card_grid(scene, info["canvas_node_id"], cards=[
        {"title": "NoIcon"},
        {"title": "HasIcon", "icon_sprite_frame_uuid": "fake@f9941"},
    ])
    assert res["cards"][0]["icon_node_id"] is None
    assert res["cards"][1]["icon_node_id"] is not None


def test_card_grid_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    sb.add_card_grid(scene, info["canvas_node_id"], cards=[
        {"title": "L1", "subtitle": "Tutorial"},
        {"title": "L2", "variant": "primary"},
        {"title": "L3"},
    ])
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ================================================ #
# 2. Lint: contrast_too_low
# ================================================ #

def test_lint_flags_low_contrast_label_on_dark_bg(tmp_path: Path):
    """Very dark gray text on near-black bg — fails WCAG AA."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    panel = sb.add_node(scene, info["canvas_node_id"], "Panel")
    sb.add_uitransform(scene, panel, 400, 200)
    sb.add_sprite(scene, panel, color=(20, 20, 20, 255))   # near black
    label = sb.add_node(scene, panel, "FaintText")
    sb.add_uitransform(scene, label, 300, 40)
    # Text ~#333 — only slightly brighter than bg, ratio << 4.5
    sb.add_label(scene, label, "Almost invisible", color=(60, 60, 60, 255))

    report = sb.lint_ui(scene)
    assert any(w["rule"] == "contrast_too_low" for w in report["warnings"])


def test_lint_passes_high_contrast_white_on_black(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    panel = sb.add_node(scene, info["canvas_node_id"], "Panel")
    sb.add_uitransform(scene, panel, 400, 200)
    sb.add_sprite(scene, panel, color=(0, 0, 0, 255))
    label = sb.add_node(scene, panel, "ClearText")
    sb.add_uitransform(scene, label, 300, 40)
    sb.add_label(scene, label, "Readable", color=(255, 255, 255, 255))

    report = sb.lint_ui(scene)
    contrast_warnings = [w for w in report["warnings"]
                         if w["rule"] == "contrast_too_low"]
    assert contrast_warnings == []


def test_lint_contrast_skips_labels_without_bg_sprite(tmp_path: Path):
    """Floating label with no ancestor Sprite — we can't tell what's
    behind it at runtime, so skip rather than false-positive."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    label = sb.add_node(scene, info["canvas_node_id"], "Floating")
    sb.add_uitransform(scene, label, 200, 40)
    sb.add_label(scene, label, "hmm", color=(128, 128, 128, 255))

    report = sb.lint_ui(scene)
    contrast_warnings = [w for w in report["warnings"]
                         if w["rule"] == "contrast_too_low"]
    assert contrast_warnings == []


def test_lint_contrast_walks_up_to_ancestor_sprite(tmp_path: Path):
    """Label → Layout → Card panel. The nearest Sprite is on the card,
    3 levels up — lint should still find it."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    card = sb.add_node(scene, info["canvas_node_id"], "Card")
    sb.add_uitransform(scene, card, 300, 300)
    sb.add_sprite(scene, card, color=(255, 255, 255, 255))  # white
    layout = sb.add_node(scene, card, "Inner")
    sb.add_uitransform(scene, layout, 280, 280)
    label = sb.add_node(scene, layout, "LabelOnCard")
    sb.add_uitransform(scene, label, 260, 40)
    # White text on a white card — ratio ~1:1, guaranteed to fail
    sb.add_label(scene, label, "invisible", color=(255, 255, 255, 255))

    report = sb.lint_ui(scene)
    assert any(w["rule"] == "contrast_too_low" for w in report["warnings"])


# ================================================ #
# 3. Lint: overlapping_buttons
# ================================================ #

def test_lint_flags_two_buttons_stacked_at_same_position(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    # Two buttons with identical UITransform + _lpos
    b1 = sb.add_node(scene, info["canvas_node_id"], "BtnA", lpos=(0, 0, 0))
    sb.add_uitransform(scene, b1, 200, 80)
    sb.add_button(scene, b1)
    b2 = sb.add_node(scene, info["canvas_node_id"], "BtnB", lpos=(0, 0, 0))
    sb.add_uitransform(scene, b2, 200, 80)
    sb.add_button(scene, b2)

    report = sb.lint_ui(scene)
    warnings = [w for w in report["warnings"] if w["rule"] == "overlapping_buttons"]
    assert len(warnings) >= 1
    # Message should name BOTH buttons
    msg = warnings[0]["message"]
    assert "BtnA" in msg and "BtnB" in msg


def test_lint_allows_tangent_buttons(tmp_path: Path):
    """Buttons touching edge-to-edge (no area overlap) are fine."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    b1 = sb.add_node(scene, info["canvas_node_id"], "Left", lpos=(-110, 0, 0))
    sb.add_uitransform(scene, b1, 200, 80)
    sb.add_button(scene, b1)
    b2 = sb.add_node(scene, info["canvas_node_id"], "Right", lpos=(110, 0, 0))
    sb.add_uitransform(scene, b2, 200, 80)
    sb.add_button(scene, b2)

    report = sb.lint_ui(scene)
    assert not any(w["rule"] == "overlapping_buttons" for w in report["warnings"])


def test_lint_ignores_cross_parent_button_overlap(tmp_path: Path):
    """A dialog button on top of a HUD button is by design (modal covers
    underlying UI). Overlap lint must not false-positive on these."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    # Parent A
    panel_a = sb.add_node(scene, info["canvas_node_id"], "PanelA")
    sb.add_uitransform(scene, panel_a, 400, 400)
    btn_a = sb.add_node(scene, panel_a, "BtnOnA", lpos=(0, 0, 0))
    sb.add_uitransform(scene, btn_a, 200, 80)
    sb.add_button(scene, btn_a)
    # Parent B overlaid
    panel_b = sb.add_node(scene, info["canvas_node_id"], "PanelB")
    sb.add_uitransform(scene, panel_b, 400, 400)
    btn_b = sb.add_node(scene, panel_b, "BtnOnB", lpos=(0, 0, 0))
    sb.add_uitransform(scene, btn_b, 200, 80)
    sb.add_button(scene, btn_b)

    report = sb.lint_ui(scene)
    assert not any(w["rule"] == "overlapping_buttons" for w in report["warnings"])


def test_lint_small_overlap_below_threshold_ok(tmp_path: Path):
    """A 10% overlap shouldn't flag — threshold is 25%."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    # 200×100 buttons offset by 180 in X → 20px overlap = 2000px² of 20000 = 10%
    b1 = sb.add_node(scene, info["canvas_node_id"], "L", lpos=(0, 0, 0))
    sb.add_uitransform(scene, b1, 200, 100)
    sb.add_button(scene, b1)
    b2 = sb.add_node(scene, info["canvas_node_id"], "R", lpos=(180, 0, 0))
    sb.add_uitransform(scene, b2, 200, 100)
    sb.add_button(scene, b2)

    report = sb.lint_ui(scene)
    assert not any(w["rule"] == "overlapping_buttons" for w in report["warnings"])


def test_lint_default_menu_passes_all_rules(tmp_path: Path):
    """A fresh main menu built via cocos_add_main_menu should lint clean —
    regression guard that our own composites don't violate our own rules."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    sb.add_main_menu(scene, info["canvas_node_id"], title="Test")

    report = sb.lint_ui(scene)
    assert report["ok"], f"main_menu composite fails lint: {report['warnings']}"


# ================================================ #
# 4. Low-level helpers (WCAG luminance math)
# ================================================ #

def test_contrast_ratio_pure_black_white():
    """Canonical sanity check — black vs white is 21:1."""
    black = {"r": 0, "g": 0, "b": 0, "a": 255}
    white = {"r": 255, "g": 255, "b": 255, "a": 255}
    assert ui_lint._contrast_ratio(black, white) == pytest.approx(21.0, abs=0.1)
    # Contrast is symmetric
    assert ui_lint._contrast_ratio(white, black) == pytest.approx(21.0, abs=0.1)


def test_contrast_ratio_same_color_is_1():
    c = {"r": 128, "g": 128, "b": 128, "a": 255}
    assert ui_lint._contrast_ratio(c, c) == pytest.approx(1.0, abs=0.01)

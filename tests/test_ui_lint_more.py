"""Three additional lint rules (sixth UI/UX batch):

* ``huge_font_small_box`` — Label with font_size that won't fit its UITransform.
* ``many_buttons_no_layout`` — parent with 6+ button children but no cc.Layout.
* ``nested_mask_perf`` — cc.Mask whose ancestor chain already has another Mask.
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


def _scene(proj: Path, theme: str = "dark_game") -> tuple[Path, dict]:
    cp.set_ui_theme(str(proj), theme=theme)
    path = proj / "assets" / "scenes" / "main.scene"
    path.parent.mkdir(parents=True)
    info = sb.create_empty_scene(path)
    return path, info


def _warnings_of_rule(report: dict, rule: str) -> list[dict]:
    return [w for w in report["warnings"] if w["rule"] == rule]


# ================================================ #
# huge_font_small_box
# ================================================ #

def test_huge_font_small_box_flags_label_too_tall_for_box(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Tiny")
    # 64px font in a 30px-tall box — ascenders/descenders will be
    # clipped even before line-height concerns.
    sb.add_uitransform(scene, n, 400, 30)
    sb.add_label(scene, n, "Big text", font_size=64)

    report = sb.lint_ui(scene)
    warnings = _warnings_of_rule(report, "huge_font_small_box")
    assert len(warnings) == 1
    msg = warnings[0]["message"]
    # Message should name the font_size AND the minimum box height
    assert "font_size=64" in msg
    assert "30px" in msg


def test_huge_font_small_box_passes_when_box_roomy_enough(tmp_path: Path):
    """1.2× ratio is the minimum — exactly at threshold should pass."""
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "OK")
    sb.add_uitransform(scene, n, 400, 60)  # 60 >= 40 * 1.2 = 48
    sb.add_label(scene, n, "ok", font_size=40)

    report = sb.lint_ui(scene)
    assert _warnings_of_rule(report, "huge_font_small_box") == []


def test_huge_font_small_box_ignores_zero_height_or_missing_size(tmp_path: Path):
    """Defensive: 0-height UITransform or missing font_size shouldn't
    crash or false-flag — just silently skip."""
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Odd")
    sb.add_uitransform(scene, n, 400, 0)  # degenerate size
    sb.add_label(scene, n, "x", font_size=32)

    # Must not raise
    report = sb.lint_ui(scene)
    # 0 height is technically less than any positive ratio * font_size,
    # but we guard against it to avoid noise from degenerate/hidden nodes.
    assert _warnings_of_rule(report, "huge_font_small_box") == []


# ================================================ #
# many_buttons_no_layout
# ================================================ #

def test_many_buttons_no_layout_flags_panel_with_8_buttons(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    # Direct panel child with 8 buttons, no Layout
    panel = sb.add_node(scene, info["canvas_node_id"], "HandPositioned")
    sb.add_uitransform(scene, panel, 800, 600)
    for i in range(8):
        btn = sb.add_node(scene, panel, f"Btn_{i}",
                          lpos=(0, 250 - i * 70, 0))
        sb.add_uitransform(scene, btn, 200, 60)
        sb.add_button(scene, btn)

    report = sb.lint_ui(scene)
    warnings = _warnings_of_rule(report, "many_buttons_no_layout")
    assert len(warnings) == 1
    assert warnings[0]["node_name"] == "HandPositioned"
    assert "8 direct button" in warnings[0]["message"]


def test_many_buttons_no_layout_passes_when_layout_present(tmp_path: Path):
    """Parent with cc.Layout arranges children at runtime — no warning."""
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    panel = sb.add_node(scene, info["canvas_node_id"], "Stack")
    sb.add_uitransform(scene, panel, 400, 800)
    sb.add_layout(scene, panel, layout_type=2, spacing_y=10)
    for i in range(8):
        btn = sb.add_node(scene, panel, f"Btn_{i}")
        sb.add_uitransform(scene, btn, 200, 60)
        sb.add_button(scene, btn)

    report = sb.lint_ui(scene)
    assert _warnings_of_rule(report, "many_buttons_no_layout") == []


def test_many_buttons_no_layout_threshold_is_6(tmp_path: Path):
    """5 buttons shouldn't flag; 6 should."""
    for count, should_flag in [(5, False), (6, True)]:
        proj = _make_project(tmp_path / f"n{count}")
        scene, info = _scene(proj)
        panel = sb.add_node(scene, info["canvas_node_id"], f"P{count}")
        sb.add_uitransform(scene, panel, 800, 600)
        for i in range(count):
            btn = sb.add_node(scene, panel, f"Btn_{i}",
                              lpos=(0, 200 - i * 70, 0))
            sb.add_uitransform(scene, btn, 200, 60)
            sb.add_button(scene, btn)

        report = sb.lint_ui(scene)
        warnings = _warnings_of_rule(report, "many_buttons_no_layout")
        if should_flag:
            assert len(warnings) == 1, f"expected flag on {count} buttons"
        else:
            assert warnings == [], f"unexpected flag on {count} buttons"


# ================================================ #
# nested_mask_perf
# ================================================ #

def test_nested_mask_flags_inner_mask(tmp_path: Path):
    """A Mask inside another Mask is the canonical "you probably didn't
    mean this" situation — outer already clips the draw region."""
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    outer = sb.add_node(scene, info["canvas_node_id"], "OuterMask")
    sb.add_uitransform(scene, outer, 400, 400)
    sb.add_mask(scene, outer)

    inner_parent = sb.add_node(scene, outer, "Content")
    sb.add_uitransform(scene, inner_parent, 300, 300)
    inner = sb.add_node(scene, inner_parent, "InnerMask")
    sb.add_uitransform(scene, inner, 200, 200)
    sb.add_mask(scene, inner)

    report = sb.lint_ui(scene)
    warnings = _warnings_of_rule(report, "nested_mask_perf")
    assert len(warnings) == 1
    assert warnings[0]["node_name"] == "InnerMask"
    assert "OuterMask" in warnings[0]["message"]


def test_nested_mask_passes_with_sibling_masks(tmp_path: Path):
    """Two masks that don't ancestor each other are fine — they clip
    disjoint regions, no compounding cost."""
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    m1 = sb.add_node(scene, info["canvas_node_id"], "M1")
    sb.add_uitransform(scene, m1, 200, 200)
    sb.add_mask(scene, m1)

    m2 = sb.add_node(scene, info["canvas_node_id"], "M2")
    sb.add_uitransform(scene, m2, 200, 200)
    sb.add_mask(scene, m2)

    report = sb.lint_ui(scene)
    assert _warnings_of_rule(report, "nested_mask_perf") == []


def test_nested_mask_passes_with_single_mask(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    m = sb.add_node(scene, info["canvas_node_id"], "SingleMask")
    sb.add_uitransform(scene, m, 200, 200)
    sb.add_mask(scene, m)

    report = sb.lint_ui(scene)
    assert _warnings_of_rule(report, "nested_mask_perf") == []


# ================================================ #
# Composites still lint clean after adding rules
# ================================================ #

def test_main_menu_lints_clean_with_all_rules(tmp_path: Path):
    """Regression: expanding lint shouldn't make our own composites fail."""
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    sb.add_main_menu(scene, info["canvas_node_id"], title="Test")

    report = sb.lint_ui(scene)
    assert report["ok"], report["warnings"]


def test_dialog_modal_lints_clean(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    sb.add_dialog_modal(scene, info["canvas_node_id"],
                        title="Over", body="Score: 1200",
                        buttons=[{"text": "Retry", "variant": "primary"},
                                 {"text": "Menu", "variant": "ghost"}])
    report = sb.lint_ui(scene)
    assert report["ok"], report["warnings"]


def test_card_grid_lints_clean(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene(proj)
    sb.add_card_grid(scene, info["canvas_node_id"], cards=[
        {"title": f"L{i}", "subtitle": f"Stage {i}"} for i in range(6)
    ])
    report = sb.lint_ui(scene)
    assert report["ok"], report["warnings"]

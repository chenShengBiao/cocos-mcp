"""Tests for ``add_styled_text_block`` — the layered typography composite.

Shape + theme-driven color/size + alignment mapping + the "no-body ⇒
no-divider" rule. We also run the scene through ``lint_ui`` as a
regression guard that the composite doesn't emit a layout that trips
contrast/overlap/clipping rules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp
from cocos import scene_builder as sb
from cocos.scene_builder.styled_text import add_styled_text_block


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


def _component_on(scene_path: Path, node_id: int, type_name: str) -> dict:
    return next(c for c in _components_on_node(scene_path, node_id)
                if c["__type__"] == type_name)


# ======================================== #
# Shape — all pieces + validate
# ======================================== #

def test_all_four_pieces_present(tmp_path: Path):
    """Title + subtitle + body + divider → every id in the return dict
    is non-None, and the scene stays structurally valid."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(
        str(scene), info["canvas_node_id"],
        title="Welcome",
        subtitle="Chapter 1",
        body="A long time ago in a galaxy far, far away.",
        show_divider=True,
    )
    assert set(res.keys()) == {
        "block_node_id", "title_node_id", "subtitle_node_id",
        "divider_node_id", "body_node_id",
    }
    assert res["title_node_id"] is not None
    assert res["subtitle_node_id"] is not None
    assert res["divider_node_id"] is not None
    assert res["body_node_id"] is not None

    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


def test_title_only_skips_subtitle_divider_body(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="Just a heading")
    assert res["title_node_id"] is not None
    assert res["subtitle_node_id"] is None
    assert res["divider_node_id"] is None
    assert res["body_node_id"] is None


# ======================================== #
# Divider-suppression rules
# ======================================== #

def test_subtitle_only_no_body_suppresses_divider(tmp_path: Path):
    """Subtitle present but no body → divider is skipped (nothing to
    divide off). body_node_id also None."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="Heading",
                                subtitle="A subtitle, alone",
                                show_divider=True)
    assert res["subtitle_node_id"] is not None
    assert res["body_node_id"] is None
    assert res["divider_node_id"] is None


def test_body_with_show_divider_false_skips_divider(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="T", body="some body",
                                show_divider=False)
    assert res["body_node_id"] is not None
    assert res["divider_node_id"] is None


def test_divider_appears_only_with_body_and_show_divider(tmp_path: Path):
    """Three combinations: (body=None, show_divider=True) → no divider;
    (body=X, show_divider=False) → no divider;
    (body=X, show_divider=True) → divider."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    r1 = add_styled_text_block(str(scene), info["canvas_node_id"],
                               title="T1", show_divider=True)
    assert r1["divider_node_id"] is None

    r2 = add_styled_text_block(str(scene), info["canvas_node_id"],
                               title="T2", body="b", show_divider=False)
    assert r2["divider_node_id"] is None

    r3 = add_styled_text_block(str(scene), info["canvas_node_id"],
                               title="T3", body="b", show_divider=True)
    assert r3["divider_node_id"] is not None


# ======================================== #
# Theme-driven color + size
# ======================================== #

def test_title_uses_dark_game_text_color_and_heading_size(tmp_path: Path):
    """With dark_game theme: text = #e2e8f0 = rgb(226, 232, 240),
    heading = 48. Both must come through from the theme, not be
    hardcoded in the composite."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="Hello")

    title_label = _component_on(scene, res["title_node_id"], "cc.Label")
    c = title_label["_color"]
    assert (c["r"], c["g"], c["b"]) == (226, 232, 240)
    assert title_label["_fontSize"] == 48


def test_subtitle_uses_text_dim_color(tmp_path: Path):
    """Subtitle uses text_dim so it reads as supporting metadata.
    dark_game.text_dim = #94a3b8 = rgb(148, 163, 184)."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="T", subtitle="S")
    sub_label = _component_on(scene, res["subtitle_node_id"], "cc.Label")
    c = sub_label["_color"]
    assert (c["r"], c["g"], c["b"]) == (148, 163, 184)
    # body-size = 32 on dark_game
    assert sub_label["_fontSize"] == 32


def test_divider_uses_border_preset_color(tmp_path: Path):
    """Divider sprite's color comes from the border preset —
    dark_game.border = #334155 = rgb(51, 65, 85)."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="T", body="B", show_divider=True)
    div_sprite = _component_on(scene, res["divider_node_id"], "cc.Sprite")
    c = div_sprite["_color"]
    assert (c["r"], c["g"], c["b"]) == (51, 65, 85)


def test_body_label_wrap_and_overflow_resize_height(tmp_path: Path):
    """Body gets wrap + RESIZE_HEIGHT so long paragraphs grow rather
    than clip — if either flag regresses, long body text clips silently."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="T", body="A longer body paragraph.")
    body_label = _component_on(scene, res["body_node_id"], "cc.Label")
    assert body_label["_enableWrapText"] is True
    assert body_label["_overflow"] == 3  # RESIZE_HEIGHT


# ======================================== #
# Alignment mapping
# ======================================== #

def test_align_left_maps_to_horizontal_align_zero(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="X", align="left")
    title_label = _component_on(scene, res["title_node_id"], "cc.Label")
    assert title_label["_horizontalAlign"] == 0


def test_align_right_maps_to_horizontal_align_two(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="X", align="right")
    title_label = _component_on(scene, res["title_node_id"], "cc.Label")
    assert title_label["_horizontalAlign"] == 2


def test_align_center_default_is_one(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    res = add_styled_text_block(str(scene), info["canvas_node_id"],
                                title="X")
    title_label = _component_on(scene, res["title_node_id"], "cc.Label")
    assert title_label["_horizontalAlign"] == 1


def test_align_invalid_raises(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    with pytest.raises(ValueError, match="align"):
        add_styled_text_block(str(scene), info["canvas_node_id"],
                              title="X", align="diagonal")


# ======================================== #
# Lint regression guard
# ======================================== #

def test_full_block_passes_ui_lint(tmp_path: Path):
    """Full block on the default theme must not trip contrast_too_low,
    label_overflow_risk, overlapping_buttons, or ui_layer_mismatch —
    if it does the composite is emitting a broken layout."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    add_styled_text_block(str(scene), info["canvas_node_id"],
                          title="Welcome Home",
                          subtitle="Ready to play?",
                          body="Press start when you're ready.")
    report = sb.lint_ui(scene)
    # Surface the specific rule failures in the assertion message so
    # future regressions are easy to triage.
    offending = [w for w in report["warnings"]
                 if w["rule"] in ("contrast_too_low", "label_overflow_risk",
                                  "overlapping_buttons", "ui_layer_mismatch")]
    assert offending == [], offending

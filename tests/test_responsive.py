"""Tests for the declarative responsive-layout helpers.

These helpers wrap ``add_widget`` / ``add_layout`` with English-named
flags so the AI doesn't have to combine bitmask ints from memory. We
assert the resulting serialized components carry exactly the bit
combinations and layout ints the module promises — not the pixel
geometry, which depends on theme spacing and would be brittle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp
from cocos import scene_builder as sb
from cocos.scene_builder import responsive as rsp


# ---------- fixtures (mirroring tests/test_ui_patterns.py) ---------- #

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


def _component_by_type(scene_path: Path, node_id: int, cc_type: str) -> dict:
    for c in _components_on_node(scene_path, node_id):
        if c.get("__type__") == cc_type:
            return c
    raise AssertionError(f"no {cc_type} component found on node {node_id}")


def _raw_component(scene_path: Path, component_id: int) -> dict:
    """Fetch any object by its scene-array index. ``add_widget`` /
    ``add_layout`` return the component's array index, which we use to
    grab the serialized dict directly — no need to walk _components."""
    with open(scene_path) as f:
        data = json.load(f)
    return data[component_id]


# ======================================== #
# make_fullscreen
# ======================================== #

def test_make_fullscreen_attaches_widget(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    node = sb.add_node(scene, info["canvas_node_id"], "Bg")

    cid = rsp.make_fullscreen(scene, node)

    # Returns the Widget component id — valid array index
    assert isinstance(cid, int) and cid > 0
    w = _component_by_type(scene, node, "cc.Widget")
    # Flags are the four edge-pin bits: top(1) + bottom(2) + left(4) + right(8) = 15
    assert w["_alignFlags"] == 15


def test_make_fullscreen_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Bg")
    sb.add_uitransform(scene, n, 100, 100)
    sb.add_sprite(scene, n, color=(50, 50, 50, 255))
    rsp.make_fullscreen(scene, n)
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ======================================== #
# anchor_to_edge
# ======================================== #

@pytest.mark.parametrize("edge,expected_flags,margin_fields", [
    ("top",          1,      ("_top",)),
    ("bottom",       2,      ("_bottom",)),
    ("left",         4,      ("_left",)),
    ("right",        8,      ("_right",)),
    ("top-left",     1 | 4,  ("_top", "_left")),
    ("top-right",    1 | 8,  ("_top", "_right")),
    ("bottom-left",  2 | 4,  ("_bottom", "_left")),
    ("bottom-right", 2 | 8,  ("_bottom", "_right")),
])
def test_anchor_to_edge_flags_and_margin_fields(tmp_path: Path, edge, expected_flags,
                                                margin_fields):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], f"Pinned_{edge}")

    cid = rsp.anchor_to_edge(scene, n, edge=edge, margin=20)

    w = _raw_component(scene, cid)
    assert w["__type__"] == "cc.Widget"
    assert w["_alignFlags"] == expected_flags
    # Each margin field in margin_fields should carry 20; the others
    # should remain at the default 0.
    for f in ("_top", "_bottom", "_left", "_right"):
        if f in margin_fields:
            assert w[f] == 20, f"{edge}: expected {f}=20, got {w[f]}"
        else:
            assert w[f] == 0, f"{edge}: expected {f}=0, got {w[f]}"


def test_anchor_to_edge_top_right_specific(tmp_path: Path):
    """Explicit case called out in the task spec — top-right = 1+8 = 9
    with margin written to both _top AND _right."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "CornerBadge")

    cid = rsp.anchor_to_edge(scene, n, edge="top-right", margin=24)

    w = _raw_component(scene, cid)
    assert w["_alignFlags"] == 9
    assert w["_top"] == 24
    assert w["_right"] == 24
    assert w["_bottom"] == 0
    assert w["_left"] == 0


def test_anchor_to_edge_default_margin_zero(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "HuggingEdge")

    cid = rsp.anchor_to_edge(scene, n, edge="top")

    w = _raw_component(scene, cid)
    assert w["_alignFlags"] == 1
    assert w["_top"] == 0  # default — hug the edge exactly


def test_anchor_to_edge_rejects_unknown_edge(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="edge"):
        rsp.anchor_to_edge(scene, n, edge="diagonal")


def test_anchor_to_edge_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Corner")
    sb.add_uitransform(scene, n, 100, 100)
    rsp.anchor_to_edge(scene, n, edge="bottom-right", margin=40)
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ======================================== #
# center_in_parent
# ======================================== #

def test_center_in_parent_both_axes(tmp_path: Path):
    """Default call centers on both axes: horizCenter(16) + vertCenter(32) = 48."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "CenterPanel")

    cid = rsp.center_in_parent(scene, n)

    w = _raw_component(scene, cid)
    assert w["__type__"] == "cc.Widget"
    assert w["_alignFlags"] == 48


def test_center_in_parent_horizontal_only(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "HCenter")

    cid = rsp.center_in_parent(scene, n, horizontal=True, vertical=False)

    w = _raw_component(scene, cid)
    assert w["_alignFlags"] == 16  # horizCenter only


def test_center_in_parent_vertical_only(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "VCenter")

    cid = rsp.center_in_parent(scene, n, horizontal=False, vertical=True)

    w = _raw_component(scene, cid)
    assert w["_alignFlags"] == 32  # vertCenter only


def test_center_in_parent_rejects_both_false(tmp_path: Path):
    """Asking for no centering would attach a dead Widget — loud-fail
    instead of silently noop."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError):
        rsp.center_in_parent(scene, n, horizontal=False, vertical=False)


# ======================================== #
# stack_vertically
# ======================================== #

def test_stack_vertically_attaches_layout_type_2(tmp_path: Path):
    """layout_type must be 2 (VERTICAL) with centered h_direction by default."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Column")

    cid = rsp.stack_vertically(scene, n)

    lay = _raw_component(scene, cid)
    assert lay["__type__"] == "cc.Layout"
    assert lay["_layoutType"] == 2
    # default align="center" → h_direction=2 (CENTER_HORIZONTAL)
    assert lay["_N$horizontalDirection"] == 2
    # resize_mode=1 (CONTAINER) — container grows to fit children
    assert lay["_resizeMode"] == 1


def test_stack_vertically_token_spacing_from_dark_game_theme(tmp_path: Path):
    """spacing='md' (=16) / padding='sm' (=8) must resolve from the
    active theme's spacing dict. dark_game: md=16, sm=8."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj, theme="dark_game")
    n = sb.add_node(scene, info["canvas_node_id"], "Column")

    cid = rsp.stack_vertically(scene, n, spacing="md", padding="sm")

    lay = _raw_component(scene, cid)
    assert lay["_N$spacingY"] == 16
    # All four padding edges get the same value
    assert lay["_N$paddingTop"] == 8
    assert lay["_N$paddingBottom"] == 8
    assert lay["_N$paddingLeft"] == 8
    assert lay["_N$paddingRight"] == 8


def test_stack_vertically_int_mode_passes_through(tmp_path: Path):
    """Raw int args are written verbatim — no token lookup."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Column")

    cid = rsp.stack_vertically(scene, n, spacing=30, padding=10)

    lay = _raw_component(scene, cid)
    assert lay["_N$spacingY"] == 30
    assert lay["_N$paddingTop"] == 10
    assert lay["_N$paddingBottom"] == 10
    assert lay["_N$paddingLeft"] == 10
    assert lay["_N$paddingRight"] == 10


@pytest.mark.parametrize("align,expected_h_dir", [
    ("left", 0),
    ("center", 2),
    ("right", 1),
])
def test_stack_vertically_align_mapping(tmp_path: Path, align, expected_h_dir):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], f"Col_{align}")

    cid = rsp.stack_vertically(scene, n, align=align)

    lay = _raw_component(scene, cid)
    assert lay["_N$horizontalDirection"] == expected_h_dir


def test_stack_vertically_rejects_bad_align(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="align"):
        rsp.stack_vertically(scene, n, align="middle")


def test_stack_vertically_bad_token_lists_valid_names(tmp_path: Path):
    """A typo'd token should raise ValueError AND enumerate all five
    valid names so the AI can self-correct without re-reading docs."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError) as exc:
        rsp.stack_vertically(scene, n, spacing="medium")
    msg = str(exc.value)
    for name in ("xs", "sm", "md", "lg", "xl"):
        assert name in msg, f"expected {name!r} to appear in: {msg}"


def test_stack_vertically_bad_padding_token(tmp_path: Path):
    """Error message should name the offending arg (padding, not spacing)."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="padding"):
        rsp.stack_vertically(scene, n, padding="huge")


def test_stack_vertically_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Column")
    sb.add_uitransform(scene, n, 400, 600)
    rsp.stack_vertically(scene, n, spacing="md", padding="lg")
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ======================================== #
# stack_horizontally
# ======================================== #

def test_stack_horizontally_attaches_layout_type_1(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Row")

    cid = rsp.stack_horizontally(scene, n)

    lay = _raw_component(scene, cid)
    assert lay["__type__"] == "cc.Layout"
    assert lay["_layoutType"] == 1


def test_stack_horizontally_token_padding(tmp_path: Path):
    """dark_game: lg=32 — the default for padding."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Row")

    cid = rsp.stack_horizontally(scene, n, spacing="md", padding="lg")

    lay = _raw_component(scene, cid)
    assert lay["_N$spacingX"] == 16  # md
    assert lay["_N$paddingTop"] == 32
    assert lay["_N$paddingBottom"] == 32
    assert lay["_N$paddingLeft"] == 32
    assert lay["_N$paddingRight"] == 32


@pytest.mark.parametrize("align,expected_v_dir", [
    ("top", 0),
    ("center", 2),
    ("bottom", 1),
])
def test_stack_horizontally_align_mapping(tmp_path: Path, align, expected_v_dir):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], f"Row_{align}")

    cid = rsp.stack_horizontally(scene, n, align=align)

    lay = _raw_component(scene, cid)
    assert lay["_N$verticalDirection"] == expected_v_dir


def test_stack_horizontally_rejects_bad_align(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="align"):
        rsp.stack_horizontally(scene, n, align="left")  # left isn't valid for horizontal


def test_stack_horizontally_int_mode(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Row")

    cid = rsp.stack_horizontally(scene, n, spacing=12, padding=24)

    lay = _raw_component(scene, cid)
    assert lay["_N$spacingX"] == 12
    assert lay["_N$paddingTop"] == 24
    assert lay["_N$paddingLeft"] == 24


def test_stack_horizontally_validates_scene(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Row")
    sb.add_uitransform(scene, n, 600, 80)
    rsp.stack_horizontally(scene, n, spacing="sm", padding="md", align="center")
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]


# ======================================== #
# cocos_lint_ui regression guard
# ======================================== #

def test_lint_ui_passes_on_composed_layout(tmp_path: Path):
    """Stringing all five helpers together into a plausible menu
    layout should produce zero UI lint warnings — if one of the
    helpers emits bad flags or components, ``lint_ui`` catches it."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    canvas = info["canvas_node_id"]

    # Fullscreen background
    bg = sb.add_node(scene, canvas, "Bg")
    sb.add_uitransform(scene, bg, 9999, 9999)
    sb.add_sprite(scene, bg, color_preset="bg")
    rsp.make_fullscreen(scene, bg)

    # Centered column of buttons, sized large enough to clear the
    # touch-target lint (otherwise lint_ui flags Buttons < 44px).
    column = sb.add_node(scene, bg, "Column")
    sb.add_uitransform(scene, column, 300, 400)
    rsp.center_in_parent(scene, column)
    rsp.stack_vertically(scene, column, spacing="md", padding="lg")

    for i in range(2):
        btn = sb.add_node(scene, column, f"Btn_{i}")
        sb.add_uitransform(scene, btn, 240, 64)  # > 44×44
        sb.add_button(scene, btn, color_preset="primary")

    # Corner badge pinned top-right
    badge = sb.add_node(scene, bg, "Badge")
    sb.add_uitransform(scene, badge, 80, 80)
    rsp.anchor_to_edge(scene, badge, edge="top-right", margin=16)

    # Horizontal toolbar pinned bottom
    toolbar = sb.add_node(scene, bg, "Toolbar")
    sb.add_uitransform(scene, toolbar, 800, 80)
    rsp.anchor_to_edge(scene, toolbar, edge="bottom", margin=0)
    rsp.stack_horizontally(scene, toolbar, spacing="sm", padding="sm",
                           align="center")

    # Final gates: structurally valid AND lint-clean.
    v = sb.validate_scene(scene)
    assert v["valid"], v["issues"]
    lint = sb.lint_ui(scene)
    assert lint["ok"], lint["warnings"]

"""Tests for declarative assertions: scene-level ``assert_scene_state``
plus the ``assert`` action kind inside ``run_preview_sequence``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import asserts as asserts_mod
from cocos import interact as interact_mod
from cocos import scene_builder as sb


# ========================================= #
# 1. Low-level primitives: _check, _resolve_path, _resolve_root
# ========================================= #

@pytest.mark.parametrize("op,actual,expected,want", [
    # Equality
    ("eq", 5, 5, True),
    ("eq", "hello", "hello", True),
    ("eq", 5, 6, False),
    ("ne", 5, 6, True),
    ("ne", 5, 5, False),
    # Ordered
    ("gt", 10, 5, True),
    ("gt", 5, 10, False),
    ("ge", 5, 5, True),
    ("lt", 5, 10, True),
    ("le", 5, 5, True),
    # Membership
    ("in", "a", ["a", "b", "c"], True),
    ("in", "z", ["a", "b", "c"], False),
    ("not_in", "z", ["a", "b", "c"], True),
    # Contains (inverted in — for strings / lists)
    ("contains", "hello world", "world", True),
    ("contains", [1, 2, 3], 2, True),
    ("contains", [1, 2, 3], 99, False),
    # Regex
    ("match", "abc123", r"\d+", True),
    ("match", "abc", r"\d+", False),
    # Null checks
    ("is_null", None, None, True),
    ("is_null", 0, None, False),
    ("not_null", 0, None, True),
    ("not_null", None, None, False),
    # Type
    ("type_is", 5, "int", True),
    ("type_is", "x", "str", True),
    ("type_is", [1], "list", True),
    ("type_is", {}, "dict", True),
    ("type_is", None, "null", True),
    ("type_is", 5, "str", False),
])
def test_check_operators(op, actual, expected, want):
    assert asserts_mod._check(actual, op, expected) is want


def test_check_unknown_op_raises():
    with pytest.raises(ValueError, match="unknown assertion op"):
        asserts_mod._check(1, "magic", 1)


def test_resolve_path_dict_keys():
    root = {"a": {"b": {"c": 42}}}
    assert asserts_mod._resolve_path(root, "a.b.c") == 42


def test_resolve_path_list_index_via_brackets():
    root = {"items": [10, 20, 30]}
    assert asserts_mod._resolve_path(root, "items[1]") == 20


def test_resolve_path_list_index_via_bare_int():
    """First dotted segment as int + root is list → list index."""
    root = [10, 20, 30]
    assert asserts_mod._resolve_path(root, "2") == 30


def test_resolve_path_mixed():
    root = {"list": [{"inner": "yes"}]}
    assert asserts_mod._resolve_path(root, "list[0].inner") == "yes"


def test_resolve_path_empty_returns_root():
    root = {"a": 1}
    assert asserts_mod._resolve_path(root, "") is root


def test_resolve_path_missing_key_raises_with_keys():
    root = {"a": 1, "b": 2, "c": 3}
    with pytest.raises(LookupError, match="x"):
        asserts_mod._resolve_path(root, "x")


def test_resolve_path_out_of_range_raises():
    root = [1, 2, 3]
    with pytest.raises(LookupError, match="out of range"):
        asserts_mod._resolve_path(root, "[10]")


def test_resolve_path_bracket_on_non_list_raises():
    with pytest.raises(LookupError, match="requires list"):
        asserts_mod._resolve_path({"a": 1}, "[0]")


# ========================================= #
# 2. assert_scene_state — finder shortcuts
# ========================================= #

def _scene_with_player(tmp_path: Path) -> Path:
    """Small scene: canvas under scene root, Player node with UITransform + Sprite."""
    scene = tmp_path / "s.scene"
    info = sb.create_empty_scene(scene)
    player = sb.add_node(scene, info["canvas_node_id"], "Player",
                         lpos=(100, 50, 0))
    sb.add_uitransform(scene, player, 80, 80)
    sb.add_sprite(scene, player, color=(255, 128, 64, 255))
    return scene


def test_find_node_by_name_then_path_passes(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "Player", "path": "_lpos.x",
         "op": "eq", "value": 100},
    ])
    assert result["ok"] is True
    assert result["passed_count"] == 1


def test_find_node_by_name_missing_reports_targeted_error(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "NotHere", "path": "_lpos.x",
         "op": "eq", "value": 0},
    ])
    assert result["ok"] is False
    assert "NotHere" in result["failed"][0]["error"]


def test_find_component_on_node(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    # Sprite color.r on Player — primary-color check
    result = asserts_mod.assert_scene_state(scene, [
        {"find_component": {"type": "cc.Sprite", "on_node_named": "Player"},
         "path": "_color.r", "op": "eq", "value": 255},
    ])
    assert result["ok"] is True


def test_find_component_missing_type(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    # Player has no cc.RigidBody2D
    result = asserts_mod.assert_scene_state(scene, [
        {"find_component": {"type": "cc.RigidBody2D", "on_node_named": "Player"},
         "path": "_enabled", "op": "eq", "value": True},
    ])
    assert result["ok"] is False
    assert "no cc.RigidBody2D" in result["failed"][0]["error"]


def test_find_component_missing_node(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_component": {"type": "cc.Sprite", "on_node_named": "Ghost"},
         "path": "_color.r", "op": "eq", "value": 0},
    ])
    assert result["ok"] is False


def test_find_component_bad_spec_raises_via_failure(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        # Missing on_node_named
        {"find_component": {"type": "cc.Sprite"},
         "path": "_color.r", "op": "eq", "value": 0},
    ])
    assert result["ok"] is False
    assert "on_node_named" in result["failed"][0]["error"]


# ========================================= #
# 3. exists / not_exists semantics
# ========================================= #

def test_exists_passes_when_path_resolves(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "Player", "path": "_lpos", "op": "exists"},
    ])
    assert result["ok"] is True


def test_not_exists_passes_when_path_missing(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "Player", "path": "some_missing_field",
         "op": "not_exists"},
    ])
    assert result["ok"] is True


def test_exists_fails_when_path_missing(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "Player", "path": "some_missing_field",
         "op": "exists"},
    ])
    assert result["ok"] is False


def test_not_exists_fails_when_path_resolves(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "Player", "path": "_lpos.x", "op": "not_exists"},
    ])
    assert result["ok"] is False


# ========================================= #
# 4. Full-report semantics: all assertions run even if some fail
# ========================================= #

def test_assertions_run_to_completion(tmp_path: Path):
    """3 assertions where #2 fails — #3 must still run + appear in result."""
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "Player", "path": "_lpos.x",
         "op": "eq", "value": 100},                    # pass
        {"find_node_by_name": "Player", "path": "_lpos.x",
         "op": "eq", "value": 9999},                   # fail
        {"find_node_by_name": "Player", "path": "_active",
         "op": "eq", "value": True},                   # pass (would skip on bail-on-fail)
    ])
    assert result["total"] == 3
    assert result["passed_count"] == 2
    assert result["failed_count"] == 1
    # Every assertion must be in exactly one of the two buckets
    assert len(result["passed"]) + len(result["failed"]) == 3


def test_failed_assertion_carries_actual_and_expected(tmp_path: Path):
    scene = _scene_with_player(tmp_path)
    result = asserts_mod.assert_scene_state(scene, [
        {"find_node_by_name": "Player", "path": "_lpos.x",
         "op": "eq", "value": 9999},
    ])
    failed = result["failed"][0]
    assert failed["actual"] == 100
    assert failed["expected"] == 9999


# ========================================= #
# 5. Raw array indexing (no finder)
# ========================================= #

def test_bare_index_path_works_on_scene_array(tmp_path: Path):
    """No find_* → root is the scene array, first path segment is int index."""
    scene = _scene_with_player(tmp_path)
    # scene[1] should be cc.Scene
    result = asserts_mod.assert_scene_state(scene, [
        {"path": "1.__type__", "op": "eq", "value": "cc.Scene"},
    ])
    assert result["ok"] is True


# ========================================= #
# 6. interact.run_preview_sequence assert action kind
# ========================================= #

def _mock_playwright(page_behaviour: dict):
    """Build the mocked sync_playwright chain; page.evaluate returns the
    eval result from ``page_behaviour['evaluate_returns']`` by expression."""
    fake_page = mock.MagicMock()
    fake_page.evaluate.side_effect = lambda expr: page_behaviour.get("evaluate_returns", {}).get(expr)

    fake_ctx = mock.MagicMock()
    fake_ctx.new_page.return_value = fake_page

    fake_browser = mock.MagicMock()
    fake_browser.new_context.return_value = fake_ctx

    fake_chromium = mock.MagicMock()
    fake_chromium.launch.return_value = fake_browser

    fake_pw_api = mock.MagicMock()
    fake_pw_api.__enter__.return_value = mock.MagicMock(chromium=fake_chromium)
    fake_pw_api.__exit__.return_value = None

    return fake_page, fake_pw_api


def test_sequence_assert_action_passes(tmp_path: Path):
    fake_page, fake_pw = _mock_playwright({
        "evaluate_returns": {"window.game.score": 42},
    })
    with mock.patch.dict(sys.modules, {
        "playwright": mock.MagicMock(),
        "playwright.sync_api": mock.MagicMock(sync_playwright=lambda: fake_pw),
    }):
        results = interact_mod.run_preview_sequence("http://fake/", actions=[
            {"kind": "assert", "expression": "window.game.score",
             "op": "eq", "value": 42},
        ])
    assert len(results) == 1
    assert results[0]["kind"] == "assert"
    assert results[0]["ok"] is True
    assert results[0]["result"]["passed"] is True
    assert results[0]["result"]["actual"] == 42
    assert results[0]["error"] is None


def test_sequence_assert_action_fails_carries_clear_error(tmp_path: Path):
    fake_page, fake_pw = _mock_playwright({
        "evaluate_returns": {"window.game.score": 7},
    })
    with mock.patch.dict(sys.modules, {
        "playwright": mock.MagicMock(),
        "playwright.sync_api": mock.MagicMock(sync_playwright=lambda: fake_pw),
    }):
        results = interact_mod.run_preview_sequence("http://fake/", actions=[
            {"kind": "assert", "expression": "window.game.score",
             "op": "ge", "value": 100},
        ])
    assert results[0]["ok"] is False
    assert results[0]["result"]["passed"] is False
    assert results[0]["result"]["actual"] == 7
    # Error message should surface op + actual + expected
    err = results[0]["error"]
    assert "ge" in err and "7" in err and "100" in err


def test_sequence_mixed_click_wait_assert(tmp_path: Path):
    """Integration: a realistic sequence — click Start, wait for scene
    transition, assert score reset to 0, assert state is 'play'."""
    fake_page, fake_pw = _mock_playwright({
        "evaluate_returns": {
            "window.game.score": 0,
            "window.game.state": "play",
        },
    })
    with mock.patch.dict(sys.modules, {
        "playwright": mock.MagicMock(),
        "playwright.sync_api": mock.MagicMock(sync_playwright=lambda: fake_pw),
    }):
        results = interact_mod.run_preview_sequence("http://fake/", actions=[
            {"kind": "click", "x": 480, "y": 320},
            {"kind": "wait", "ms": 300},
            {"kind": "assert", "expression": "window.game.score",
             "op": "eq", "value": 0},
            {"kind": "assert", "expression": "window.game.state",
             "op": "eq", "value": "play"},
        ])
    assert [r["kind"] for r in results] == ["click", "wait", "assert", "assert"]
    assert all(r["ok"] for r in results)


def test_sequence_assert_action_does_not_short_circuit_on_failure(tmp_path: Path):
    """Per the sequence-level contract, one failing action shouldn't skip
    subsequent ones. A failed assert should still let later actions run."""
    fake_page, fake_pw = _mock_playwright({
        "evaluate_returns": {
            "a": 1,
            "b": 2,
        },
    })
    with mock.patch.dict(sys.modules, {
        "playwright": mock.MagicMock(),
        "playwright.sync_api": mock.MagicMock(sync_playwright=lambda: fake_pw),
    }):
        results = interact_mod.run_preview_sequence("http://fake/", actions=[
            {"kind": "assert", "expression": "a", "op": "eq", "value": 999},  # fail
            {"kind": "assert", "expression": "b", "op": "eq", "value": 2},    # pass
        ])
    assert len(results) == 2
    assert results[0]["ok"] is False
    assert results[1]["ok"] is True


# ========================================= #
# 7. MCP tool surface
# ========================================= #

def test_mcp_tool_cocos_assert_scene_state_registered():
    """Regression guard that the tool is attached at the MCP layer."""
    import server
    mgr = server.mcp._tool_manager
    assert "cocos_assert_scene_state" in mgr._tools

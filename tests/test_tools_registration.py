"""Smoke tests for the MCP tool registration layer.

The tools/ submodules are 100% thin wrappers — every test elsewhere targets
the underlying ``cocos.scene_builder`` / ``cocos.project`` / ``cocos.build``
functions directly. That gave us 0% line coverage on cocos/tools/*, which
means a busted wrapper (wrong arg order, swapped color tuple, typo in the
prop name) would never be caught until an AI client actually called it.

These tests cover the gap by:
  1. Confirming ``tools.register_all`` registers every expected tool.
  2. Spot-checking ~10 wrappers end-to-end via the MCP tool manager — we
     don't care about behavior depth here (other tests have that), only
     that the wrapper forwards args correctly and the JSON schema parses.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import tools


@pytest.fixture(scope="module")
def mcp_inst():
    m = FastMCP("test-cocos")
    tools.register_all(m)
    return m


def _all_tool_names(m: FastMCP) -> list[str]:
    return list(m._tool_manager._tools.keys())


# ============================================================
#  Registration coverage
# ============================================================

def test_register_all_attaches_at_least_100_tools(mcp_inst):
    names = _all_tool_names(mcp_inst)
    assert len(names) >= 100, f"expected >=100 tools, got {len(names)}"


def test_every_tool_starts_with_cocos_prefix(mcp_inst):
    names = _all_tool_names(mcp_inst)
    bad = [n for n in names if not n.startswith("cocos_")]
    assert not bad, f"tools without cocos_ prefix: {bad}"


def test_no_duplicate_tool_names(mcp_inst):
    names = _all_tool_names(mcp_inst)
    assert len(names) == len(set(names)), "duplicate tool names registered"


def test_critical_tools_are_registered(mcp_inst):
    """Spot check that a representative slice across every concern is present."""
    names = set(_all_tool_names(mcp_inst))
    must_have = {
        # core
        "cocos_new_uuid", "cocos_compress_uuid", "cocos_init_project",
        "cocos_add_image", "cocos_set_sprite_frame_border", "cocos_constants",
        # scene
        "cocos_create_scene", "cocos_create_node", "cocos_add_uitransform",
        "cocos_add_sprite", "cocos_validate_scene", "cocos_batch_scene_ops",
        "cocos_create_prefab", "cocos_instantiate_prefab",
        "cocos_set_ambient", "cocos_set_skybox", "cocos_set_shadows",
        # physics + ui
        "cocos_add_rigidbody2d", "cocos_add_box_collider2d",
        "cocos_add_distance_joint2d", "cocos_add_hinge_joint2d",
        "cocos_add_spring_joint2d", "cocos_add_button", "cocos_add_layout",
        # media
        "cocos_add_audio_source", "cocos_add_animation",
        "cocos_add_camera", "cocos_add_richtext", "cocos_add_video_player",
        # build
        "cocos_build", "cocos_start_preview", "cocos_clean_project",
        "cocos_set_native_build_config", "cocos_set_bundle_config",
        "cocos_set_wechat_subpackages", "cocos_set_wechat_appid",
        "cocos_set_engine_module",
    }
    missing = must_have - names
    assert not missing, f"critical tools not registered: {sorted(missing)}"


def test_every_tool_has_description(mcp_inst):
    """FastMCP uses the function docstring as the tool description.
    AI clients rely on that to pick which tool to call — empty descriptions
    silently degrade tool selection quality."""
    bad = []
    for name, t in mcp_inst._tool_manager._tools.items():
        desc = (t.description or "").strip()
        if not desc:
            bad.append(name)
    assert not bad, f"tools missing docstrings: {bad}"


def test_every_tool_has_parameters_schema(mcp_inst):
    """Each tool should expose a JSON-Schema for its parameters (the
    pydantic model FastMCP builds from the function signature). Tools
    with no parameters still get a schema with empty 'properties'."""
    bad = []
    for name, t in mcp_inst._tool_manager._tools.items():
        if not isinstance(t.parameters, dict) or "properties" not in t.parameters:
            bad.append(name)
    assert not bad, f"tools missing JSON-Schema 'parameters.properties': {bad}"


# ============================================================
#  Wrapper round-trip — end-to-end via tool manager
# ============================================================
#
# These call into the underlying functions and verify the wrapper forwards
# arguments correctly. They're not exhaustive — just enough to catch a
# wrong-arg-order regression in any of the 5 tools/*.py modules.

@pytest.mark.anyio
async def test_call_uuid_round_trip(mcp_inst):
    """Verifies cocos_new_uuid → compress → decompress wrappers route args
    correctly through the tool manager (not just by direct sb.* call)."""
    mgr = mcp_inst._tool_manager
    new_uuid = await mgr.call_tool("cocos_new_uuid", {})
    assert isinstance(new_uuid, str)
    assert len(new_uuid) == 36 and new_uuid.count("-") == 4

    short = await mgr.call_tool("cocos_compress_uuid", {"uuid": new_uuid})
    assert len(short) == 23

    back = await mgr.call_tool("cocos_decompress_uuid", {"short_uuid": short})
    assert back == new_uuid


@pytest.mark.anyio
async def test_call_create_scene_then_add_node(mcp_inst, tmp_path: Path):
    """Realistic build flow through wrappers: project skeleton → scene → node."""
    mgr = mcp_inst._tool_manager

    # Need a project skeleton (no Creator install required for these tools)
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"test"}')
    (proj / "assets/scenes").mkdir(parents=True)

    info = await mgr.call_tool("cocos_create_scene", {"project_path": str(proj)})
    assert "scene_path" in info and "canvas_node_id" in info
    sp = info["scene_path"]
    canvas = info["canvas_node_id"]

    node_id = await mgr.call_tool("cocos_create_node",
                                  {"scene_path": sp, "parent_id": canvas, "name": "Player"})
    assert isinstance(node_id, int) and node_id > canvas

    val = await mgr.call_tool("cocos_validate_scene", {"scene_path": sp})
    assert val["valid"] is True


@pytest.mark.anyio
async def test_call_constants_returns_tables(mcp_inst):
    sc = await mcp_inst._tool_manager.call_tool("cocos_constants", {})
    # Every category we promise in the docstring must be present
    for cat in ("layers", "blend_factors", "label_align", "sprite_type",
                "rigidbody2d_type", "button_transition", "layout_type"):
        assert cat in sc, f"cocos_constants missing category: {cat}"
    assert sc["layers"]["UI_2D"] == 33554432


@pytest.mark.anyio
async def test_call_set_node_position_forwards_correctly(mcp_inst, tmp_path: Path):
    """Spot-check that scene.py wrapper passes (x, y, z) to set_node_position
    in the right order — easy to get wrong with positional args."""
    from cocos import scene_builder as sb
    sp = tmp_path / "s.scene"
    info = sb.create_empty_scene(sp)
    canvas = info["canvas_node_id"]
    n = sb.add_node(sp, canvas, "T")

    await mcp_inst._tool_manager.call_tool("cocos_set_node_position", {
        "scene_path": str(sp), "node_id": n, "x": 10, "y": 20, "z": 5,
    })
    obj = sb.get_object(sp, n)
    assert obj["_lpos"]["x"] == 10
    assert obj["_lpos"]["y"] == 20
    assert obj["_lpos"]["z"] == 5  # easy off-by-one if wrapper drops z


@pytest.mark.anyio
async def test_call_color_tuple_wrapper_forwards_rgba(mcp_inst, tmp_path: Path):
    """The color_r/g/b/a → tuple repacking pattern is in many wrappers
    (label, sprite, button, motion_streak…). Easy to get the order wrong;
    verify with cocos_add_label."""
    from cocos import scene_builder as sb
    sp = tmp_path / "s.scene"
    info = sb.create_empty_scene(sp)
    canvas = info["canvas_node_id"]
    n = sb.add_node(sp, canvas, "T")

    cid = await mcp_inst._tool_manager.call_tool("cocos_add_label", {
        "scene_path": str(sp), "node_id": n, "text": "Hi",
        "color_r": 200, "color_g": 100, "color_b": 50, "color_a": 240,
    })
    obj = sb.get_object(sp, cid)
    assert obj["_color"] == {"__type__": "cc.Color", "r": 200, "g": 100, "b": 50, "a": 240}


# AnyIO backend — pytest-anyio defaults to trio + asyncio; we only need asyncio
@pytest.fixture
def anyio_backend():
    return "asyncio"

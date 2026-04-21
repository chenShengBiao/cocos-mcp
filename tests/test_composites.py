"""Tests for cocos.composites — the single-call shorthands that fold
multi-step dogfood sequences into one tool.

Each composite should behave exactly as the equivalent primitive
sequence, returning both halves of what the caller needs (script uuid +
attached component id in the case of ``add_and_attach_script``). The
interesting regressions are around the Bug A interaction (overwriting
an existing script via the composite shouldn't mint a new UUID) and
the Bug B interaction (attaching to a ``.prefab`` node should produce
a valid prefab).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import composites as co
from cocos import project as cp
from cocos import scene_builder as sb
from cocos.uuid_util import compress_uuid


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    p.mkdir()
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    (p / "assets").mkdir()
    return p


def _make_scene(tmp_path: Path) -> tuple[Path, dict]:
    scene_path = tmp_path / "main.scene"
    info = sb.create_empty_scene(scene_path)
    return scene_path, info


# ================================================================ #
# add_and_attach_script — the most-used composite
# ================================================================ #

def test_add_and_attach_script_creates_file_compresses_and_attaches(tmp_path: Path):
    """The happy path: writes the .ts, compresses the uuid, and
    attaches a scene component that actually references the right
    __type__ (= compressed uuid).
    """
    proj = _make_project(tmp_path)
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "Bird")

    r = co.add_and_attach_script(
        str(proj), "Bird", "export class Bird {}",
        str(scene), node,
    )

    assert Path(r["script_path"]).exists(), "script file must be written"
    assert r["rel_path"] == "assets/scripts/Bird.ts"
    assert len(r["uuid_standard"]) == 36 and "-" in r["uuid_standard"]
    assert r["uuid_compressed"] == compress_uuid(r["uuid_standard"])
    assert r["created"] is True
    assert isinstance(r["component_id"], int) and r["component_id"] > 0

    # The component in the scene file must carry the COMPRESSED uuid as
    # its __type__ — that's how Cocos looks up the script class.
    with open(scene) as f:
        data = json.load(f)
    comp = data[r["component_id"]]
    assert comp["__type__"] == r["uuid_compressed"]
    # And it must be wired to the node's _components list.
    assert any(c["__id__"] == r["component_id"] for c in data[node]["_components"])


def test_add_and_attach_script_forwards_props(tmp_path: Path):
    """`props` must reach the scene component verbatim — bare ints stay
    ints (not coerced to __id__ refs), dict refs pass through untouched.
    Same contract as the underlying scene_builder.add_script."""
    proj = _make_project(tmp_path)
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "Player")
    label_node = sb.add_node(scene, info["canvas_node_id"], "ScoreLabel")

    r = co.add_and_attach_script(
        str(proj), "Player", "export class Player {}",
        str(scene), node,
        props={
            "speed": 100,                           # literal int (NOT a ref)
            "scoreLabel": {"__id__": label_node},   # explicit ref
            "prefab": {"__uuid__": "abc-def"},      # asset ref
        },
    )

    with open(scene) as f:
        data = json.load(f)
    comp = data[r["component_id"]]
    assert comp["speed"] == 100                              # not {"__id__": 100}
    assert comp["scoreLabel"] == {"__id__": label_node}
    assert comp["prefab"] == {"__uuid__": "abc-def"}


def test_add_and_attach_script_idempotent_on_rewrite(tmp_path: Path):
    """Bug A via the composite: overwriting the source preserves the
    UUID, so the scene's attached component still resolves. Prior to
    the Bug A fix, the second call would have silently rewritten
    <uuid>.meta to a new value, breaking the first call's attachment."""
    proj = _make_project(tmp_path)
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "Foo")

    first = co.add_and_attach_script(
        str(proj), "Foo", "export class Foo { a = 1; }",
        str(scene), node,
    )
    # Rewrite source (no ``uuid=`` override) via the composite.
    second_node = sb.add_node(scene, info["canvas_node_id"], "Foo2")
    second = co.add_and_attach_script(
        str(proj), "Foo", "export class Foo { a = 2; }",
        str(scene), second_node,
    )

    assert second["uuid_standard"] == first["uuid_standard"]
    assert second["uuid_compressed"] == first["uuid_compressed"]
    assert second["created"] is False
    # Both components in the scene share the same __type__ — both work
    # and both reference a single script class.
    with open(scene) as f:
        data = json.load(f)
    assert data[first["component_id"]]["__type__"] == data[second["component_id"]]["__type__"]


def test_add_and_attach_script_on_prefab_writes_prefab_info(tmp_path: Path):
    """Bug B interaction: attaching a script onto a node inside a
    ``.prefab`` is the combined-Bug-B path — the composite invokes
    scene_builder.add_script, which uses _attach_component (not
    add_node), so PrefabInfo wiring for a fresh child node is the
    caller's responsibility. But attaching onto an already-valid
    prefab node must not break the prefab's structure.
    """
    proj = _make_project(tmp_path)
    prefab = tmp_path / "Pipe.prefab"
    info = sb.create_prefab(str(prefab), root_name="Pipe")
    root = info["root_node_id"]

    r = co.add_and_attach_script(
        str(proj), "Pipe", "export class Pipe {}",
        str(prefab), root,
    )

    with open(prefab) as f:
        data = json.load(f)
    # Root still has PrefabInfo (unchanged by attach)
    assert data[root]["_prefab"] is not None
    # Script component attached
    comp = data[r["component_id"]]
    assert comp["__type__"] == r["uuid_compressed"]


def test_add_and_attach_script_explicit_uuid_forces_identity(tmp_path: Path):
    """The composite forwards ``uuid=`` to the underlying add_script,
    so callers keep the 'fork the script' escape hatch."""
    proj = _make_project(tmp_path)
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "Fork")

    forced = "aabbccdd-1111-2222-3333-444455556666"
    r = co.add_and_attach_script(
        str(proj), "Fork", "// v1",
        str(scene), node,
        uuid=forced,
    )
    assert r["uuid_standard"] == forced
    assert r["created"] is True


def test_add_and_attach_script_tool_registration():
    """Sanity: the composites show up in the MCP tool surface so the
    agent can actually find them. Regression guard for tools/__init__.py
    forgetting to call composites.register."""
    from cocos.tools import composites as tools_composites
    assert hasattr(tools_composites, "register")

    class _Mock:
        def __init__(self):
            self.tools: dict = {}

        def tool(self):
            def wrap(fn):
                self.tools[fn.__name__] = fn
                return fn
            return wrap

    m = _Mock()
    tools_composites.register(m)
    for expected in ("cocos_add_and_attach_script",
                     "cocos_add_physics_body2d",
                     "cocos_add_button_with_label"):
        assert expected in m.tools, f"{expected} must be registered"


# =============================================================== #
# add_physics_body2d — RigidBody2D + shape collider in one call
# =============================================================== #

def test_add_physics_body2d_box_shape(tmp_path: Path):
    """Box shape produces cc.RigidBody2D + cc.BoxCollider2D wired on
    the same node, with explicit width/height passed through."""
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "Bird")

    r = co.add_physics_body2d(str(scene), node, shape="box",
                              body_type=2, gravity_scale=1.5,
                              width=40, height=30, friction=0.1)

    with open(scene) as f:
        data = json.load(f)
    rb = data[r["rigidbody_id"]]
    assert rb["__type__"] == "cc.RigidBody2D"
    # Engine serializes with underscore-prefixed backing-field names —
    # see physics.py module docstring. Pre-fix we wrote non-underscore
    # versions which the runtime silently ignored.
    assert rb["_type"] == 2
    assert rb["_gravityScale"] == 1.5
    col = data[r["collider_id"]]
    assert col["__type__"] == "cc.BoxCollider2D"
    # cc.Size dict (not a [w, h] list — the engine deserializes a list
    # to a zero-filled Size and the collider silently becomes a 1×1
    # square).
    assert col["_size"] == {"__type__": "cc.Size", "width": 40, "height": 30}
    assert col["_friction"] == 0.1
    assert r["shape"] == "box"


def test_add_physics_body2d_circle_shape(tmp_path: Path):
    """Circle shape passes `radius` through, ignores width/height."""
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "Ball")

    r = co.add_physics_body2d(str(scene), node, shape="circle",
                              radius=75, is_sensor=True)

    with open(scene) as f:
        data = json.load(f)
    assert data[r["collider_id"]]["__type__"] == "cc.CircleCollider2D"
    assert data[r["collider_id"]]["_radius"] == 75
    assert data[r["collider_id"]]["_sensor"] is True


def test_add_physics_body2d_polygon_shape(tmp_path: Path):
    """Polygon shape accepts explicit vertex list. Each vertex is
    emitted as a ``cc.Vec2`` dict — engine types ``_points`` as
    ``Vec2[]``, so raw tuple/list elements deserialize to a
    zero-filled Vec2 and the polygon degenerates."""
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "Poly")
    triangle = [[0, 40], [-40, -40], [40, -40]]

    r = co.add_physics_body2d(str(scene), node, shape="polygon",
                              points=triangle, density=2.0)

    with open(scene) as f:
        data = json.load(f)
    assert data[r["collider_id"]]["__type__"] == "cc.PolygonCollider2D"
    assert data[r["collider_id"]]["_points"] == [
        {"__type__": "cc.Vec2", "x": 0, "y": 40},
        {"__type__": "cc.Vec2", "x": -40, "y": -40},
        {"__type__": "cc.Vec2", "x": 40, "y": -40},
    ]
    assert data[r["collider_id"]]["_density"] == 2.0


def test_add_physics_body2d_unknown_shape_raises(tmp_path: Path):
    """Silent-attach of a default on unknown shape would hide typos —
    raise explicitly instead."""
    import pytest
    scene, info = _make_scene(tmp_path)
    node = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="unknown shape"):
        co.add_physics_body2d(str(scene), node, shape="capsule")


# =============================================================== #
# add_button_with_label — button node + child Label in one call
# =============================================================== #

def test_add_button_with_label_structure(tmp_path: Path):
    """Produces the canonical Btn → Label parent/child pair with all
    four components (UITransform+Button on Btn, UITransform+Label on
    Label)."""
    scene, info = _make_scene(tmp_path)

    r = co.add_button_with_label(str(scene), info["canvas_node_id"],
                                 "Play", width=180, height=54,
                                 name="PlayBtn", font_size=40)

    with open(scene) as f:
        data = json.load(f)
    # Node hierarchy
    assert data[r["button_node_id"]]["_name"] == "PlayBtn"
    assert data[r["label_node_id"]]["_name"] == "Label"
    # Label is a direct child of the button
    assert data[r["label_node_id"]]["_parent"]["__id__"] == r["button_node_id"]
    # Components attached
    assert data[r["button_component_id"]]["__type__"] == "cc.Button"
    assert data[r["label_component_id"]]["__type__"] == "cc.Label"
    assert data[r["label_component_id"]]["_string"] == "Play"
    assert data[r["label_component_id"]]["_fontSize"] == 40
    # UITransform dimensions match
    # (Button's UITransform is the first _components entry — attached by add_uitransform.)
    btn_components = data[r["button_node_id"]]["_components"]
    btn_uit_id = btn_components[0]["__id__"]
    assert data[btn_uit_id]["__type__"] == "cc.UITransform"
    assert data[btn_uit_id]["_contentSize"] == {
        "__type__": "cc.Size", "width": 180, "height": 54,
    }
    # No background sprite when sprite_frame_uuid omitted + no bg preset
    assert r["sprite_component_id"] is None


def test_add_button_with_label_sprite_frame_uuid(tmp_path: Path):
    """When sprite_frame_uuid is set, a cc.Sprite is attached to the
    button node with the uuid wired to _spriteFrame."""
    scene, info = _make_scene(tmp_path)

    r = co.add_button_with_label(str(scene), info["canvas_node_id"],
                                 "OK", sprite_frame_uuid="xxxxxx@f9941")

    assert r["sprite_component_id"] is not None
    with open(scene) as f:
        data = json.load(f)
    sprite = data[r["sprite_component_id"]]
    assert sprite["__type__"] == "cc.Sprite"
    assert sprite["_spriteFrame"] == {"__uuid__": "xxxxxx@f9941"}


def test_add_button_with_label_forwards_click_events(tmp_path: Path):
    """click_events are forwarded to add_button verbatim — each
    event gets materialized as a separate cc.ClickEvent entry."""
    scene, info = _make_scene(tmp_path)
    # Set up a receiver node with a script-component placeholder.
    # For this test we just need a target node id; make_click_event
    # accepts any int.
    target = sb.add_node(scene, info["canvas_node_id"], "GM")
    evt = sb.make_click_event(target, "GameMgr", "onPlay")

    r = co.add_button_with_label(str(scene), info["canvas_node_id"],
                                 "Start", click_events=[evt])

    with open(scene) as f:
        data = json.load(f)
    btn = data[r["button_component_id"]]
    assert len(btn["clickEvents"]) == 1
    evt_obj = data[btn["clickEvents"][0]["__id__"]]
    assert evt_obj["__type__"] == "cc.ClickEvent"
    assert evt_obj["handler"] == "onPlay"


# =============================================================== #
# cocos_list_tools — introspection
# =============================================================== #

def test_cocos_list_tools_returns_every_registered_tool():
    """Without filters, list_tools returns the full registered surface.
    This also verifies our test-time registration covers every module."""
    from mcp.server.fastmcp import FastMCP
    from cocos.tools import register_all

    mcp = FastMCP("t")
    register_all(mcp)
    # Invoke the registered tool — it's captured by the FastMCP
    # manager, so we pull it back out for direct call.
    tool = mcp._tool_manager.get_tool("cocos_list_tools")
    assert tool is not None
    result = tool.fn()

    assert result["count"] == len(result["tools"])
    # Sanity: a handful of well-known tools show up.
    names = {t["name"] for t in result["tools"]}
    for expected in ("cocos_new_uuid", "cocos_create_scene",
                     "cocos_add_rigidbody2d", "cocos_list_tools",
                     "cocos_add_and_attach_script"):
        assert expected in names, f"{expected} missing from list"


def test_cocos_list_tools_name_contains_filter():
    """``name_contains`` is a case-insensitive substring match."""
    from mcp.server.fastmcp import FastMCP
    from cocos.tools import register_all

    mcp = FastMCP("t")
    register_all(mcp)
    tool = mcp._tool_manager.get_tool("cocos_list_tools")
    assert tool is not None
    result = tool.fn(name_contains="joint")

    names = [t["name"] for t in result["tools"]]
    assert len(names) >= 8, "expected at least 8 joint-related tools"
    assert all("joint" in n.lower() for n in names)


def test_cocos_list_tools_category_filter():
    """``category`` narrows to a single heuristic bucket."""
    from mcp.server.fastmcp import FastMCP
    from cocos.tools import register_all

    mcp = FastMCP("t")
    register_all(mcp)
    tool = mcp._tool_manager.get_tool("cocos_list_tools")
    assert tool is not None
    result = tool.fn(category="scaffold")

    assert result["count"] >= 9, "9 gameplay scaffolds + 1 introspection"
    for item in result["tools"]:
        assert item["category"] == "scaffold"
        assert "scaffold" in item["name"].lower()


def test_cocos_list_tools_no_other_bucket():
    """Regression guard for the category heuristic — every registered
    tool should land in a known bucket. If ``other`` ever grows, add
    a rule in ``_CATEGORY_RULES``."""
    from mcp.server.fastmcp import FastMCP
    from cocos.tools import register_all

    mcp = FastMCP("t")
    register_all(mcp)
    tool = mcp._tool_manager.get_tool("cocos_list_tools")
    assert tool is not None
    result = tool.fn(category="other")
    assert result["count"] == 0, \
        f"these tools need a category rule: {[t['name'] for t in result['tools']]}"

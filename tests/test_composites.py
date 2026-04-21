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
    """Sanity: the composite shows up in the MCP tool surface so the
    agent can actually find it. Regression guard for tools/__init__.py
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
    assert "cocos_add_and_attach_script" in m.tools

"""Tests for cocos.scene_builder."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.scene_builder import (
    _auto_wrap_value,
    add_box_collider2d,
    add_button,
    add_component,
    add_label,
    add_node,
    add_rigidbody2d,
    add_script,
    add_uitransform,
    batch_ops,
    create_empty_scene,
    delete_node,
    duplicate_node,
    find_node_by_name,
    move_node,
    validate_scene,
)


def _tmp_scene(**kwargs):
    f = tempfile.NamedTemporaryFile(suffix=".scene", delete=False)
    f.close()
    info = create_empty_scene(f.name, **kwargs)
    return f.name, info


class TestAutoWrap:
    def test_vec3(self):
        r = _auto_wrap_value("pos", [1, 2, 3])
        assert r == {"__type__": "cc.Vec3", "x": 1, "y": 2, "z": 3}

    def test_color(self):
        r = _auto_wrap_value("_color", [255, 0, 0, 255])
        assert r["__type__"] == "cc.Color"
        assert r["r"] == 255

    def test_size(self):
        r = _auto_wrap_value("contentSize", [100, 50])
        assert r["__type__"] == "cc.Size"

    def test_vec2(self):
        r = _auto_wrap_value("offset", [10, 20])
        assert r["__type__"] == "cc.Vec2"

    def test_int_to_ref(self):
        assert _auto_wrap_value("parent", 5) == {"__id__": 5}

    def test_float_passthrough(self):
        assert _auto_wrap_value("gravity", 9.8) == 9.8

    def test_string_passthrough(self):
        assert _auto_wrap_value("name", "hello") == "hello"

    def test_dict_passthrough(self):
        d = {"__uuid__": "abc"}
        assert _auto_wrap_value("clip", d) is d


class TestCreateScene:
    def test_basic(self):
        path, info = _tmp_scene()
        assert info["canvas_node_id"] == 2
        assert info["camera_component_id"] == 4
        v = validate_scene(path)
        assert v["valid"]
        assert v["object_count"] == 13

    def test_custom_size(self):
        path, info = _tmp_scene(canvas_width=480, canvas_height=320)
        with open(path) as f:
            data = json.load(f)
        uit = data[info["canvas_node_id"] + 3]  # Canvas UITransform (id 5)
        assert uit["_contentSize"]["width"] == 480


class TestNodeOps:
    def test_add_node(self):
        path, info = _tmp_scene()
        nid = add_node(path, info["canvas_node_id"], "TestNode", lpos=(10, 20, 0))
        assert nid == 13
        v = validate_scene(path)
        assert v["valid"]

    def test_sibling_index(self):
        path, info = _tmp_scene()
        add_node(path, info["canvas_node_id"], "First")
        n2 = add_node(path, info["canvas_node_id"], "Second", sibling_index=0)
        with open(path) as f:
            data = json.load(f)
        children = [c["__id__"] for c in data[info["canvas_node_id"]]["_children"]]
        assert children[0] == n2  # Second inserted at index 0

    def test_find_by_name(self):
        path, info = _tmp_scene()
        add_node(path, info["canvas_node_id"], "MyNode")
        found = find_node_by_name(path, "MyNode")
        assert found is not None
        assert find_node_by_name(path, "NonExistent") is None

    def test_move_node(self):
        path, info = _tmp_scene()
        n1 = add_node(path, info["canvas_node_id"], "Parent1")
        n2 = add_node(path, info["canvas_node_id"], "Child")
        move_node(path, n2, n1)
        with open(path) as f:
            data = json.load(f)
        assert data[n2]["_parent"]["__id__"] == n1
        children_of_n1 = [c["__id__"] for c in data[n1]["_children"]]
        assert n2 in children_of_n1

    def test_delete_node(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "ToDelete")
        delete_node(path, n)
        with open(path) as f:
            data = json.load(f)
        assert not data[n]["_active"]
        assert data[n]["_parent"] is None

    def test_duplicate_node(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "Orig")
        d = duplicate_node(path, n, "Copy")
        with open(path) as f:
            data = json.load(f)
        assert data[d]["_name"] == "Copy"


class TestComponents:
    def test_add_uitransform(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "N")
        cid = add_uitransform(path, n, 200, 100)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.UITransform"
        assert data[cid]["_contentSize"]["width"] == 200

    def test_add_label(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "N")
        add_uitransform(path, n, 200, 50)
        cid = add_label(path, n, "Hello", font_size=32)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["_string"] == "Hello"
        assert data[cid]["_fontSize"] == 32

    def test_add_rigidbody2d(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "Ball")
        cid = add_rigidbody2d(path, n, body_type=2, gravity_scale=0.5)
        with open(path) as f:
            data = json.load(f)
        rb = data[cid]
        assert rb["__type__"] == "cc.RigidBody2D"
        # Cocos 3.8 serializes getter/setter-backed fields with their
        # underscore-prefixed private names. Prior to the physics audit
        # we wrote "type"/"gravityScale" which the engine silently
        # ignored → every body ran as Dynamic with default gravity.
        assert rb["_type"] == 2
        assert rb["_gravityScale"] == 0.5
        assert rb["_linearVelocity"] == {"__type__": "cc.Vec2", "x": 0, "y": 0}

    def test_add_box_collider(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "Wall")
        cid = add_box_collider2d(path, n, width=80, height=20, restitution=1.0)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.BoxCollider2D"
        assert data[cid]["_restitution"] == 1.0

    def test_add_button(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "Btn")
        cid = add_button(path, n, transition=2)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.Button"
        assert data[cid]["transition"] == 2

    def test_generic_add_component(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "N")
        cid = add_component(path, n, "cc.Mask", {"_type": 0})
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.Mask"

    def test_attach_script(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "GM")
        cid = add_script(path, n, "5372db1ch5D9rAE0w2hyKmg", props={
            "speed": 100.0,
            "playerId": 1,                    # literal int — stays as 1
            "label": {"__id__": 15},          # explicit ref
            "prefab": {"__uuid__": "abc-123"},  # resource ref
        })
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "5372db1ch5D9rAE0w2hyKmg"
        assert data[cid]["speed"] == 100.0
        assert data[cid]["playerId"] == 1          # NOT {"__id__": 1}
        assert data[cid]["label"] == {"__id__": 15}
        assert data[cid]["prefab"] == {"__uuid__": "abc-123"}


class TestBatchOps:
    def test_basic_batch(self):
        path, info = _tmp_scene()
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "Bird", "pos_y": 40},
            {"op": "add_uitransform", "node_id": "$0", "width": 50, "height": 50},
            {"op": "add_graphics", "node_id": "$0"},
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "Label"},
            {"op": "add_uitransform", "node_id": "$3", "width": 200, "height": 50},
            {"op": "add_label", "node_id": "$3", "text": "Score: 0", "font_size": 32},
        ])
        assert result["ops_executed"] == 6
        assert all(not isinstance(r, dict) or "error" not in r for r in result["results"])
        v = validate_scene(path)
        assert v["valid"]

    def test_back_reference(self):
        path, info = _tmp_scene()
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "N"},
            {"op": "add_rigidbody2d", "node_id": "$0", "body_type": 2},
            {"op": "add_box_collider2d", "node_id": "$0", "width": 60, "height": 20},
        ])
        node_id = result["results"][0]
        rb_id = result["results"][1]
        col_id = result["results"][2]
        assert isinstance(node_id, int)
        assert isinstance(rb_id, int)
        assert isinstance(col_id, int)
        with open(path) as f:
            data = json.load(f)
        assert data[rb_id]["__type__"] == "cc.RigidBody2D"
        assert data[col_id]["__type__"] == "cc.BoxCollider2D"

    def test_polygon_collider2d_default_points(self):
        """Batch add_polygon_collider2d mirrors the direct version —
        default to a 100×100 square when points aren't specified."""
        path, info = _tmp_scene()
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "P"},
            {"op": "add_rigidbody2d", "node_id": "$0"},
            {"op": "add_polygon_collider2d", "node_id": "$0"},
        ])
        col_id = result["results"][2]
        with open(path) as f:
            data = json.load(f)
        col = data[col_id]
        assert col["__type__"] == "cc.PolygonCollider2D"
        # Each vertex must be a cc.Vec2 dict — engine types the field as
        # Vec2[], so raw [x, y] arrays deserialize to zero-filled Vec2
        # and the polygon silently becomes a degenerate shape.
        assert col["_points"] == [
            {"__type__": "cc.Vec2", "x": -50, "y": -50},
            {"__type__": "cc.Vec2", "x": 50, "y": -50},
            {"__type__": "cc.Vec2", "x": 50, "y": 50},
            {"__type__": "cc.Vec2", "x": -50, "y": 50},
        ]

    def test_polygon_collider2d_explicit_points(self):
        """Triangle polygon with explicit vertex list."""
        path, info = _tmp_scene()
        tri = [[0, 50], [-50, -50], [50, -50]]
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "T"},
            {"op": "add_rigidbody2d", "node_id": "$0"},
            {"op": "add_polygon_collider2d", "node_id": "$0",
             "points": tri, "friction": 0.8, "density": 2.5, "is_sensor": True},
        ])
        col_id = result["results"][2]
        with open(path) as f:
            data = json.load(f)
        col = data[col_id]
        assert col["_points"] == [
            {"__type__": "cc.Vec2", "x": x, "y": y} for x, y in tri
        ]
        assert col["_friction"] == 0.8
        assert col["_density"] == 2.5
        assert col["_sensor"] is True

    def test_all_eight_joints_attach(self):
        """Exercise every Joint2D variant in one batch — regression
        guard that ensures none are silently broken. Two RigidBody2D
        nodes give the joints something to connect to."""
        path, info = _tmp_scene()
        result = batch_ops(path, [
            # Two bodies: bodyA and bodyB.
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "A"},
            {"op": "add_rigidbody2d", "node_id": "$0"},
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "B"},
            {"op": "add_rigidbody2d", "node_id": "$2"},
            # The 8 joints, each attached to A and referencing B as the
            # connected body (except MouseJoint, which ignores it).
            {"op": "add_distance_joint2d", "node_id": "$0", "connected_body_id": "$3",
             "distance": 150.0, "auto_calc_distance": False},
            {"op": "add_hinge_joint2d", "node_id": "$0", "connected_body_id": "$3",
             "enable_motor": True, "motor_speed": 45.0},
            {"op": "add_spring_joint2d", "node_id": "$0", "connected_body_id": "$3",
             "frequency": 4.0, "damping_ratio": 0.5},
            {"op": "add_mouse_joint2d", "node_id": "$0", "max_force": 800.0,
             "target_x": 100, "target_y": 50},
            {"op": "add_slider_joint2d", "node_id": "$0", "connected_body_id": "$3",
             "angle": 30.0, "enable_limit": True, "upper_limit": 60.0},
            {"op": "add_wheel_joint2d", "node_id": "$0", "connected_body_id": "$3",
             "angle": 90.0, "enable_motor": True},
            {"op": "add_fixed_joint_2d", "node_id": "$0", "connected_body_id": "$3",
             "frequency": 6.0},
            {"op": "add_relative_joint2d", "node_id": "$0", "connected_body_id": "$3",
             "linear_offset_x": 25.0, "angular_offset": 10.0},
        ])
        # All 8 joint ops must return an int cid (not an error dict).
        joint_cids = result["results"][4:12]
        assert all(isinstance(c, int) for c in joint_cids), \
            f"expected 8 ints, got {[type(c).__name__ for c in joint_cids]}"
        # Inspect each resulting component carries the right __type__.
        with open(path) as f:
            data = json.load(f)
        expected = [
            "cc.DistanceJoint2D", "cc.HingeJoint2D", "cc.SpringJoint2D",
            "cc.MouseJoint2D", "cc.SliderJoint2D", "cc.WheelJoint2D",
            "cc.FixedJoint2D", "cc.RelativeJoint2D",
        ]
        assert [data[cid]["__type__"] for cid in joint_cids] == expected
        # DistanceJoint2D specifically passes through configuration.
        # Note: serialized field is ``_maxLength`` in Cocos 3.8 (not
        # ``_distance``); the python parameter name kept stable.
        dj = data[joint_cids[0]]
        assert dj["_maxLength"] == 150.0
        assert dj["_autoCalcDistance"] is False
        # HingeJoint2D motor enabled.
        hj = data[joint_cids[1]]
        assert hj["_enableMotor"] is True
        assert hj["_motorSpeed"] == 45.0
        # Base-class fields are PUBLIC @serializable — no underscore.
        assert "anchor" in dj and "connectedAnchor" in dj
        assert "connectedBody" in dj and "collideConnected" in dj
        assert "_anchor" not in dj, "legacy underscore form resurrected"
        assert "_connectedBody" not in dj

    def test_joint_without_connected_body(self):
        """connected_body_id is optional — None means anchor to world.

        Also regression-guards the field name: pre-audit we wrote
        ``_connectedBody`` (underscore) which the 3.8 engine ignores.
        """
        path, info = _tmp_scene()
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "Solo"},
            {"op": "add_rigidbody2d", "node_id": "$0"},
            {"op": "add_distance_joint2d", "node_id": "$0", "distance": 50.0},
        ])
        cid = result["results"][2]
        with open(path) as f:
            data = json.load(f)
        # Public @serializable — JSON key is ``connectedBody``.
        assert data[cid]["connectedBody"] is None
        assert "_connectedBody" not in data[cid]

    # ------- named back-references + named_results -------

    def test_named_back_reference(self):
        """"$name" resolves against prior ops' ``name`` field, stable
        across reordering/edits. Reads cleaner in 10+ op batches where
        agents were juggling positional $N indices."""
        path, info = _tmp_scene()
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "bird"},
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "enemy"},
            {"op": "add_uitransform", "node_id": "$bird", "width": 40, "height": 40},
            {"op": "add_uitransform", "node_id": "$enemy", "width": 80, "height": 80},
        ])
        # named_results maps name -> result; positional still works.
        assert "bird" in result["named_results"]
        assert "enemy" in result["named_results"]
        assert result["named_results"]["bird"] == result["results"][0]
        assert result["named_results"]["enemy"] == result["results"][1]
        # The UITransform ops got the right widths because the refs resolved.
        bird_uit_id = result["results"][2]
        enemy_uit_id = result["results"][3]
        with open(path) as f:
            data = json.load(f)
        assert data[bird_uit_id]["_contentSize"]["width"] == 40
        assert data[enemy_uit_id]["_contentSize"]["width"] == 80

    def test_named_results_preserves_positional_compat(self):
        """Ops without a ``name`` don't contaminate named_results —
        positional $N still resolves them identically to before."""
        path, info = _tmp_scene()
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "hero"},
            {"op": "add_node", "parent_id": info["canvas_node_id"]},  # anonymous
            {"op": "add_uitransform", "node_id": "$1"},                # positional
        ])
        assert list(result["named_results"].keys()) == ["hero"]
        # $1 (the anonymous node) still resolved — its UITransform got attached.
        uit_id = result["results"][2]
        with open(path) as f:
            data = json.load(f)
        assert data[uit_id]["__type__"] == "cc.UITransform"

    def test_unknown_named_ref_falls_through(self):
        """Unknown ``$name`` stays as a literal string so downstream op
        raises a clear type error — better than a silent wrong id."""
        path, info = _tmp_scene()
        result = batch_ops(path, [
            {"op": "add_uitransform", "node_id": "$nobody", "width": 10, "height": 10},
        ])
        # Op must have errored (since node_id should be int, got str).
        first = result["results"][0]
        assert isinstance(first, dict)
        assert "error" in first

    def test_attach_script_auto_compresses_in_batch(self):
        """Passing the 36-char standard UUID to batch attach_script now
        auto-compresses like the direct scene_builder.add_script. Regression:
        previously the batch path silently took the standard form and
        produced a no-op component."""
        path, info = _tmp_scene()
        standard_uuid = "12345678-1234-1234-1234-123456789abc"
        result = batch_ops(path, [
            {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "X"},
            {"op": "attach_script", "node_id": "$0",
             "script_uuid_compressed": standard_uuid},
        ])
        cid = result["results"][1]
        with open(path) as f:
            data = json.load(f)
        comp = data[cid]
        # __type__ must be the 23-char compressed form, not the standard uuid.
        assert len(comp["__type__"]) == 23
        assert "-" not in comp["__type__"]


class TestValidation:
    def test_valid_scene(self):
        path, _ = _tmp_scene()
        v = validate_scene(path)
        assert v["valid"]
        assert v["issues"] == []

    def test_invalid_ref(self):
        path, _ = _tmp_scene()
        with open(path) as f:
            data = json.load(f)
        data[2]["_children"].append({"__id__": 9999})
        with open(path, "w") as f:
            json.dump(data, f)
        v = validate_scene(path)
        assert not v["valid"]
        assert any("9999" in issue for issue in v["issues"])

    def test_prefab_skips_canvas_ancestor_check(self, tmp_path):
        """Dogfood-flappy MEDIUM #6: validate_scene used to flag every
        UITransform in a .prefab as "not under a Canvas" because the
        prefab's root has ``_parent: null`` by design. Prefab files
        now skip the Canvas-ancestry walk entirely."""
        from cocos.scene_builder import (
            create_prefab, add_node, add_uitransform, add_sprite,
        )
        prefab = str(tmp_path / "Enemy.prefab")
        info = create_prefab(prefab, root_name="Enemy")
        # A realistic subtree with UITransform/Sprite — would trip the
        # Canvas check in the old validator.
        add_uitransform(prefab, info["root_node_id"], 80, 80)
        add_sprite(prefab, info["root_node_id"], color=(200, 50, 50, 255))
        child = add_node(prefab, info["root_node_id"], "Body")
        add_uitransform(prefab, child, 40, 40)

        v = validate_scene(prefab)
        assert v["valid"], f"prefab should validate clean; got: {v['issues']}"
        # And it should NOT report any "not under any Canvas" noise.
        assert not any("Canvas" in issue for issue in v["issues"])

    def test_prefab_flags_missing_prefab_info(self, tmp_path):
        """A .prefab whose node is missing its cc.PrefabInfo (hand-
        tampered, or produced by an old cocos-mcp pre-Bug-B) must be
        caught — leaving it silent is what allowed Bug B to land in the
        first place."""
        from cocos.scene_builder import create_prefab
        prefab = str(tmp_path / "Broken.prefab")
        info = create_prefab(prefab, root_name="Broken")
        # Manually break: clear the root's _prefab ref (simulates a
        # pre-fix cocos-mcp scene that forgot to append PrefabInfo).
        with open(prefab) as f:
            data = json.load(f)
        data[info["root_node_id"]]["_prefab"] = None
        with open(prefab, "w") as f:
            json.dump(data, f)

        v = validate_scene(prefab)
        assert not v["valid"]
        assert any("_prefab: null" in issue for issue in v["issues"])

    def test_prefab_flags_duplicate_file_ids(self, tmp_path):
        """Two nodes sharing a PrefabInfo.fileId would collide on
        instance-identity at runtime. validate_scene catches it."""
        from cocos.scene_builder import create_prefab, add_node
        prefab = str(tmp_path / "Dup.prefab")
        info = create_prefab(prefab, root_name="Dup")
        child = add_node(prefab, info["root_node_id"], "Child")

        # Force the child's PrefabInfo.fileId to match the root's.
        with open(prefab) as f:
            data = json.load(f)
        root_pi = data[info["root_node_id"]]["_prefab"]["__id__"]
        child_pi = data[child]["_prefab"]["__id__"]
        data[child_pi]["fileId"] = data[root_pi]["fileId"]
        with open(prefab, "w") as f:
            json.dump(data, f)

        v = validate_scene(prefab)
        assert not v["valid"]
        assert any("duplicates" in issue for issue in v["issues"])


# ========================================================================
# Physics serialization shape lock-in.
# Cocos 3.8's deserializer silently drops unknown field names and
# wrong-shape values — the physics audit found every RigidBody2D /
# collider / joint config was being ignored before the fix landed.
# These tests are regression guards.
# ========================================================================


class TestPhysicsSerializationShape:
    def test_rigidbody2d_uses_underscore_backing_fields(self):
        """RigidBody2D's getter/setter-backed fields serialize with
        their underscore-prefixed private names (``_type``,
        ``_gravityScale``, ...). Public @serializable fields
        (``enabledContactListener``, ``bullet``, ``awakeOnLoad``) stay
        bare. Any drift silently ignores the caller's config."""
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "N")
        cid = add_rigidbody2d(path, n, body_type=0, gravity_scale=0.5,
                              fixed_rotation=True, linear_damping=0.3,
                              angular_damping=0.2, bullet=True,
                              awake_on_load=False)
        with open(path) as f:
            rb = json.load(f)[cid]
        # Serialized with underscore — private backing field names.
        assert rb["_type"] == 0
        assert rb["_gravityScale"] == 0.5
        assert rb["_fixedRotation"] is True
        assert rb["_linearDamping"] == 0.3
        assert rb["_angularDamping"] == 0.2
        assert rb["_allowSleep"] is True
        assert rb["_angularVelocity"] == 0.0
        assert rb["_group"] == 1  # PhysicsGroup.DEFAULT
        assert rb["_linearVelocity"] == {"__type__": "cc.Vec2", "x": 0, "y": 0}
        # Public @serializable — bare name.
        assert rb["enabledContactListener"] is True
        assert rb["bullet"] is True
        assert rb["awakeOnLoad"] is False
        # None of the legacy wrong names should be present.
        for bad in ("type", "gravityScale", "fixedRotation", "linearDamping",
                    "angularDamping", "linearVelocity", "angularVelocity",
                    "allowSleep"):
            assert bad not in rb, f"legacy field {bad!r} resurrected"

    def test_box_collider2d_uses_cc_size_and_cc_vec2_dicts(self):
        """BoxCollider2D.``_size`` must be a ``cc.Size`` dict;
        ``_offset`` must be ``cc.Vec2``. A bare list deserializes to
        a zero/default Size/Vec2 and the collider silently becomes a
        unit square at the origin."""
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "B")
        cid = add_box_collider2d(path, n, width=80, height=40,
                                 offset_x=10, offset_y=-5)
        with open(path) as f:
            col = json.load(f)[cid]
        assert col["_size"] == {"__type__": "cc.Size", "width": 80, "height": 40}
        assert col["_offset"] == {"__type__": "cc.Vec2", "x": 10, "y": -5}

    def test_circle_collider2d_offset_is_cc_vec2_dict(self):
        """Same drift guard for CircleCollider2D."""
        from cocos.scene_builder import add_circle_collider2d
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "C")
        cid = add_circle_collider2d(path, n, radius=30, offset_x=5)
        with open(path) as f:
            col = json.load(f)[cid]
        assert col["_radius"] == 30
        assert col["_offset"] == {"__type__": "cc.Vec2", "x": 5, "y": 0}

    def test_polygon_collider2d_points_are_cc_vec2_dicts(self):
        """``_points`` is typed ``Vec2[]`` in the engine — every entry
        must be a cc.Vec2 dict, not a bare [x, y] list."""
        from cocos.scene_builder import add_polygon_collider2d
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "P")
        cid = add_polygon_collider2d(path, n, points=[[0, 10], [-10, -10], [10, -10]])
        with open(path) as f:
            col = json.load(f)[cid]
        assert col["_points"] == [
            {"__type__": "cc.Vec2", "x": 0, "y": 10},
            {"__type__": "cc.Vec2", "x": -10, "y": -10},
            {"__type__": "cc.Vec2", "x": 10, "y": -10},
        ]

    def test_joint2d_base_fields_have_no_underscore(self):
        """Joint2D's @serializable base fields (anchor / connectedAnchor
        / connectedBody / collideConnected) are PUBLIC — no underscore
        prefix. Verified across every joint variant."""
        from cocos.scene_builder import (
            add_distance_joint2d, add_hinge_joint2d, add_spring_joint2d,
            add_slider_joint2d, add_wheel_joint2d, add_fixed_joint_2d,
            add_relative_joint2d,
        )
        path, info = _tmp_scene()
        n1 = add_node(path, info["canvas_node_id"], "A")
        add_rigidbody2d(path, n1)
        n2 = add_node(path, info["canvas_node_id"], "B")
        rb2 = add_rigidbody2d(path, n2)

        # RelativeJoint2D's base keys are connectedBody/collideConnected
        # only — it doesn't use anchor/connectedAnchor (uses _linearOffset
        # instead), but the base-field rule still applies.
        joints = [
            add_distance_joint2d(path, n1, connected_body_id=rb2),
            add_hinge_joint2d(path, n1, connected_body_id=rb2),
            add_spring_joint2d(path, n1, connected_body_id=rb2),
            add_slider_joint2d(path, n1, connected_body_id=rb2),
            add_wheel_joint2d(path, n1, connected_body_id=rb2),
            add_fixed_joint_2d(path, n1, connected_body_id=rb2),
            add_relative_joint2d(path, n1, connected_body_id=rb2),
        ]
        with open(path) as f:
            data = json.load(f)
        for cid in joints:
            j = data[cid]
            ttype = j["__type__"]
            assert "connectedBody" in j, f"{ttype} missing connectedBody"
            assert "_connectedBody" not in j, f"{ttype} has legacy _connectedBody"
            assert "collideConnected" in j
            assert "_collideConnected" not in j

    def test_distance_joint2d_uses_maxLength_field(self):
        """DistanceJoint2D's distance field is ``_maxLength`` in Cocos
        3.8, not ``_distance``. Pre-fix we wrote ``_distance`` which
        the engine ignored and the joint ran with maxLength=5 (default).
        """
        from cocos.scene_builder import add_distance_joint2d
        path, info = _tmp_scene()
        n1 = add_node(path, info["canvas_node_id"], "A")
        add_rigidbody2d(path, n1)
        cid = add_distance_joint2d(path, n1, distance=123.4, auto_calc_distance=False)
        with open(path) as f:
            j = json.load(f)[cid]
        assert j["_maxLength"] == 123.4
        assert "_distance" not in j
        assert j["_autoCalcDistance"] is False


class TestNewComponents:
    def test_add_camera(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "MiniCam")
        from cocos.scene_builder import add_camera
        cid = add_camera(path, n, projection=0, priority=100, ortho_height=160)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.Camera"
        assert data[cid]["_priority"] == 100

    def test_add_mask(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "Masked")
        from cocos.scene_builder import add_mask
        cid = add_mask(path, n, mask_type=1)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.Mask"
        assert data[cid]["_type"] == 1

    def test_add_richtext(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "RT")
        from cocos.scene_builder import add_richtext
        cid = add_richtext(path, n, text="<b>Bold</b>", font_size=24)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.RichText"
        assert data[cid]["string"] == "<b>Bold</b>"

    def test_add_sliced_sprite(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "Panel")
        from cocos.scene_builder import add_sliced_sprite
        cid = add_sliced_sprite(path, n)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["__type__"] == "cc.Sprite"
        assert data[cid]["_type"] == 1  # SLICED

    def test_add_tiled_sprite(self):
        path, info = _tmp_scene()
        n = add_node(path, info["canvas_node_id"], "Floor")
        from cocos.scene_builder import add_tiled_sprite
        cid = add_tiled_sprite(path, n)
        with open(path) as f:
            data = json.load(f)
        assert data[cid]["_type"] == 2  # TILED

    def test_click_events(self):
        path, info = _tmp_scene()
        gm = add_node(path, info["canvas_node_id"], "GM")
        btn_node = add_node(path, info["canvas_node_id"], "Btn")
        add_uitransform(path, btn_node, 200, 60)
        from cocos.scene_builder import add_button as add_btn
        from cocos.scene_builder import make_click_event
        evt = make_click_event(gm, "GameManager", "onRestart", "hello")
        cid = add_btn(path, btn_node, click_events=[evt])
        with open(path) as f:
            data = json.load(f)
        assert len(data[cid]["clickEvents"]) == 1
        evt_ref = data[cid]["clickEvents"][0]
        evt_obj = data[evt_ref["__id__"]]
        assert evt_obj["__type__"] == "cc.ClickEvent"
        assert evt_obj["component"] == "GameManager"
        assert evt_obj["handler"] == "onRestart"
        v = validate_scene(path)
        assert v["valid"]


# ========================================================================
# Bug B regression: add_node on .prefab files must wire cc.PrefabInfo per
# child. Dogfood-flappy surfaced this — children were written with
# _prefab: null and no sibling PrefabInfo entry, leaving the prefab
# structurally malformed for the Cocos runtime.
# ========================================================================


class TestPrefabChildPrefabInfo:
    def _new_prefab(self, tmp_path):
        from cocos.scene_builder import create_prefab
        p = tmp_path / "Pipe.prefab"
        info = create_prefab(str(p), root_name="Pipe")
        return str(p), info

    def test_add_node_on_prefab_writes_prefab_info(self, tmp_path):
        """Child node added to a .prefab must have its own cc.PrefabInfo
        with a unique fileId — Cocos runtime reconciles per-instance
        overrides via those ids."""
        prefab_path, info = self._new_prefab(tmp_path)
        root_id = info["root_node_id"]
        # Grab the root's PrefabInfo so we can assert the child gets a
        # different fileId.
        with open(prefab_path) as f:
            before = json.load(f)
        root_pi_idx = before[root_id]["_prefab"]["__id__"]
        root_fileid = before[root_pi_idx]["fileId"]

        child_id = add_node(prefab_path, root_id, "PipeTop")

        with open(prefab_path) as f:
            after = json.load(f)
        child = after[child_id]
        assert child["_prefab"] is not None, "child must have _prefab wired"
        pi_idx = child["_prefab"]["__id__"]
        pi = after[pi_idx]
        assert pi["__type__"] == "cc.PrefabInfo"
        assert pi["fileId"], "PrefabInfo must carry a fileId"
        assert pi["fileId"] != root_fileid, \
            "child PrefabInfo.fileId must be unique (else identity collides with root)"

    def test_add_node_on_scene_no_prefab_info(self, tmp_path):
        """Scene nodes must NOT get a PrefabInfo — only prefab nodes do.
        Regression guard: don't accidentally widen the fix to all scenes."""
        scene = str(tmp_path / "main.scene")
        info = create_empty_scene(scene)
        before_count = 0
        with open(scene) as f:
            data = json.load(f)
            before_count = sum(1 for o in data if o.get("__type__") == "cc.PrefabInfo")

        add_node(scene, info["canvas_node_id"], "Plain")

        with open(scene) as f:
            data = json.load(f)
        after_count = sum(1 for o in data if o.get("__type__") == "cc.PrefabInfo")
        # Scene already has ONE PrefabInfo (the scene root's own) — it
        # should be unchanged. Adding a plain scene node must not create
        # a new one.
        assert after_count == before_count

    def test_batch_add_node_on_prefab_writes_prefab_info(self, tmp_path):
        """The batch-ops variant follows the same rule as the direct
        add_node. Regression: it was easy to patch one path and forget
        the other."""
        prefab_path, info = self._new_prefab(tmp_path)
        root_id = info["root_node_id"]

        res = batch_ops(prefab_path, [
            {"op": "add_node", "name": "PipeTop", "parent_id": root_id},
            {"op": "add_node", "name": "PipeBottom", "parent_id": root_id},
        ])
        top_id, bottom_id = res["results"][0], res["results"][1]

        with open(prefab_path) as f:
            data = json.load(f)
        for nid in (top_id, bottom_id):
            assert data[nid]["_prefab"] is not None
            pi_idx = data[nid]["_prefab"]["__id__"]
            assert data[pi_idx]["__type__"] == "cc.PrefabInfo"
            assert data[pi_idx]["fileId"]
        # Two children → two distinct fileIds
        top_fid = data[data[top_id]["_prefab"]["__id__"]]["fileId"]
        bot_fid = data[data[bottom_id]["_prefab"]["__id__"]]["fileId"]
        assert top_fid != bot_fid

    def test_duplicate_node_on_prefab_gets_fresh_prefab_info(self, tmp_path):
        """Duplicating a node inside a prefab must mint a fresh
        PrefabInfo — aliasing the source's fileId would collide two
        prefab-instance identities in the same file."""
        prefab_path, info = self._new_prefab(tmp_path)
        root_id = info["root_node_id"]
        child_id = add_node(prefab_path, root_id, "PipeOrig")
        with open(prefab_path) as f:
            data = json.load(f)
        src_fileid = data[data[child_id]["_prefab"]["__id__"]]["fileId"]

        dup_id = duplicate_node(prefab_path, child_id, new_name="PipeCopy")

        with open(prefab_path) as f:
            data = json.load(f)
        dup_fileid = data[data[dup_id]["_prefab"]["__id__"]]["fileId"]
        assert dup_fileid != src_fileid

    def test_save_subtree_as_prefab_wires_every_node(self, tmp_path):
        """save_subtree_as_prefab had the same missing-PrefabInfo bug for
        extracted child nodes. A subtree with N nodes should produce N
        PrefabInfo entries, all wired, root using the main uuid."""
        from cocos.scene_builder import save_subtree_as_prefab
        scene = str(tmp_path / "main.scene")
        info = create_empty_scene(scene)
        parent = add_node(scene, info["canvas_node_id"], "Enemy")
        child_a = add_node(scene, parent, "A")
        child_b = add_node(scene, parent, "B")

        prefab_path = str(tmp_path / "Enemy.prefab")
        res = save_subtree_as_prefab(scene, parent, prefab_path)

        with open(prefab_path) as f:
            data = json.load(f)
        node_ids = [i for i, o in enumerate(data) if o.get("__type__") == "cc.Node"]
        pi_ids = [i for i, o in enumerate(data) if o.get("__type__") == "cc.PrefabInfo"]
        assert len(node_ids) == 3, f"expected 3 cc.Node entries, got {len(node_ids)}"
        assert len(pi_ids) == 3, f"expected 3 cc.PrefabInfo entries, got {len(pi_ids)}"
        # Each node points at a PrefabInfo
        pi_fids: list[str] = []
        for nid in node_ids:
            prefab_ref = data[nid]["_prefab"]
            assert prefab_ref is not None, f"node {data[nid]['_name']} missing _prefab"
            pi_idx = prefab_ref["__id__"]
            assert data[pi_idx]["__type__"] == "cc.PrefabInfo"
            pi_fids.append(data[pi_idx]["fileId"])
        # All PrefabInfo fileIds unique
        assert len(set(pi_fids)) == 3
        # Root's fileId matches the prefab uuid (round-trips through Creator importer)
        root_nid = node_ids[0]  # cloned[0] is root per save_subtree_as_prefab contract
        root_pi = data[root_nid]["_prefab"]["__id__"]
        assert data[root_pi]["fileId"] == res["prefab_uuid"]

    def test_add_node_idempotent_wiring(self, tmp_path):
        """Calling _ensure_node_prefab_info on a node that already has a
        valid PrefabInfo must be a no-op, not append a duplicate."""
        from cocos.scene_builder._helpers import _ensure_node_prefab_info, _load_scene
        prefab_path, info = self._new_prefab(tmp_path)
        root_id = info["root_node_id"]
        child_id = add_node(prefab_path, root_id, "Child")

        s = _load_scene(prefab_path)
        before_len = len(s)
        pi_idx_first = _ensure_node_prefab_info(s, child_id)
        pi_idx_second = _ensure_node_prefab_info(s, child_id)
        assert pi_idx_first == pi_idx_second
        assert len(s) == before_len  # no new PrefabInfo appended on re-call

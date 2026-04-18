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
        assert data[cid]["__type__"] == "cc.RigidBody2D"
        assert data[cid]["type"] == 2
        assert data[cid]["gravityScale"] == 0.5

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

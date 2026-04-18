"""Tests for cocos.meta_util."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.meta_util import (
    new_sprite_frame_meta,
    prefab_meta,
    scene_meta,
    script_ts_meta,
    upgrade_texture_to_sprite_frame,
)


def test_script_meta():
    m = script_ts_meta()
    assert m["importer"] == "typescript"
    assert len(m["uuid"]) == 36


def test_script_meta_custom_uuid():
    m = script_ts_meta(uuid="test-uuid-1234")
    assert m["uuid"] == "test-uuid-1234"


def test_scene_meta():
    m = scene_meta()
    assert m["importer"] == "scene"
    assert m["files"] == [".json"]


def test_prefab_meta():
    m = prefab_meta(sync_node_name="Player")
    assert m["importer"] == "prefab"
    assert m["userData"]["syncNodeName"] == "Player"


def test_sprite_frame_meta():
    # Create a tiny 2x2 PNG for testing
    from PIL import Image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGBA", (64, 32), (255, 0, 0, 255))
        img.save(f.name)
        m = new_sprite_frame_meta(f.name)

    assert m["importer"] == "image"
    assert "6c48a" in m["subMetas"]  # texture
    assert "f9941" in m["subMetas"]  # sprite-frame
    assert m["userData"]["type"] == "sprite-frame"

    sf = m["subMetas"]["f9941"]
    assert sf["userData"]["width"] == 64
    assert sf["userData"]["height"] == 32
    assert sf["userData"]["rawWidth"] == 64


def test_upgrade_texture_to_sprite_frame():
    from PIL import Image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGBA", (128, 128))
        img.save(f.name)
        png_path = f.name

    # Write a texture-only meta (simulating what Cocos CLI auto-generates)
    texture_meta = {
        "ver": "1.0.27",
        "importer": "image",
        "imported": True,
        "uuid": "test-uuid-upgrade",
        "files": [".json", ".png"],
        "subMetas": {
            "6c48a": {
                "importer": "texture",
                "uuid": "test-uuid-upgrade@6c48a",
                "displayName": "test",
                "id": "6c48a",
                "name": "texture",
                "ver": "1.0.22",
                "imported": True,
                "files": [".json"],
                "subMetas": {},
                "userData": {},
            }
        },
        "userData": {
            "type": "texture",
            "hasAlpha": True,
            "redirect": "test-uuid-upgrade@6c48a",
        },
    }
    meta_path = f"{png_path}.meta"
    with open(meta_path, "w") as f:
        json.dump(texture_meta, f)

    result = upgrade_texture_to_sprite_frame(meta_path)
    assert "f9941" in result["subMetas"]
    assert result["userData"]["type"] == "sprite-frame"

    # Idempotent
    result2 = upgrade_texture_to_sprite_frame(meta_path)
    assert result2["subMetas"]["f9941"]["uuid"] == result["subMetas"]["f9941"]["uuid"]

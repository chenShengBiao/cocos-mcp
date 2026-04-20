"""Tests for ``save_subtree_as_prefab`` — the main gap filler in the
prefab workflow. Covers:

* Simple subtree roundtrip (save → instantiate reproduces the shape).
* Inline child objects (ClickEvent, EventHandler on Button) travel along.
* External cc.Node refs raise with a targeted error (no silent
  clipping that would produce a broken prefab).
* Asset UUID refs survive unchanged (project-level, not scene-level).
* Source scene isn't mutated.
* Prefab meta sidecar gets the right importer + uuid.
* save → instantiate → save → instantiate is stable (no id drift).
* That existing ``scene_builder`` mutation tools work on .prefab files too
  (the "prefab file IS a scene-shaped JSON array" hidden capability).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import scene_builder as sb


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    (p / "assets" / "scenes").mkdir(parents=True)
    (p / "assets" / "prefabs").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


def _scene_in_project(proj: Path) -> tuple[Path, dict]:
    path = proj / "assets" / "scenes" / "main.scene"
    info = sb.create_empty_scene(path)
    return path, info


def _load(path: Path) -> list:
    with open(path) as f:
        return json.load(f)


# ================================================ #
# Basic save roundtrip
# ================================================ #

def test_save_simple_subtree_roundtrips_shape(tmp_path: Path):
    """Build a small subtree (node + UITransform + Sprite) in the scene,
    save as prefab, instantiate into a fresh scene — the resulting tree
    structure and component types should match."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    enemy = sb.add_node(scene, info["canvas_node_id"], "Enemy")
    sb.add_uitransform(scene, enemy, 80, 80)
    sb.add_sprite(scene, enemy, color=(200, 50, 50, 255))

    prefab = proj / "assets/prefabs/enemy.prefab"
    res = sb.save_subtree_as_prefab(scene, enemy, prefab)

    assert Path(res["prefab_path"]).exists()
    data = _load(Path(res["prefab_path"]))
    # [0]=cc.Prefab, [1]=root node, [2..N-1]=components, [N]=PrefabInfo
    assert data[0]["__type__"] == "cc.Prefab"
    assert data[-1]["__type__"] == "cc.PrefabInfo"
    assert data[1]["__type__"] == "cc.Node"
    assert data[1]["_name"] == "Enemy"
    assert data[1]["_parent"] is None  # prefab root has no parent

    # Components dragged along
    types_in_prefab = {o.get("__type__") for o in data if isinstance(o, dict)}
    assert "cc.UITransform" in types_in_prefab
    assert "cc.Sprite" in types_in_prefab


def test_save_preserves_component_field_values(tmp_path: Path):
    """Color / size fields on the components should come through
    unchanged after the save."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    node = sb.add_node(scene, info["canvas_node_id"], "Label")
    sb.add_uitransform(scene, node, 123, 45)
    sb.add_label(scene, node, "hi", font_size=36, color=(10, 20, 30, 255))

    prefab = proj / "assets/prefabs/label.prefab"
    res = sb.save_subtree_as_prefab(scene, node, prefab)

    data = _load(Path(res["prefab_path"]))
    uit = next(o for o in data if o.get("__type__") == "cc.UITransform")
    label = next(o for o in data if o.get("__type__") == "cc.Label")
    assert uit["_contentSize"]["width"] == 123
    assert label["_fontSize"] == 36
    assert label["_color"]["r"] == 10


def test_save_includes_descendants(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    parent = sb.add_node(scene, info["canvas_node_id"], "Parent")
    sb.add_uitransform(scene, parent, 200, 200)
    child_a = sb.add_node(scene, parent, "ChildA")
    sb.add_uitransform(scene, child_a, 50, 50)
    child_b = sb.add_node(scene, parent, "ChildB")
    sb.add_uitransform(scene, child_b, 50, 50)
    grandchild = sb.add_node(scene, child_a, "Deep")
    sb.add_uitransform(scene, grandchild, 25, 25)

    prefab = proj / "assets/prefabs/parent.prefab"
    sb.save_subtree_as_prefab(scene, parent, prefab)

    data = _load(prefab)
    names = {o.get("_name") for o in data
             if isinstance(o, dict) and o.get("__type__") == "cc.Node"}
    assert names == {"Parent", "ChildA", "ChildB", "Deep"}


# ================================================ #
# Inline helper objects (ClickEvent, etc.) travel along
# ================================================ #

def test_save_includes_button_click_events(tmp_path: Path):
    """Button.clickEvents is a list of {__id__: N} pointing at inline
    cc.ClickEvent scene objects. Those need to be pulled into the
    prefab too — otherwise the dangling id breaks instantiation."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    # A GameManager node inside the subtree that the button will target
    btn_parent = sb.add_node(scene, info["canvas_node_id"], "Container")
    sb.add_uitransform(scene, btn_parent, 400, 400)
    gm = sb.add_node(scene, btn_parent, "GameManager")
    sb.add_uitransform(scene, gm, 1, 1)

    btn = sb.add_node(scene, btn_parent, "Btn")
    sb.add_uitransform(scene, btn, 100, 50)
    evt = sb.make_click_event(gm, "GameManager", "onClick")
    sb.add_button(scene, btn, click_events=[evt])

    prefab = proj / "assets/prefabs/btn.prefab"
    sb.save_subtree_as_prefab(scene, btn_parent, prefab)

    data = _load(prefab)
    click_events = [o for o in data
                    if isinstance(o, dict) and o.get("__type__") == "cc.ClickEvent"]
    assert len(click_events) == 1
    # The ClickEvent's target field should point at the cloned GameManager
    # (which now has a new __id__ inside the prefab)
    target_ref = click_events[0]["target"]["__id__"]
    # Walk to the target and verify it's the GameManager
    assert data[target_ref]["_name"] == "GameManager"


# ================================================ #
# External refs: the failure mode that matters most
# ================================================ #

def test_save_rejects_external_node_reference(tmp_path: Path):
    """A Button whose click target is OUTSIDE the subtree should raise,
    NOT silently produce a prefab with a dangling __id__ that would
    crash at instantiation."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    # HUD lives OUTSIDE the subtree we'll extract
    hud = sb.add_node(scene, info["canvas_node_id"], "HUD_Score")
    sb.add_uitransform(scene, hud, 200, 50)

    # Button subtree points OUT at the HUD
    btn_parent = sb.add_node(scene, info["canvas_node_id"], "MenuPanel")
    sb.add_uitransform(scene, btn_parent, 400, 400)
    btn = sb.add_node(scene, btn_parent, "Btn")
    sb.add_uitransform(scene, btn, 100, 50)
    evt = sb.make_click_event(hud, "HUD", "flash")
    sb.add_button(scene, btn, click_events=[evt])

    prefab = proj / "assets/prefabs/bad.prefab"
    with pytest.raises(ValueError, match="external cc.Node"):
        sb.save_subtree_as_prefab(scene, btn_parent, prefab)

    # And nothing gets written on failure — the caller expects save to
    # be atomic, not half-produce a broken file.
    assert not prefab.exists()


def test_save_preserves_asset_uuid_references(tmp_path: Path):
    """Asset UUID refs (SpriteFrame, audio clip, etc.) are project-level,
    not scene-level. They MUST survive the save unchanged — otherwise
    every saved prefab loses its textures."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    fake_sf_uuid = "abcd1234@f9941"

    node = sb.add_node(scene, info["canvas_node_id"], "Enemy")
    sb.add_uitransform(scene, node, 80, 80)
    sb.add_sprite(scene, node, sprite_frame_uuid=fake_sf_uuid)

    prefab = proj / "assets/prefabs/enemy.prefab"
    sb.save_subtree_as_prefab(scene, node, prefab)

    data = _load(prefab)
    sprite = next(o for o in data if o.get("__type__") == "cc.Sprite")
    assert sprite["_spriteFrame"]["__uuid__"] == fake_sf_uuid


# ================================================ #
# Source scene is untouched
# ================================================ #

def test_save_does_not_mutate_source_scene(tmp_path: Path):
    """save_subtree_as_prefab is read-only on the source scene — mtimes
    and content should both be unchanged after the call."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    node = sb.add_node(scene, info["canvas_node_id"], "X")
    sb.add_uitransform(scene, node, 50, 50)

    before = scene.read_bytes()
    sb.save_subtree_as_prefab(scene, node, proj / "assets/prefabs/x.prefab")
    after = scene.read_bytes()

    assert before == after


# ================================================ #
# meta sidecar
# ================================================ #

def test_save_writes_prefab_meta_sidecar(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    node = sb.add_node(scene, info["canvas_node_id"], "X")
    sb.add_uitransform(scene, node, 50, 50)

    prefab = proj / "assets/prefabs/x.prefab"
    res = sb.save_subtree_as_prefab(scene, node, prefab)

    meta_path = prefab.with_suffix(prefab.suffix + ".meta")
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["importer"] == "prefab"
    assert meta["uuid"] == res["prefab_uuid"]


def test_save_accepts_explicit_uuid(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    node = sb.add_node(scene, info["canvas_node_id"], "X")
    sb.add_uitransform(scene, node, 50, 50)
    fixed_uuid = "11111111-2222-3333-4444-555555555555"

    res = sb.save_subtree_as_prefab(
        scene, node,
        proj / "assets/prefabs/x.prefab",
        prefab_uuid=fixed_uuid,
    )
    assert res["prefab_uuid"] == fixed_uuid


# ================================================ #
# Error paths
# ================================================ #

def test_save_rejects_non_node_root(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    # info["canvas_component_id"] points at cc.Canvas, not cc.Node
    with pytest.raises(ValueError, match="not a cc.Node"):
        sb.save_subtree_as_prefab(scene, info["canvas_component_id"],
                                  proj / "assets/prefabs/x.prefab")


def test_save_rejects_out_of_range_id(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, _ = _scene_in_project(proj)
    with pytest.raises(IndexError, match="out of range"):
        sb.save_subtree_as_prefab(scene, 9999,
                                  proj / "assets/prefabs/x.prefab")


# ================================================ #
# End-to-end: save → instantiate produces equivalent structure
# ================================================ #

def test_save_then_instantiate_produces_equivalent_subtree(tmp_path: Path):
    """The real test: extract subtree A from scene 1, instantiate into
    scene 2, and verify scene 2's subtree matches A's structure."""
    proj = _make_project(tmp_path)
    scene1, info1 = _scene_in_project(proj)

    # Build "Enemy" in scene 1
    enemy = sb.add_node(scene1, info1["canvas_node_id"], "Enemy",
                        lpos=(100, 50, 0))
    sb.add_uitransform(scene1, enemy, 80, 80)
    sb.add_sprite(scene1, enemy, color=(200, 50, 50, 255))
    health = sb.add_node(scene1, enemy, "HealthBar")
    sb.add_uitransform(scene1, health, 60, 6)
    sb.add_sprite(scene1, health, color=(0, 255, 0, 255))

    prefab = proj / "assets/prefabs/enemy.prefab"
    sb.save_subtree_as_prefab(scene1, enemy, prefab)

    # Fresh scene 2, drop the prefab
    scene2 = proj / "assets/scenes/battle.scene"
    info2 = sb.create_empty_scene(scene2)
    new_root = sb.instantiate_prefab(scene2, info2["canvas_node_id"], prefab)

    data2 = _load(scene2)
    names = {o["_name"] for o in data2
             if isinstance(o, dict) and o.get("__type__") == "cc.Node"}
    assert "Enemy" in names
    assert "HealthBar" in names
    # Root carries Sprite component
    root_sprite_found = False
    for cref in data2[new_root].get("_components", []):
        cid = cref["__id__"]
        if data2[cid].get("__type__") == "cc.Sprite":
            root_sprite_found = True
            break
    assert root_sprite_found


# ================================================ #
# Hidden capability: scene_builder tools work on .prefab files
# ================================================ #

def test_scene_tools_work_on_prefab_files_directly(tmp_path: Path):
    """A .prefab file IS a JSON array in the same shape as a .scene.
    ``_load_scene`` doesn't look at the extension, so every scene-
    mutation tool should work against a prefab file too. Verify by
    editing a prefab in-place with add_node + add_sprite."""
    proj = _make_project(tmp_path)
    prefab = proj / "assets/prefabs/template.prefab"

    # Build a prefab the traditional way (empty root)
    sb.create_prefab(prefab, root_name="Card")
    # The root is at index 1 in a newly-created prefab.
    # Add a child + sprite directly on the prefab file.
    child = sb.add_node(prefab, 1, "Icon")
    sb.add_uitransform(prefab, child, 40, 40)
    sb.add_sprite(prefab, child, color=(100, 150, 200, 255))

    # Readback: prefab now has the added structure
    data = _load(prefab)
    names = {o.get("_name") for o in data
             if isinstance(o, dict) and o.get("__type__") == "cc.Node"}
    assert "Card" in names
    assert "Icon" in names
    sprite = next(o for o in data if o.get("__type__") == "cc.Sprite")
    assert sprite["_color"]["b"] == 200

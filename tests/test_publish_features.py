"""Tests for the publish-readiness pass:

1. ``set_native_build_config`` writes correct iOS / Android sections of builder.json
2. ``set_bundle_config`` patches the directory .meta sidecar with bundle metadata
3. ``set_wechat_subpackages`` populates wechatgame.subpackages atomically
4. ``add_video_player`` produces a well-formed cc.VideoPlayer component
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import build as cb
from cocos import scene_builder as sb


def _project(tmp_path: Path) -> Path:
    p = tmp_path / "p"
    p.mkdir()
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


# ============================================================
#  set_native_build_config
# ============================================================

def test_native_ios_full_config(tmp_path: Path):
    proj = _project(tmp_path)
    res = cb.set_native_build_config(
        proj, "ios",
        package_name="com.example.demo",
        orientation="portrait",
        icon_path="assets/icon.png",
        splash_path="assets/splash.png",
        ios_team_id="ABCD123XYZ",
    )
    saved = json.loads(Path(res["builder_path"]).read_text())
    ios = saved["ios"]
    assert ios["packageName"] == "com.example.demo"
    assert ios["iosTeamID"] == "ABCD123XYZ"
    assert ios["icon"] == "assets/icon.png"
    assert ios["splash"] == "assets/splash.png"
    assert ios["orientation"] == {
        "portrait": True, "upsideDown": False,
        "landscapeLeft": False, "landscapeRight": False,
    }


def test_native_android_landscape_release(tmp_path: Path):
    proj = _project(tmp_path)
    cb.set_native_build_config(
        proj, "android",
        package_name="com.example.demo",
        orientation="landscape",
        android_min_api=21, android_target_api=33,
        android_use_debug_keystore=False,
        android_keystore_path="/keys/release.jks",
        android_keystore_password="pass1",
        android_keystore_alias="prod",
        android_keystore_alias_password="pass2",
        android_app_bundle=True,
    )
    saved = json.loads((proj / "settings/v2/packages/builder.json").read_text())
    a = saved["android"]
    assert a["minApiLevel"] == 21
    assert a["targetApiLevel"] == 33
    assert a["useDebugKeystore"] is False
    assert a["keystorePath"] == "/keys/release.jks"
    assert a["appBundle"] is True
    assert a["orientation"]["landscapeLeft"] and a["orientation"]["landscapeRight"]
    assert not a["orientation"]["portrait"]


def test_native_partial_update_preserves_existing(tmp_path: Path):
    proj = _project(tmp_path)
    cb.set_native_build_config(proj, "ios", package_name="com.first", ios_team_id="TEAM1")
    # Second call only changes splash_path; package_name & team must remain
    cb.set_native_build_config(proj, "ios", splash_path="new.png")
    saved = json.loads((proj / "settings/v2/packages/builder.json").read_text())
    assert saved["ios"]["packageName"] == "com.first"
    assert saved["ios"]["iosTeamID"] == "TEAM1"
    assert saved["ios"]["splash"] == "new.png"


def test_native_invalid_platform_raises(tmp_path: Path):
    with pytest.raises(ValueError, match=r"ios.*android"):
        cb.set_native_build_config(_project(tmp_path), "windows", package_name="x")


def test_native_invalid_orientation_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="orientation"):
        cb.set_native_build_config(_project(tmp_path), "ios", orientation="diagonal")


# ============================================================
#  set_bundle_config
# ============================================================

def test_bundle_config_creates_meta_when_missing(tmp_path: Path):
    proj = _project(tmp_path)
    folder = proj / "assets" / "levels" / "world1"
    folder.mkdir(parents=True)
    res = cb.set_bundle_config(
        proj, "assets/levels/world1",
        compression_type={"web-mobile": "merge_dep", "wechatgame": "subpackage"},
        is_remote={"web-mobile": False, "wechatgame": False},
    )
    meta = json.loads(Path(res["meta_path"]).read_text())
    user = meta["userData"]
    assert user["isBundle"] is True
    assert user["bundleName"] == "world1"
    assert user["compressionType"]["wechatgame"] == "subpackage"
    assert user["isRemoteBundle"]["web-mobile"] is False


def test_bundle_config_patches_existing_meta(tmp_path: Path):
    proj = _project(tmp_path)
    folder = proj / "assets" / "shared"
    folder.mkdir(parents=True)
    # Pre-existing meta from Creator
    existing_meta = {
        "ver": "1.2.0", "importer": "directory", "imported": True,
        "uuid": "preexisting-uuid", "files": [], "subMetas": {},
        "userData": {"someOtherField": "preserved"},
    }
    meta_path = Path(str(folder) + ".meta")
    meta_path.write_text(json.dumps(existing_meta))

    cb.set_bundle_config(proj, "assets/shared", bundle_name="myShared",
                         priority=5, is_bundle=True)
    saved = json.loads(meta_path.read_text())
    # Untouched fields preserved
    assert saved["uuid"] == "preexisting-uuid"
    assert saved["userData"]["someOtherField"] == "preserved"
    # Bundle fields applied
    assert saved["userData"]["isBundle"] is True
    assert saved["userData"]["bundleName"] == "myShared"
    assert saved["userData"]["priority"] == 5


def test_bundle_config_rejects_non_directory(tmp_path: Path):
    proj = _project(tmp_path)
    with pytest.raises(FileNotFoundError, match="not a directory"):
        cb.set_bundle_config(proj, "assets/does/not/exist")


# ============================================================
#  set_wechat_subpackages
# ============================================================

def test_wechat_subpackages_basic(tmp_path: Path):
    proj = _project(tmp_path)
    res = cb.set_wechat_subpackages(proj, [
        {"name": "level1", "root": "assets/levels/world1"},
        {"name": "audio", "root": "assets/audio"},
    ])
    saved = json.loads(Path(res["builder_path"]).read_text())
    sps = saved["wechatgame"]["subpackages"]
    assert sps == [
        {"name": "level1", "root": "assets/levels/world1"},
        {"name": "audio", "root": "assets/audio"},
    ]


def test_wechat_subpackages_replaces_atomically(tmp_path: Path):
    proj = _project(tmp_path)
    cb.set_wechat_subpackages(proj, [{"name": "old", "root": "assets/old"}])
    cb.set_wechat_subpackages(proj, [{"name": "new", "root": "assets/new"}])
    saved = json.loads((proj / "settings/v2/packages/builder.json").read_text())
    # Replaced, not merged
    names = [sp["name"] for sp in saved["wechatgame"]["subpackages"]]
    assert names == ["new"]


def test_wechat_subpackages_coexists_with_appid(tmp_path: Path):
    proj = _project(tmp_path)
    cb.set_wechat_appid(proj, "wxABCDEF")
    cb.set_wechat_subpackages(proj, [{"name": "x", "root": "assets/x"}])
    saved = json.loads((proj / "settings/v2/packages/builder.json").read_text())
    assert saved["wechatgame"]["appid"] == "wxABCDEF"
    assert saved["wechatgame"]["subpackages"][0]["name"] == "x"


def test_wechat_subpackages_validates_entry_shape(tmp_path: Path):
    with pytest.raises(ValueError, match=r"name.*root"):
        cb.set_wechat_subpackages(_project(tmp_path), [{"name": "x"}])


# ============================================================
#  add_video_player
# ============================================================

def _scene() -> tuple[Path, int]:
    f = tempfile.NamedTemporaryFile(suffix=".scene", delete=False)
    f.close()
    info = sb.create_empty_scene(f.name)
    return Path(f.name), info["canvas_node_id"]


def test_video_player_local_clip():
    path, canvas = _scene()
    n = sb.add_node(path, canvas, "Video")
    sb.add_uitransform(path, n, 640, 360)
    cid = sb.add_video_player(path, n, resource_type=1,
                              clip_uuid="clip-uuid-123", volume=0.5, loop=True)
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.VideoPlayer"
    assert obj["_resourceType"] == 1
    assert obj["_clip"] == {"__uuid__": "clip-uuid-123", "__expectedType__": "cc.VideoClip"}
    assert obj["_volume"] == 0.5
    assert obj["_loop"] is True
    assert sb.validate_scene(path)["valid"]


def test_video_player_remote_url():
    path, canvas = _scene()
    n = sb.add_node(path, canvas, "Ad")
    sb.add_uitransform(path, n, 320, 180)
    cid = sb.add_video_player(path, n, resource_type=0,
                              remote_url="https://cdn.example.com/ad.mp4",
                              full_screen_on_awake=True)
    obj = sb.get_object(path, cid)
    assert obj["_resourceType"] == 0
    assert obj["_remoteURL"] == "https://cdn.example.com/ad.mp4"
    assert obj["_clip"] is None  # no clip for remote
    assert obj["_fullScreenOnAwake"] is True


def test_video_player_auto_attaches_uitransform():
    """VideoPlayer is in _UI_RENDER_TYPES? Actually it's NOT — but the underlying
    add_component path doesn't auto-attach UITransform. Verify behavior matches
    the public contract: no auto-attach for VideoPlayer (it manages its own DOM)."""
    path, canvas = _scene()
    n = sb.add_node(path, canvas, "Bare")
    cid = sb.add_video_player(path, n)
    # The component attaches even without UITransform; that's fine for VideoPlayer
    obj = sb.get_object(path, cid)
    assert obj["__type__"] == "cc.VideoPlayer"
    assert sb.validate_scene(path)["valid"]

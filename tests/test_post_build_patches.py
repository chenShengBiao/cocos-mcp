"""Tests for the post-build patch registry + apply engine.

Three patch ``kind`` s (json_set / regex_sub / copy_from) × CRUD on the
registry (register / list / remove) × integration into cli_build.

The registry file is our own (``settings/v2/packages/post-build-patches.json``)
so these tests don't need a real Cocos install — just a project skeleton.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import build as cb
from cocos import project as cp
from cocos.project import post_build_patches as pbp


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    (p / "assets").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


def _seed_build_file(project: Path, platform: str, rel: str, content: str | bytes) -> Path:
    """Drop a file under build/<platform>/<rel> so patches have something
    to act on. Real builds would have produced this via cocos_build."""
    target = project / "build" / platform / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content)
    return target


# ==================================================== #
#  Registration + validation                           #
# ==================================================== #

def test_register_appends_by_default(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "style.css", "kind": "regex_sub",
         "find": "a", "replace": "b"},
    ])
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "index.html", "kind": "regex_sub",
         "find": "c", "replace": "d"},
    ])
    listing = cp.list_post_build_patches(str(proj))
    assert len(listing["patches"]) == 2
    assert [p["file"] for p in listing["patches"]] == ["style.css", "index.html"]


def test_register_replace_mode_wipes_prior(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "a.txt", "kind": "regex_sub",
         "find": "x", "replace": "y"},
    ])
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "b.txt", "kind": "regex_sub",
         "find": "z", "replace": "w"},
    ], mode="replace")
    listing = cp.list_post_build_patches(str(proj))
    assert len(listing["patches"]) == 1
    assert listing["patches"][0]["file"] == "b.txt"


def test_register_atomically_fails_on_invalid_patch(tmp_path: Path):
    """Even if the bad patch is second in the list, nothing should get written."""
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError):
        cp.register_post_build_patches(str(proj), [
            {"platform": "web-mobile", "file": "ok.txt", "kind": "regex_sub",
             "find": "a", "replace": "b"},
            {"platform": "web-mobile", "file": "bad.txt", "kind": "regex_sub",
             "find": "[unclosed", "replace": ""},  # invalid regex
        ])
    # Registry file should not exist yet (first-ever register failed)
    assert not (proj / "settings" / "v2" / "packages" / "post-build-patches.json").exists()


def test_register_rejects_absolute_file_path(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError, match="relative"):
        cp.register_post_build_patches(str(proj), [
            {"platform": "web-mobile", "file": "/etc/passwd", "kind": "regex_sub",
             "find": "a", "replace": "b"},
        ])


def test_register_rejects_parent_traversal(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError, match=r"'\.\.'"):
        cp.register_post_build_patches(str(proj), [
            {"platform": "web-mobile", "file": "../outside.txt", "kind": "regex_sub",
             "find": "a", "replace": "b"},
        ])


def test_register_rejects_unknown_kind(tmp_path: Path):
    proj = _make_project(tmp_path)
    with pytest.raises(ValueError, match="kind"):
        cp.register_post_build_patches(str(proj), [
            {"platform": "web-mobile", "file": "a.txt", "kind": "magic"},
        ])


# ==================================================== #
#  Remove semantics                                    #
# ==================================================== #

def test_remove_by_platform_filter(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "a.txt", "kind": "regex_sub",
         "find": "a", "replace": "b"},
        {"platform": "wechatgame", "file": "b.txt", "kind": "regex_sub",
         "find": "c", "replace": "d"},
        {"platform": "web-mobile", "file": "c.txt", "kind": "regex_sub",
         "find": "e", "replace": "f"},
    ])
    res = cp.remove_post_build_patches(str(proj), platform="web-mobile")
    assert res["removed"] == 2
    assert res["remaining"] == 1
    remaining = cp.list_post_build_patches(str(proj))["patches"]
    assert remaining[0]["platform"] == "wechatgame"


def test_remove_noop_when_no_filter(tmp_path: Path):
    """Calling with all None must NOT wipe the list — safety guard."""
    proj = _make_project(tmp_path)
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "a.txt", "kind": "regex_sub",
         "find": "a", "replace": "b"},
    ])
    res = cp.remove_post_build_patches(str(proj))
    assert res["removed"] == 0
    assert res["remaining"] == 1


def test_remove_by_indices(tmp_path: Path):
    proj = _make_project(tmp_path)
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "a", "kind": "regex_sub",
         "find": "a", "replace": "b"},
        {"platform": "web-mobile", "file": "b", "kind": "regex_sub",
         "find": "a", "replace": "b"},
        {"platform": "web-mobile", "file": "c", "kind": "regex_sub",
         "find": "a", "replace": "b"},
    ])
    cp.remove_post_build_patches(str(proj), indices=[0, 2])
    remaining = cp.list_post_build_patches(str(proj))["patches"]
    assert [p["file"] for p in remaining] == ["b"]


# ==================================================== #
#  Apply — json_set                                    #
# ==================================================== #

def test_apply_json_set_simple(tmp_path: Path):
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "wechatgame", "project.config.json",
                     json.dumps({"appid": "default"}))
    cp.register_post_build_patches(str(proj), [
        {"platform": "wechatgame", "file": "project.config.json",
         "kind": "json_set", "path": "appid",
         "value": "wx000000000000demo"},
    ])
    res = cp.apply_post_build_patches(str(proj), "wechatgame")
    assert res["ok"]
    assert len(res["applied"]) == 1
    with open(proj / "build" / "wechatgame" / "project.config.json") as f:
        data = json.load(f)
    assert data["appid"] == "wx000000000000demo"


def test_apply_json_set_creates_intermediate_dicts(tmp_path: Path):
    """launch.launchScene on a brand-new settings.json should materialize
    the ``launch`` dict."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "src/settings.json", json.dumps({}))
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "src/settings.json",
         "kind": "json_set", "path": "launch.launchScene",
         "value": "Home.scene"},
    ])
    cp.apply_post_build_patches(str(proj), "web-mobile")
    with open(proj / "build" / "web-mobile" / "src" / "settings.json") as f:
        data = json.load(f)
    assert data["launch"]["launchScene"] == "Home.scene"


def test_apply_json_set_refuses_to_traverse_non_dict(tmp_path: Path):
    """If ``foo`` is a string, setting ``foo.bar`` should raise instead
    of overwriting the string."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "settings.json",
                     json.dumps({"launch": "not-a-dict"}))
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "settings.json",
         "kind": "json_set", "path": "launch.launchScene",
         "value": "Home.scene"},
    ])
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert not res["ok"]
    assert "non-dict" in res["errors"][0]["message"].lower()


# ==================================================== #
#  Apply — regex_sub                                   #
# ==================================================== #

def test_apply_regex_sub_replaces_body_background(tmp_path: Path):
    """The motivating example from the design doc: CSS body bg color."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "style.css",
                     "html, body { margin: 0; background: #ffffff; }\n")
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "style.css",
         "kind": "regex_sub",
         "find": r"background:\s*#[0-9a-fA-F]{3,6}",
         "replace": "background: #1c2833"},
    ])
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert res["ok"]
    content = (proj / "build" / "web-mobile" / "style.css").read_text()
    assert "#1c2833" in content
    assert "#ffffff" not in content


def test_apply_regex_sub_errors_when_pattern_doesnt_match(tmp_path: Path):
    """A drifted regex is a silent regression we want to surface."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "style.css", "body { color: red; }\n")
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "style.css",
         "kind": "regex_sub",
         "find": r"purple", "replace": "blue"},
    ])
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert not res["ok"]
    assert "didn't match" in res["errors"][0]["message"]


# ==================================================== #
#  Apply — copy_from                                   #
# ==================================================== #

def test_apply_copy_from_overwrites_target(tmp_path: Path):
    proj = _make_project(tmp_path)
    # Source — a file inside the project we want to copy over the build output
    custom_html = proj / "custom" / "index.html"
    custom_html.parent.mkdir()
    custom_html.write_text("<!-- custom -->\n")
    # Seed the default target
    _seed_build_file(proj, "web-mobile", "index.html", "<!-- default -->\n")
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "index.html",
         "kind": "copy_from", "source": "custom/index.html"},
    ])
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert res["ok"]
    assert (proj / "build" / "web-mobile" / "index.html").read_text() == "<!-- custom -->\n"


def test_apply_copy_from_errors_if_source_missing(tmp_path: Path):
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "index.html", "<html/>")
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "index.html",
         "kind": "copy_from", "source": "nope/nothing.html"},
    ])
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert not res["ok"]
    assert "doesn't exist" in res["errors"][0]["message"].lower()


# ==================================================== #
#  Apply — platform filtering + dry_run                #
# ==================================================== #

def test_apply_filters_by_platform(tmp_path: Path):
    """A wechatgame patch must not run when applying web-mobile."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "wechatgame", "project.config.json",
                     json.dumps({"appid": "default"}))
    cp.register_post_build_patches(str(proj), [
        {"platform": "wechatgame", "file": "project.config.json",
         "kind": "json_set", "path": "appid", "value": "wx123"},
    ])
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert res["ok"]
    assert res["applied"] == []
    # File must remain untouched
    with open(proj / "build" / "wechatgame" / "project.config.json") as f:
        assert json.load(f)["appid"] == "default"


def test_apply_skips_patches_for_missing_files(tmp_path: Path):
    """If a patch targets a file the build didn't emit this time, skip
    rather than raise — the build itself is still valid."""
    proj = _make_project(tmp_path)
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "only-in-some-builds.json",
         "kind": "json_set", "path": "x", "value": 1},
    ])
    # build/ dir doesn't even exist here — simulates build cleaned / never ran
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert res["ok"]
    assert res["applied"] == []
    assert len(res["skipped"]) == 1
    assert res["skipped"][0]["file"] == "only-in-some-builds.json"


def test_apply_dry_run_doesnt_touch_filesystem(tmp_path: Path):
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "wechatgame", "project.config.json",
                     json.dumps({"appid": "default"}))
    cp.register_post_build_patches(str(proj), [
        {"platform": "wechatgame", "file": "project.config.json",
         "kind": "json_set", "path": "appid", "value": "wx-dry-run"},
    ])
    res = cp.apply_post_build_patches(str(proj), "wechatgame", dry_run=True)
    assert res["ok"]
    assert res["dry_run"] is True
    # File still has the original value
    with open(proj / "build" / "wechatgame" / "project.config.json") as f:
        assert json.load(f)["appid"] == "default"


def test_apply_stops_on_first_error_no_cascade(tmp_path: Path):
    """A failed patch shouldn't cause subsequent patches on the same file
    to compound the damage."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "style.css", "body{}")
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "style.css",
         "kind": "regex_sub", "find": "nonexistent", "replace": "x"},
        # If we didn't stop, this one would also run. style.css contents
        # shouldn't change — the first patch left it untouched because
        # its find didn't match.
        {"platform": "web-mobile", "file": "style.css",
         "kind": "regex_sub", "find": "body", "replace": "XXX"},
    ])
    res = cp.apply_post_build_patches(str(proj), "web-mobile")
    assert not res["ok"]
    assert len(res["errors"]) == 1
    # The second patch should NOT have run (first failure stops the batch)
    assert (proj / "build" / "web-mobile" / "style.css").read_text() == "body{}"


# ==================================================== #
#  Integration with cli_build                          #
# ==================================================== #

def test_cli_build_auto_applies_patches_on_success(tmp_path: Path, monkeypatch):
    """The golden path: cocos_build succeeds → patches run automatically
    → the edit survives into the build output."""
    proj = _make_project(tmp_path)

    # Pre-populate the file Cocos would normally generate so _seed simulates
    # the build. cli_build checks build_dir exists + is non-empty for success.
    _seed_build_file(proj, "web-mobile", "style.css",
                     "body { background: #ffffff; }\n")

    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "style.css",
         "kind": "regex_sub",
         "find": r"background:\s*#[0-9a-fA-F]{3,6}",
         "replace": "background: #1c2833"},
    ])

    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })
    monkeypatch.setattr(cb.subprocess, "run",
                        lambda *a, **k: type("P", (), {"returncode": 36})())

    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["success"] is True
    assert "post_build_patches" in res
    assert res["post_build_patches"]["ok"] is True
    assert res["post_build_patches"]["applied"][0]["file"] == "style.css"
    # File actually got patched
    content = (proj / "build" / "web-mobile" / "style.css").read_text()
    assert "#1c2833" in content


def test_cli_build_apply_patches_false_skips_them(tmp_path: Path, monkeypatch):
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "style.css", "body {}")
    cp.register_post_build_patches(str(proj), [
        {"platform": "web-mobile", "file": "style.css",
         "kind": "regex_sub", "find": "body", "replace": "xxx"},
    ])
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })
    monkeypatch.setattr(cb.subprocess, "run",
                        lambda *a, **k: type("P", (), {"returncode": 36})())

    res = cb.cli_build(str(proj), clean_temp=False, apply_patches=False)
    assert res["success"] is True
    # No patch ran — file should be unchanged
    assert (proj / "build" / "web-mobile" / "style.css").read_text() == "body {}"
    assert "post_build_patches" not in res


def test_cli_build_patch_failure_surfaces_structured_error(tmp_path: Path, monkeypatch):
    """Build itself passed; patch broke → success=False + POST_BUILD_PATCH_FAILED
    error_code so the caller isn't chasing the Cocos log."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "style.css", "body {}")
    cp.register_post_build_patches(str(proj), [
        # Pattern won't match → raises at apply time
        {"platform": "web-mobile", "file": "style.css",
         "kind": "regex_sub", "find": "nonexistent", "replace": "x"},
    ])
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })
    monkeypatch.setattr(cb.subprocess, "run",
                        lambda *a, **k: type("P", (), {"returncode": 36})())

    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["success"] is False
    assert res["error_code"] == "POST_BUILD_PATCH_FAILED"
    assert "cocos_list_post_build_patches" in res["hint"]
    assert res["post_build_patches"]["ok"] is False


def test_cli_build_no_patches_registered_emits_no_report(tmp_path: Path, monkeypatch):
    """Fresh project with no patches should look exactly like it did before
    this feature existed — no extra fields in the result dict."""
    proj = _make_project(tmp_path)
    _seed_build_file(proj, "web-mobile", "index.html", "<html/>")
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })
    monkeypatch.setattr(cb.subprocess, "run",
                        lambda *a, **k: type("P", (), {"returncode": 36})())

    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["success"] is True
    # Registry doesn't exist → apply runs, returns ok=True with nothing
    # applied/skipped. Empty-but-present report is fine; what matters is
    # success and no errors.
    assert res["post_build_patches"]["ok"] is True
    assert res["post_build_patches"]["applied"] == []
    assert res["post_build_patches"]["errors"] == []

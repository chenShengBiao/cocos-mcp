"""Tests for cocos.build — settings/cleanup/log helpers (no real Creator needed)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import build as cb


def _make_project_skeleton(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(json.dumps({"name": "demo"}))
    return root


# ----------- log dir is cross-platform -----------

def test_log_dir_uses_tempfile_module():
    assert Path(tempfile.gettempdir()) == cb._LOG_DIR
    assert cb._LOG_DIR.exists()


# ----------- start scene / included scenes -----------

def test_set_start_scene_writes_settings(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    res = cb.set_start_scene(str(proj), "uuid-aaa")
    assert res["startScene"] == "uuid-aaa"

    saved = json.loads(Path(res["settings_path"]).read_text())
    assert saved["general"]["startScene"] == "uuid-aaa"


def test_add_scene_to_build_is_idempotent(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    cb.add_scene_to_build(str(proj), "u1")
    cb.add_scene_to_build(str(proj), "u2")
    res = cb.add_scene_to_build(str(proj), "u1")  # duplicate
    assert res["includedScenes"] == ["u1", "u2"]


def test_set_wechat_appid_writes_builder_json(tmp_path: Path):
    proj = _make_project_skeleton(tmp_path / "p")
    res = cb.set_wechat_appid(str(proj), "wx1234567890")
    saved = json.loads(Path(res["builder_path"]).read_text())
    assert saved["wechatgame"]["appid"] == "wx1234567890"


# ----------- clean_project -----------

@pytest.mark.parametrize("level,expect_removed", [
    ("build", ["build"]),
    ("temp", ["temp"]),
    ("library", ["library"]),
    ("default", ["build", "temp"]),
    ("all", ["build", "temp", "library"]),
])
def test_clean_project_levels(tmp_path: Path, level: str, expect_removed: list[str]):
    proj = _make_project_skeleton(tmp_path / "p")
    for d in ("build", "temp", "library"):
        (proj / d).mkdir()
        (proj / d / "marker").write_text("x")

    res = cb.clean_project(str(proj), level=level)

    assert sorted(res["removed"]) == sorted(expect_removed)
    for d in expect_removed:
        assert not (proj / d).exists()


def test_clean_project_rejects_unknown_level(tmp_path: Path):
    """Unknown level used to silently fall back to 'default' (clean build+temp),
    which masked typos like 'lib' meaning 'library'. Now raises ValueError."""
    proj = _make_project_skeleton(tmp_path / "p")
    (proj / "library").mkdir()
    with pytest.raises(ValueError, match=r"unknown level 'lib'"):
        cb.clean_project(str(proj), level="lib")
    # Library should still be there since the call never executed
    assert (proj / "library").exists()


# ----------- cli_build (subprocess mocked) -----------

def test_cli_build_rejects_non_project(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="not a Cocos project"):
        cb.cli_build(str(tmp_path / "nope"))


def test_cli_build_marks_success_on_exit_36(tmp_path: Path, monkeypatch):
    proj = _make_project_skeleton(tmp_path / "p")
    build_dir = proj / "build" / "web-mobile"
    build_dir.mkdir(parents=True)
    (build_dir / "index.html").write_text("<html/>")

    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    class _FakeProc:
        returncode = 36

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        # Simulate Creator producing an empty log.
        return _FakeProc()

    monkeypatch.setattr(cb.subprocess, "run", _fake_run)

    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["exit_code"] == 36
    assert res["success"] is True
    assert res["build_dir"] == str(build_dir)
    assert "index.html" in res["artifacts"]


def test_cli_build_marks_failure_when_no_artifacts(tmp_path: Path, monkeypatch):
    proj = _make_project_skeleton(tmp_path / "p")

    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    class _FakeProc:
        returncode = 34  # Creator's "unexpected error" exit

    monkeypatch.setattr(cb.subprocess, "run", lambda *a, **k: _FakeProc())

    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["exit_code"] == 34
    assert res["success"] is False
    # Generic build failure gets a BUILD_FAILED code + a hint pointing at the log.
    assert res["error_code"] == "BUILD_FAILED"
    assert "log" in res["hint"].lower()


def test_cli_build_classifies_typescript_error(tmp_path: Path, monkeypatch):
    """When log_tail contains a TS compile signature, the result should carry
    BUILD_TYPESCRIPT_ERROR + a hint that tells the LLM to fix the .ts file."""
    proj = _make_project_skeleton(tmp_path / "p")
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    # Seed the log file that cli_build tails. Note: cli_build writes its
    # log BEFORE reading it back, so we have to patch subprocess.run to
    # leave a log behind.
    fake_log_body = (
        "Starting build...\n"
        "src/Player.ts:12:5 - error TS2322: Type 'string' is not assignable to 'number'.\n"
        "Build failed.\n"
    )

    class _FakeProc:
        returncode = 34

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        if stdout is not None:
            stdout.write(fake_log_body)
            stdout.flush()
        return _FakeProc()

    monkeypatch.setattr(cb.subprocess, "run", _fake_run)
    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["success"] is False
    assert res["error_code"] == "BUILD_TYPESCRIPT_ERROR"
    assert "cocos_add_script" in res["hint"]


def test_cli_build_classifies_missing_module(tmp_path: Path, monkeypatch):
    proj = _make_project_skeleton(tmp_path / "p")
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    class _FakeProc:
        returncode = 34

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        if stdout is not None:
            stdout.write("Error: Cannot find module './UIHelper'\n")
            stdout.flush()
        return _FakeProc()

    monkeypatch.setattr(cb.subprocess, "run", _fake_run)
    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["error_code"] == "BUILD_MISSING_MODULE"


def test_cli_build_timeout_sets_timeout_code(tmp_path: Path, monkeypatch):
    proj = _make_project_skeleton(tmp_path / "p")
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        raise cb.subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(cb.subprocess, "run", _fake_run)
    res = cb.cli_build(str(proj), clean_temp=False, timeout_sec=5)
    assert res["success"] is False
    assert res["timed_out"] is True
    assert res["error_code"] == "BUILD_TIMEOUT"
    assert "timeout_sec" in res["hint"]

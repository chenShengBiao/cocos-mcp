"""Verify runtime dicts returned by the tools match the declared TypedDicts.

These tests exist to catch shape drift — if someone adds a new field to a
return dict but forgets to add it to the TypedDict (or vice versa), the
runtime shape will stop matching what the type system thinks it is, and
downstream code (and the LLM caller) silently loses the key. We can't
enforce this with mypy alone because TypedDict keys with ``total=False``
are all optional, so the type-check passes regardless.

Strategy: reflect the TypedDict's declared keys via ``__annotations__``
and compare against the keys the function actually returns.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import build as cb
from cocos import scene_builder as sb
from cocos import types as t


def _all_keys(td: type) -> set[str]:
    """Declared keys for a TypedDict, including inherited ones."""
    keys: set[str] = set()
    for klass in td.__mro__:
        if hasattr(klass, "__annotations__"):
            keys.update(klass.__annotations__.keys())
    # `__mro__` includes `object`, `dict`, etc. — those contribute nothing
    # useful but also nothing harmful (their __annotations__ is {} or missing).
    return keys


# ---------- BuildResult ----------

def test_build_result_success_keys_subset_of_typed(tmp_path: Path, monkeypatch):
    """Success path returns only keys declared in BuildResult."""
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "package.json").write_text(json.dumps({"name": "demo"}))
    build_dir = proj / "build" / "web-mobile"
    build_dir.mkdir(parents=True)
    (build_dir / "index.html").write_text("<html/>")

    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t"})

    class _FakeProc:
        returncode = 36

    monkeypatch.setattr(cb.subprocess, "run", lambda *a, **k: _FakeProc())
    res = cb.cli_build(str(proj), clean_temp=False)

    declared = _all_keys(t.BuildResult)
    runtime = set(res.keys())
    extra = runtime - declared
    assert not extra, f"cli_build returned undeclared keys: {extra}"
    # Required fields (from _BuildCommon) must all be present on success
    required = {"exit_code", "success", "duration_sec", "log_path",
                "log_tail", "build_dir", "artifacts"}
    assert required.issubset(runtime)


def test_build_result_failure_keys_subset_of_typed(tmp_path: Path, monkeypatch):
    """Failure path adds error_code+hint — still a subset of BuildResult."""
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "package.json").write_text(json.dumps({"name": "demo"}))

    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t"})

    class _FakeProc:
        returncode = 34

    monkeypatch.setattr(cb.subprocess, "run", lambda *a, **k: _FakeProc())
    res = cb.cli_build(str(proj), clean_temp=False)

    declared = _all_keys(t.BuildResult)
    extra = set(res.keys()) - declared
    assert not extra, f"cli_build (failure) returned undeclared keys: {extra}"
    assert "error_code" in res and "hint" in res


def test_build_result_timeout_keys_subset_of_typed(tmp_path: Path, monkeypatch):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "package.json").write_text(json.dumps({"name": "demo"}))

    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t"})

    def _raise_timeout(cmd, stdout=None, stderr=None, timeout=None):
        raise cb.subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(cb.subprocess, "run", _raise_timeout)
    res = cb.cli_build(str(proj), clean_temp=False, timeout_sec=1)

    declared = _all_keys(t.BuildResult)
    extra = set(res.keys()) - declared
    assert not extra, f"cli_build (timeout) returned undeclared keys: {extra}"
    assert res["timed_out"] is True


# ---------- SceneCreateResult ----------

def test_scene_create_result_matches_typed(tmp_path: Path):
    res = sb.create_empty_scene(tmp_path / "s.scene")
    declared = _all_keys(t.SceneCreateResult)
    runtime = set(res.keys())
    assert runtime == declared, (
        f"create_empty_scene shape drift — "
        f"missing: {declared - runtime}, extra: {runtime - declared}")


# ---------- ValidationResult ----------

def test_validation_result_matches_typed(tmp_path: Path):
    path = tmp_path / "v.scene"
    sb.create_empty_scene(path)
    res = sb.validate_scene(path)
    declared = _all_keys(t.ValidationResult)
    runtime = set(res.keys())
    assert runtime == declared, (
        f"validate_scene shape drift — "
        f"missing: {declared - runtime}, extra: {runtime - declared}")


# ---------- BatchOpsResult ----------

def test_batch_ops_result_matches_typed(tmp_path: Path):
    path = tmp_path / "b.scene"
    info = sb.create_empty_scene(path)
    res = sb.batch_ops(str(path), [
        {"op": "add_node", "parent_id": info["canvas_node_id"], "name": "N"},
    ])
    declared = _all_keys(t.BatchOpsResult)
    runtime = set(res.keys())
    assert runtime == declared, (
        f"batch_ops shape drift — "
        f"missing: {declared - runtime}, extra: {runtime - declared}")


# ---------- PreviewStatusResult ----------

def test_preview_status_result_matches_typed():
    res = cb.preview_status()
    declared = _all_keys(t.PreviewStatusResult)
    assert set(res.keys()) == declared
    # Each entry must match PreviewStatusEntry shape
    entry_declared = _all_keys(t.PreviewStatusEntry)
    for entry in res["running"]:
        assert set(entry.keys()) == entry_declared

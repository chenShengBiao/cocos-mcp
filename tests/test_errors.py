"""Unit tests for cocos.errors — structured error helper + build log classifier."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import errors


def test_make_error_basic_shape():
    err = errors.make_error("X_CODE", "something broke")
    assert err == {"ok": False, "error": {"code": "X_CODE", "message": "something broke"}}


def test_make_error_with_hint_and_extras():
    err = errors.make_error("X", "m", hint="do Y", extra_field=123)
    assert err["error"]["hint"] == "do Y"
    assert err["error"]["extra_field"] == 123


def test_classify_build_log_typescript_error():
    log = "src/Foo.ts:9:3 - error TS2304: Cannot find name 'MissingClass'.\n"
    result = errors.classify_build_log(log)
    assert result is not None
    code, hint = result
    # TS-prefix pattern is more specific than generic "Cannot find name",
    # so classifier should report the TS error code, not the module code.
    assert code == errors.BUILD_TYPESCRIPT_ERROR
    assert "cocos_add_script" in hint


def test_classify_build_log_missing_module():
    log = "Error: Cannot find module '../helpers/Audio'\n"
    result = errors.classify_build_log(log)
    assert result is not None
    code, _ = result
    assert code == errors.BUILD_MISSING_MODULE


def test_classify_build_log_asset_not_found():
    log = "SceneLoader: asset not found for uuid abc-123-def\n"
    result = errors.classify_build_log(log)
    assert result is not None
    code, hint = result
    assert code == errors.BUILD_ASSET_NOT_FOUND
    assert "cocos_list_assets" in hint or "cocos_validate_scene" in hint


def test_classify_build_log_returns_none_for_unknown():
    assert errors.classify_build_log("some unrelated chatter") is None
    assert errors.classify_build_log("") is None


# ----------- find_creator error enrichment -----------

def test_find_creator_lists_available_versions_on_mismatch(monkeypatch):
    from cocos import project as cp
    monkeypatch.setattr(cp, "list_creator_installs", lambda: [
        {"version": "3.8.6", "exe": "/a", "template_dir": "/t"},
        {"version": "3.8.0", "exe": "/b", "template_dir": "/t"},
    ])
    with pytest.raises(RuntimeError) as exc:
        cp.find_creator("3.99")
    msg = str(exc.value)
    # Must name the prefix the caller asked for AND list what's available,
    # otherwise the LLM has to spin up another tool call to find out.
    assert "3.99" in msg
    assert "3.8.6" in msg and "3.8.0" in msg


def test_find_creator_no_installs_hint_includes_install_step(monkeypatch):
    from cocos import project as cp
    monkeypatch.setattr(cp, "list_creator_installs", lambda: [])
    with pytest.raises(RuntimeError) as exc:
        cp.find_creator()
    msg = str(exc.value)
    assert "cocos_list_creator_installs" in msg or "install" in msg.lower()

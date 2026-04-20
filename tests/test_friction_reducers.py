"""Tests for the four "reduce AI's friction" improvements:

1. Creator path flexibility — COCOS_CREATOR_PATH / COCOS_CREATOR_EXTRA_ROOTS /
   $PATH probe. All failure modes previously surfaced as a single vague
   "no Cocos Creator install found locally" error.
2. TypeScript error structured parsing — pulling {file, line, col, code,
   message} out of the build log tail so the orchestrating LLM doesn't
   have to regex it itself.
3. Script UUID auto-compress — accepting the 36-char standard form and
   converting to the 23-char short form the engine actually reads.
4. Engine-module audit — cross-checking a scene's components against
   the project's engine.json so "build succeeded but RigidBody2D does
   nothing" gets caught pre-build.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import build as cb
from cocos import errors as errs
from cocos import scene_builder as sb
from cocos.project import installs
from cocos.uuid_util import compress_uuid, new_uuid


# ========================= #
#  1. Creator path override #
# ========================= #

def _fake_install_dir(root: Path, version: str) -> Path:
    """Build a Cocos Creator install skeleton at ``root/<version>/``
    matching the platform's expected binary layout.

    Returns the version dir so tests can pass it to ``COCOS_CREATOR_PATH``
    or include its parent as an extra root."""
    vdir = root / version
    if sys.platform == "darwin":
        bin_dir = vdir / "CocosCreator.app/Contents/MacOS"
        tpl_dir = vdir / "CocosCreator.app/Contents/Resources/templates"
        exe = bin_dir / "CocosCreator"
    elif sys.platform == "win32":
        tpl_dir = vdir / "resources/templates"
        exe = vdir / "CocosCreator.exe"
    else:
        tpl_dir = vdir / "resources/templates"
        exe = vdir / "CocosCreator"
    bin_dir = exe.parent
    bin_dir.mkdir(parents=True)
    tpl_dir.mkdir(parents=True)
    exe.touch()
    return vdir


def _reset_creator_cache():
    """LRU caches survive across tests — purge before each isolated probe."""
    installs._list_creator_installs_cached.cache_clear()


def test_cocos_creator_path_env_pins_single_install(tmp_path: Path, monkeypatch):
    _reset_creator_cache()
    vdir = _fake_install_dir(tmp_path, "3.8.6")
    monkeypatch.setenv("COCOS_CREATOR_PATH", str(vdir))
    monkeypatch.delenv("COCOS_CREATOR_EXTRA_ROOTS", raising=False)

    result = installs.list_creator_installs()
    assert len(result) == 1
    assert result[0]["version"] == "3.8.6"
    assert result[0]["exe"] == str(vdir / (
        "CocosCreator.app/Contents/MacOS/CocosCreator" if sys.platform == "darwin"
        else ("CocosCreator.exe" if sys.platform == "win32" else "CocosCreator")
    ))


def test_cocos_creator_path_bad_falls_back_to_auto_scan(tmp_path: Path, monkeypatch):
    """Pointing at a non-existent dir shouldn't swallow the rest of
    discovery — auto-scan still runs, just with nothing in the extras."""
    _reset_creator_cache()
    monkeypatch.setenv("COCOS_CREATOR_PATH", str(tmp_path / "nowhere"))
    monkeypatch.setenv("COCOS_CREATOR_EXTRA_ROOTS", "")
    # Point default scan at a dir with nothing so we know the only
    # installs found came from env/fallback.
    monkeypatch.setattr(installs, "INSTALL_ROOTS", {
        sys.platform: [tmp_path / "empty_default"],
    })
    monkeypatch.setattr(installs.shutil, "which", lambda _n: None)
    result = installs.list_creator_installs()
    # Falls back to auto-scan → nothing in empty dirs → []. Key point:
    # no crash, no RuntimeError in THIS call — that happens only when
    # find_creator sees an empty list.
    assert result == []


def test_cocos_creator_extra_roots_env(tmp_path: Path, monkeypatch):
    _reset_creator_cache()
    _fake_install_dir(tmp_path, "3.9.0")
    monkeypatch.delenv("COCOS_CREATOR_PATH", raising=False)
    sep = ";" if sys.platform == "win32" else ":"
    monkeypatch.setenv("COCOS_CREATOR_EXTRA_ROOTS", f"{tmp_path}{sep}/nonexistent")
    # Kill the default scan so only the extra root contributes
    monkeypatch.setattr(installs, "INSTALL_ROOTS", {
        sys.platform: [tmp_path / "defaults_empty"],
    })
    monkeypatch.setattr(installs.shutil, "which", lambda _n: None)

    result = installs.list_creator_installs()
    assert any(e["version"] == "3.9.0" for e in result)


def test_path_probe_discovers_binary_on_PATH(tmp_path: Path, monkeypatch):
    """If CocosCreator is reachable via shutil.which, we should back-walk
    to the install root and include it."""
    _reset_creator_cache()
    vdir = _fake_install_dir(tmp_path, "3.8.7")
    monkeypatch.delenv("COCOS_CREATOR_PATH", raising=False)
    monkeypatch.delenv("COCOS_CREATOR_EXTRA_ROOTS", raising=False)
    monkeypatch.setattr(installs, "INSTALL_ROOTS", {
        sys.platform: [tmp_path / "defaults_empty"],
    })
    # Simulate `which CocosCreator` returning the fake exe
    if sys.platform == "darwin":
        exe = vdir / "CocosCreator.app/Contents/MacOS/CocosCreator"
    elif sys.platform == "win32":
        exe = vdir / "CocosCreator.exe"
    else:
        exe = vdir / "CocosCreator"
    monkeypatch.setattr(installs.shutil, "which",
                        lambda n: str(exe) if n in ("CocosCreator", "CocosCreator.exe") else None)

    result = installs.list_creator_installs()
    assert any(e["version"] == "3.8.7" for e in result)


def test_find_creator_error_mentions_env_var_escape_hatches(monkeypatch):
    """The error message on 'no installs' should point users at the
    COCOS_CREATOR_PATH / COCOS_CREATOR_EXTRA_ROOTS escape hatches,
    because the default install location is often wrong in practice."""
    from cocos import project as cp
    monkeypatch.setattr(cp, "list_creator_installs", lambda: [])
    with pytest.raises(RuntimeError) as exc:
        cp.find_creator()
    msg = str(exc.value)
    assert "COCOS_CREATOR_PATH" in msg
    assert "COCOS_CREATOR_EXTRA_ROOTS" in msg
    assert "PATH" in msg


# ========================= #
#  2. TS error parsing      #
# ========================= #

def test_parse_ts_errors_extracts_diagnostics():
    log = (
        "Starting build...\n"
        "src/Player.ts:12:5 - error TS2322: Type 'string' is not assignable to 'number'.\n"
        "12     this.hp = 'full';\n"
        "       ~~~~~~~\n"
        "src/UI/Hud.ts:3:18 - error TS2304: Cannot find name 'Label'.\n"
        "3 private score: Label;\n"
        "                 ~~~~~\n"
        "Build failed.\n"
    )
    out = errs.parse_ts_errors(log)
    assert len(out) == 2

    assert out[0]["file"] == "src/Player.ts"
    assert out[0]["line"] == 12
    assert out[0]["col"] == 5
    assert out[0]["code"] == "TS2322"
    assert "string" in out[0]["message"] and "number" in out[0]["message"]

    assert out[1]["file"] == "src/UI/Hud.ts"
    assert out[1]["line"] == 3
    assert out[1]["col"] == 18
    assert out[1]["code"] == "TS2304"


def test_parse_ts_errors_empty_inputs():
    assert errs.parse_ts_errors("") == []
    assert errs.parse_ts_errors("no ts errors here, just informational chatter") == []


def test_cli_build_ts_error_includes_ts_errors_field(tmp_path: Path, monkeypatch):
    """cli_build should emit the structured ts_errors list alongside the
    existing error_code/hint when the log tail has parseable TS errors."""
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "package.json").write_text(json.dumps({"name": "demo"}))
    monkeypatch.setattr(cb, "find_creator", lambda v=None: {
        "exe": "/fake/cc", "version": "3.8.6", "template_dir": "/fake/t",
    })

    class _FakeProc:
        returncode = 34

    def _fake_run(cmd, stdout=None, stderr=None, timeout=None):
        if stdout is not None:
            stdout.write(
                "src/Main.ts:7:9 - error TS2304: Cannot find name 'foo'.\n"
                "Build failed.\n"
            )
            stdout.flush()
        return _FakeProc()

    monkeypatch.setattr(cb.subprocess, "run", _fake_run)
    res = cb.cli_build(str(proj), clean_temp=False)
    assert res["error_code"] == "BUILD_TYPESCRIPT_ERROR"
    assert "ts_errors" in res
    assert res["ts_errors"][0]["file"] == "src/Main.ts"
    assert res["ts_errors"][0]["line"] == 7
    assert res["ts_errors"][0]["code"] == "TS2304"


# ========================= #
#  3. Script UUID compress  #
# ========================= #

def test_add_script_auto_compresses_36_char_uuid(tmp_path: Path):
    """Passing the standard 36-char UUID (common when copy-pasting from
    a .ts.meta file or cocos_list_assets output) used to be a silent
    bug — the engine couldn't resolve the class. Now auto-compresses."""
    path = tmp_path / "s.scene"
    info = sb.create_empty_scene(path)
    n = sb.add_node(path, info["canvas_node_id"], "Player")

    standard = new_uuid()  # 36-char dashed form
    expected_short = compress_uuid(standard)
    assert len(standard) == 36 and standard.count("-") == 4
    assert len(expected_short) == 23

    cid = sb.add_script(str(path), n, standard)
    obj = sb.get_object(path, cid)
    # The scene's script_component carries the short form, not the original 36-char
    assert obj["__type__"] == expected_short


def test_add_script_keeps_23_char_uuid_as_is(tmp_path: Path):
    path = tmp_path / "s.scene"
    info = sb.create_empty_scene(path)
    n = sb.add_node(path, info["canvas_node_id"], "Player")
    short = compress_uuid(new_uuid())
    cid = sb.add_script(str(path), n, short)
    assert sb.get_object(path, cid)["__type__"] == short


# ========================= #
#  4. Engine-module audit   #
# ========================= #

def _make_project(tmp_path: Path, modules_enabled: dict[str, bool] | None = None) -> Path:
    p = tmp_path / "proj"
    (p / "assets").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    engine_json = p / "settings" / "v2" / "packages" / "engine.json"
    engine_json.parent.mkdir(parents=True)
    cache = {name: {"_value": on} for name, on in (modules_enabled or {}).items()}
    engine_json.write_text(json.dumps({
        "modules": {"configs": {"defaultConfig": {"cache": cache}}},
    }))
    return p


def test_audit_flags_rigidbody2d_when_physics_module_off(tmp_path: Path):
    proj = _make_project(tmp_path, modules_enabled={"physics-2d": False})
    scene = proj / "assets" / "scenes" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    n = sb.add_node(scene, info["canvas_node_id"], "Ball")
    sb.add_rigidbody2d(str(scene), n)

    report = sb.audit_scene_modules(scene)
    assert report["ok"] is False
    assert "physics-2d" in report["disabled"]
    assert "physics-2d" in report["required"]
    # Action hint should point to cocos_set_engine_module + cocos_clean_project
    combined = "\n".join(report["actions"])
    assert "cocos_set_engine_module" in combined
    assert "cocos_clean_project" in combined


def test_audit_accepts_physics_2d_box2d_as_satisfying_physics_2d(tmp_path: Path):
    """physics-2d parent can be left off in engine.json as long as the
    backend sub-module is on — Cocos's own inspector treats that as valid
    (the sub-module implies the parent). Audit must match."""
    proj = _make_project(tmp_path, modules_enabled={
        "physics-2d-box2d": True,
    })
    scene = proj / "assets" / "scenes" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    n = sb.add_node(scene, info["canvas_node_id"], "Ball")
    sb.add_rigidbody2d(str(scene), n)

    report = sb.audit_scene_modules(scene)
    assert report["ok"] is True
    assert report["disabled"] == []


def test_audit_ok_when_no_special_modules_needed(tmp_path: Path):
    """A plain-UI scene (Label + Button) doesn't need physics/spine/etc."""
    proj = _make_project(tmp_path, modules_enabled={})
    scene = proj / "assets" / "scenes" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    n = sb.add_node(scene, info["canvas_node_id"], "Label")
    sb.add_uitransform(scene, n, 200, 60)
    sb.add_label(scene, n, "hello")

    report = sb.audit_scene_modules(scene)
    assert report["ok"] is True


def test_audit_flags_multiple_missing_modules(tmp_path: Path):
    """A scene that uses spine + tiled + physics-2d should flag all three."""
    proj = _make_project(tmp_path, modules_enabled={})
    scene = proj / "assets" / "scenes" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    canvas = info["canvas_node_id"]

    n_sp = sb.add_node(scene, canvas, "SpineChar")
    sb.add_spine(str(scene), n_sp)
    n_tm = sb.add_node(scene, canvas, "Map")
    sb.add_tiled_map(str(scene), n_tm)
    n_rb = sb.add_node(scene, canvas, "Body")
    sb.add_rigidbody2d(str(scene), n_rb)

    report = sb.audit_scene_modules(scene)
    assert report["ok"] is False
    assert set(report["disabled"]) >= {"spine", "tiled-map", "physics-2d"}


def test_audit_walks_up_to_find_project_root(tmp_path: Path):
    """Callers typically pass just the scene path; we should auto-locate
    package.json by walking up."""
    proj = _make_project(tmp_path, modules_enabled={"physics-2d-box2d": True})
    scene = proj / "assets" / "scenes" / "deep" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    report = sb.audit_scene_modules(scene)
    assert Path(report["project_path"]) == proj.resolve()


def test_audit_raises_when_project_unfindable(tmp_path: Path):
    """If the scene lives outside any Cocos project layout, ask the caller
    to be explicit instead of silently falling through."""
    scene = tmp_path / "floating.scene"
    sb.create_empty_scene(scene)
    with pytest.raises(FileNotFoundError, match=r"project_path"):
        sb.audit_scene_modules(scene)

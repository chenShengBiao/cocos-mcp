"""Post-build patch registry + apply engine.

Cocos Creator regenerates ``build/<platform>/`` from scratch every
``cocos_build`` call. Any manual edit to a file under ``build/`` gets
wiped the next build. Three common needs where there's no source-config
switch to do the edit upstream:

* ``build/web-mobile/style.css`` — template-default body background;
  customizing requires editing the Creator template (fragile, global)
  or patching the output.
* Platform-specific JSON tweaks that Cocos doesn't expose as a project
  setting (e.g. ``project.config.json.setting.urlCheck`` for WeChat).
* Whole-file overrides like a custom ``index.html``.

Rather than making users rerun their edits after every build, we
register declarative patches in
``settings/v2/packages/post-build-patches.json`` (our own file — Cocos
ignores unrecognized filenames) and apply them automatically after a
successful build.

Three patch kinds:

* ``json_set`` — navigate by dotted path, assign value. Creates
  intermediate dicts if missing. Refuses to traverse a non-dict
  (e.g. trying to set ``"foo.bar"`` when ``foo`` is a string) — that
  would silently corrupt user data.
* ``regex_sub`` — ``re.sub(find, replace, content, count=1)`` on text
  files. Required at registration time to compile cleanly, and at
  apply time must match at least once (a patch that stops matching
  after a Cocos Creator version bump is a silent regression waiting
  to bite).
* ``copy_from`` — ``shutil.copy`` a whole file from project-root
  relative ``source`` over the build target. Handy for a custom
  ``index.html`` template.

The registry is version-stamped (``version: 1``) so we can evolve the
shape later without breaking stored patches.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

_REGISTRY_REL = Path("settings") / "v2" / "packages" / "post-build-patches.json"
_SUPPORTED_KINDS = ("json_set", "regex_sub", "copy_from")
_REGISTRY_VERSION = 1


def _registry_path(project_path: str | Path) -> Path:
    return Path(project_path).expanduser().resolve() / _REGISTRY_REL


def _load_registry(project_path: str | Path) -> dict:
    p = _registry_path(project_path)
    if not p.exists():
        return {"version": _REGISTRY_VERSION, "patches": []}
    try:
        with open(p) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"post-build patch registry at {p} is unreadable ({e}); "
            "delete the file or fix the JSON to continue"
        ) from e
    # Forward-compat: accept newer schema versions but warn; refuse older
    # (shouldn't exist yet). Reject anything that's not the expected shape
    # so registry CRUD doesn't silently corrupt it.
    if not isinstance(data, dict) or "patches" not in data:
        raise RuntimeError(
            f"post-build patch registry at {p} has unexpected shape — "
            "expected {{version, patches}}. Delete and re-register."
        )
    return data


def _save_registry(project_path: str | Path, data: dict) -> Path:
    p = _registry_path(project_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys=False preserves patch iteration order — ``apply_patches``
    # runs patches in registration order, which users rely on when one
    # patch's output feeds another.
    with open(p, "w") as f:
        json.dump(data, f, indent=2, sort_keys=False)
    return p


# ---------- validation ----------

def _validate_patch(patch: dict) -> None:
    """Raise ``ValueError`` if a patch is malformed at register time,
    with a message pointing at the specific field that's wrong.

    Registration-time validation is the right place to catch invalid
    regex / dangerous paths — catching them at apply time would mean a
    build succeeds but patching fails, the worst combination for CI.
    """
    if not isinstance(patch, dict):
        raise ValueError(f"patch must be a dict, got {type(patch).__name__}")

    platform = patch.get("platform")
    if not isinstance(platform, str) or not platform:
        raise ValueError(f"patch.platform must be a non-empty str, got {platform!r}")

    file_rel = patch.get("file")
    if not isinstance(file_rel, str) or not file_rel:
        raise ValueError(f"patch.file must be a non-empty str, got {file_rel!r}")
    # Path injection guard: ``..`` segments and absolute paths could let a
    # patch write outside ``build/<platform>/``. No legitimate use case.
    pp = Path(file_rel)
    if pp.is_absolute() or ".." in pp.parts:
        raise ValueError(
            f"patch.file {file_rel!r} must be a relative path without '..' "
            "segments (all patches target build/<platform>/<file>)"
        )

    kind = patch.get("kind")
    if kind not in _SUPPORTED_KINDS:
        raise ValueError(
            f"patch.kind must be one of {_SUPPORTED_KINDS}, got {kind!r}"
        )

    if kind == "json_set":
        if not isinstance(patch.get("path"), str) or not patch["path"]:
            raise ValueError("json_set patch requires non-empty 'path' (dotted key like 'launch.launchScene')")
        if "value" not in patch:
            raise ValueError("json_set patch requires 'value' (any JSON-serializable)")
    elif kind == "regex_sub":
        find = patch.get("find")
        if not isinstance(find, str) or not find:
            raise ValueError("regex_sub patch requires non-empty 'find' regex")
        try:
            re.compile(find)
        except re.error as e:
            raise ValueError(f"regex_sub 'find' isn't a valid regex: {e}") from e
        if not isinstance(patch.get("replace", None), str):
            raise ValueError("regex_sub patch requires 'replace' (str, may be empty)")
    elif kind == "copy_from":
        src = patch.get("source")
        if not isinstance(src, str) or not src:
            raise ValueError("copy_from patch requires non-empty 'source' (project-root relative)")
        sp = Path(src)
        if sp.is_absolute() or ".." in sp.parts:
            raise ValueError(
                f"copy_from source {src!r} must be a relative path without '..' "
                "(source files must live inside the project)"
            )


# ---------- registry CRUD ----------

def register_patches(project_path: str | Path, patches: list[dict],
                     mode: str = "append") -> dict:
    """Register one or more patches.

    ``mode``:
      - ``"append"`` (default) — extend the existing list. Order preserved.
      - ``"replace"`` — replace the entire list. Useful when regenerating
        the patch set from a higher-level config.

    Every patch is validated before the file is written — a batch with
    even one invalid patch fails atomically (registry stays unchanged).
    """
    if mode not in ("append", "replace"):
        raise ValueError(f"mode must be 'append' or 'replace', got {mode!r}")
    for p in patches:
        _validate_patch(p)

    data = _load_registry(project_path)
    if mode == "replace":
        data["patches"] = list(patches)
    else:
        data.setdefault("patches", []).extend(patches)
    data.setdefault("version", _REGISTRY_VERSION)
    registry_path = _save_registry(project_path, data)
    return {
        "registry_path": str(registry_path),
        "mode": mode,
        "count": len(data["patches"]),
        "added": len(patches),
    }


def list_patches(project_path: str | Path) -> dict:
    """Return the full patch list with indices for later selective removal."""
    data = _load_registry(project_path)
    return {
        "registry_path": str(_registry_path(project_path)),
        "version": data.get("version", _REGISTRY_VERSION),
        "patches": [
            {"index": i, **p} for i, p in enumerate(data.get("patches", []))
        ],
    }


def remove_patches(project_path: str | Path,
                   indices: list[int] | None = None,
                   platform: str | None = None,
                   file: str | None = None) -> dict:
    """Remove patches by index list or by platform/file filter.

    Call with no arguments to remove nothing (explicit wipe requires
    ``register_patches([], mode='replace')`` — forces the user to think
    twice about clearing the whole list).

    Filter precedence: if ``indices`` is given it wins; otherwise
    platform+file filter applies (AND semantics). This keeps the "remove
    all on this platform" case ergonomic.
    """
    data = _load_registry(project_path)
    patches = data.get("patches", [])
    if indices is not None:
        drop = {i for i in indices if 0 <= i < len(patches)}
        kept = [p for i, p in enumerate(patches) if i not in drop]
    elif platform is None and file is None:
        # No filter → no-op. Avoids accidentally wiping the registry.
        return {
            "registry_path": str(_registry_path(project_path)),
            "removed": 0,
            "remaining": len(patches),
        }
    else:
        kept = []
        for p in patches:
            if platform is not None and p.get("platform") != platform:
                kept.append(p)
                continue
            if file is not None and p.get("file") != file:
                kept.append(p)
                continue
            # Falls through to drop
    removed = len(patches) - len(kept)
    data["patches"] = kept
    registry_path = _save_registry(project_path, data)
    return {
        "registry_path": str(registry_path),
        "removed": removed,
        "remaining": len(kept),
    }


# ---------- apply engine ----------

def _set_dotted(doc: dict, dotted: str, value: Any) -> None:
    """In-place set on a nested dict. Creates missing intermediate dicts.

    Refuses to traverse a non-dict — raising here means the patch has a
    bug (or the file's shape changed) and we'd rather fail loudly than
    overwrite a scalar/list somewhere unexpected.
    """
    parts = dotted.split(".")
    cur: Any = doc
    for key in parts[:-1]:
        if not isinstance(cur, dict):
            raise ValueError(
                f"json_set: cannot descend into non-dict at key '{key}' "
                f"(full path: {dotted!r}, current type: {type(cur).__name__})"
            )
        if key not in cur or not isinstance(cur[key], dict):
            if key in cur and not isinstance(cur[key], dict):
                raise ValueError(
                    f"json_set: key {key!r} exists with non-dict value "
                    f"{type(cur[key]).__name__}; can't descend (path: {dotted!r})"
                )
            cur[key] = {}
        cur = cur[key]
    if not isinstance(cur, dict):
        raise ValueError(
            f"json_set: terminal parent at '{'.'.join(parts[:-1])}' is not a dict"
        )
    cur[parts[-1]] = value


def _apply_json_set(target: Path, patch: dict) -> str:
    if not target.exists():
        return "skipped: file not found"
    try:
        with open(target) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"{target}: can't parse as JSON ({e}); "
            "is this the right file for a json_set patch?"
        ) from e
    _set_dotted(data, patch["path"], patch["value"])
    with open(target, "w") as f:
        json.dump(data, f, indent=2)
    return f"json_set: {patch['path']} = {patch['value']!r}"


def _apply_regex_sub(target: Path, patch: dict) -> str:
    if not target.exists():
        return "skipped: file not found"
    with open(target) as f:
        content = f.read()
    new_content, count = re.subn(patch["find"], patch["replace"], content, count=1)
    if count == 0:
        raise RuntimeError(
            f"{target}: regex_sub pattern {patch['find']!r} didn't match. "
            "Likely Cocos changed its template — open the file, find the "
            "new shape, update your 'find' regex."
        )
    with open(target, "w") as f:
        f.write(new_content)
    return f"regex_sub: {patch['find']!r} → 1 replacement"


def _apply_copy_from(target: Path, project_root: Path, patch: dict) -> str:
    src = project_root / patch["source"]
    if not src.exists():
        raise RuntimeError(
            f"copy_from source {src} doesn't exist. "
            "The project-root-relative 'source' path must point at an existing file."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, target)
    return f"copy_from: {patch['source']} → {target.name}"


def apply_patches(project_path: str | Path, platform: str,
                  dry_run: bool = False) -> dict:
    """Walk the registry and apply every patch whose ``platform`` matches.

    ``dry_run=True`` reports what would happen without writing anything.
    Normal run writes in-place; if any patch raises, we stop on that
    patch — partially-applied state is reported in the return value so
    the caller knows the scope of the in-flight mutation.

    Returns::

        {
          "platform": str,
          "dry_run": bool,
          "build_dir": str,                       # build/<platform>/ resolved
          "applied": [{"file": str, "note": str}, ...],
          "skipped": [{"file": str, "reason": str}, ...],  # patch matched but file missing
          "errors":  [{"file": str, "message": str}, ...], # patch errored; stops the run
          "ok": bool,                             # True iff errors is empty
        }
    """
    project_root = Path(project_path).expanduser().resolve()
    build_dir = project_root / "build" / platform
    data = _load_registry(project_root)
    patches = [p for p in data.get("patches", []) if p.get("platform") == platform]

    applied: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    for patch in patches:
        target = build_dir / patch["file"]
        try:
            if dry_run:
                # Report intent without touching the file. Still check existence
                # so the dry-run report is accurate.
                if not target.exists() and patch["kind"] != "copy_from":
                    skipped.append({"file": patch["file"], "reason": "file not found"})
                    continue
                applied.append({
                    "file": patch["file"],
                    "kind": patch["kind"],
                    "note": f"[dry-run] would apply {patch['kind']}",
                })
                continue

            if patch["kind"] == "json_set":
                note = _apply_json_set(target, patch)
            elif patch["kind"] == "regex_sub":
                note = _apply_regex_sub(target, patch)
            elif patch["kind"] == "copy_from":
                note = _apply_copy_from(target, project_root, patch)
            else:
                # _validate_patch should have caught this at register time
                raise RuntimeError(f"unknown patch kind at apply time: {patch['kind']!r}")

            if note.startswith("skipped:"):
                skipped.append({"file": patch["file"], "reason": note[len("skipped: "):]})
            else:
                applied.append({"file": patch["file"], "kind": patch["kind"], "note": note})
        except Exception as e:
            errors.append({"file": patch["file"], "message": str(e)})
            # Stop on first error. Continuing would risk compounding failures
            # (e.g. applying 5 patches to a json_set that already corrupted the file).
            break

    return {
        "platform": platform,
        "dry_run": dry_run,
        "build_dir": str(build_dir),
        "applied": applied,
        "skipped": skipped,
        "errors": errors,
        "ok": not errors,
    }

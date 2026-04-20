"""Cocos Creator install detection + project init from template.

Three discovery paths, tried in order:

1. ``COCOS_CREATOR_PATH`` env var — highest precedence. If set, it should
   point at a single Creator install root (the directory whose name is the
   version, e.g. ``/custom/path/3.8.6``) and becomes the ONLY install the
   server sees. Overrides everything else so users with weird install
   locations have a simple escape hatch.
2. Auto-scan: platform default roots (``INSTALL_ROOTS``) plus any extra
   roots in ``COCOS_CREATOR_EXTRA_ROOTS`` (colon/semicolon-separated on
   POSIX/Windows respectively).
3. ``$PATH`` probe: if a ``CocosCreator`` binary is reachable via the
   shell's PATH we back-walk to the install root and include it.

Why ``find_creator`` looks ``list_creator_installs`` up lazily through the
package: tests and examples monkeypatch ``cocos.project.list_creator_installs``
(via ``monkeypatch.setattr(cp, "list_creator_installs", ...)``). A bare
``list_creator_installs()`` call inside ``find_creator`` would resolve to
this module's own binding and skip the patch. The ``from cocos.project
import list_creator_installs`` idiom inside the function reads the
attribute from the package namespace each call, so patches take effect.
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import sys
from pathlib import Path

from ..uuid_util import new_uuid

# Where Cocos Dashboard installs Creator on each platform. Users with
# non-standard setups can add more via COCOS_CREATOR_EXTRA_ROOTS (see
# module docstring).
INSTALL_ROOTS = {
    "darwin": [Path("/Applications/Cocos/Creator")],
    "win32": [Path("C:/CocosDashboard/Creator"), Path("C:/Program Files/Cocos/Creator")],
    "linux": [Path("/opt/Cocos/Creator")],
}


def _paths_for_creator_binary(exe: Path) -> tuple[Path, Path] | None:
    """Given a resolved CocosCreator executable path, return (version_dir,
    template_dir) or None if the layout doesn't look like a Creator install.

    Creator's on-disk layout is the same whether the install lives at
    /Applications/Cocos/Creator/3.8.6/ or some custom directory, so the
    derivation rules are uniform — the difference is which side of the
    ``.app`` bundle you're on (macOS) vs a plain dir (Windows/Linux).
    """
    exe = exe.resolve()
    if sys.platform == "darwin":
        # /<version_dir>/CocosCreator.app/Contents/MacOS/CocosCreator
        app = exe.parent.parent.parent
        if app.suffix != ".app":
            return None
        version_dir = app.parent
        template_dir = app / "Contents/Resources/templates"
    else:
        # /<version_dir>/CocosCreator(.exe)
        version_dir = exe.parent
        template_dir = version_dir / "resources/templates"
    if not version_dir.exists():
        return None
    return version_dir, template_dir


def _entry_for_version_dir(version_dir: Path) -> dict | None:
    """Build a ``{version, exe, template_dir}`` entry from a Creator
    version directory. Returns None if the expected binary is missing."""
    if not version_dir.is_dir():
        return None
    if sys.platform == "darwin":
        exe = version_dir / "CocosCreator.app/Contents/MacOS/CocosCreator"
        template_dir = version_dir / "CocosCreator.app/Contents/Resources/templates"
    elif sys.platform == "win32":
        exe = version_dir / "CocosCreator.exe"
        template_dir = version_dir / "resources/templates"
    else:
        exe = version_dir / "CocosCreator"
        template_dir = version_dir / "resources/templates"
    if not exe.exists():
        return None
    return {
        "version": version_dir.name,
        "exe": str(exe),
        "template_dir": str(template_dir) if template_dir.exists() else None,
    }


def _scan_root(root: Path) -> list[dict]:
    """Scan ``<root>/<version>/`` for installed Creators."""
    if not root.exists():
        return []
    out: list[dict] = []
    for child in root.iterdir():
        entry = _entry_for_version_dir(child)
        if entry is not None:
            out.append(entry)
    return out


def _extra_roots_from_env() -> list[Path]:
    raw = os.environ.get("COCOS_CREATOR_EXTRA_ROOTS", "")
    if not raw:
        return []
    # Windows uses ';' in PATH-like vars; POSIX uses ':'. Accept both.
    sep = ";" if sys.platform == "win32" else ":"
    return [Path(p).expanduser() for p in raw.split(sep) if p.strip()]


def _probe_path_for_creator() -> dict | None:
    """If ``CocosCreator`` is on $PATH, return its entry.

    This lets users with symlinks / custom installs just make the binary
    reachable the normal way instead of hunting for the right env var.
    """
    for name in ("CocosCreator", "CocosCreator.exe"):
        resolved = shutil.which(name)
        if not resolved:
            continue
        got = _paths_for_creator_binary(Path(resolved))
        if got is None:
            continue
        version_dir, _template_dir = got
        entry = _entry_for_version_dir(version_dir)
        if entry is not None:
            return entry
    return None


@functools.lru_cache(maxsize=1)
def _list_creator_installs_cached() -> tuple[dict, ...]:
    # (1) explicit pin via COCOS_CREATOR_PATH beats all auto-discovery
    pinned = os.environ.get("COCOS_CREATOR_PATH", "").strip()
    if pinned:
        entry = _entry_for_version_dir(Path(pinned).expanduser())
        if entry is not None:
            return (entry,)
        # Pin was set but doesn't look like a Creator install — fall through
        # to auto-discovery rather than silently acting as if it wasn't set.
        # The next error message will tell the user what's wrong.

    seen_exes: set[str] = set()
    out: list[dict] = []

    # (2) default platform roots + user-supplied extras
    roots = list(INSTALL_ROOTS.get(sys.platform, [Path("/Applications/Cocos/Creator")]))
    roots.extend(_extra_roots_from_env())
    for root in roots:
        for entry in _scan_root(root):
            if entry["exe"] not in seen_exes:
                seen_exes.add(entry["exe"])
                out.append(entry)

    # (3) whatever's on PATH
    path_entry = _probe_path_for_creator()
    if path_entry is not None and path_entry["exe"] not in seen_exes:
        out.append(path_entry)

    return tuple(out)


def list_creator_installs() -> list[dict]:
    """Return all locally installed Cocos Creator versions.

    Results are cached for the lifetime of this process — Creator installs
    rarely change mid-session, and probing the filesystem every call wastes
    time on the init path (``find_creator`` → ``init_project``/``cli_build``).
    Call ``invalidate_creator_installs_cache()`` if an install was added/
    removed and you need fresh data.
    """
    return [dict(i) for i in _list_creator_installs_cached()]


def invalidate_creator_installs_cache() -> None:
    """Drop the cached Creator install list (e.g. after a new install)."""
    _list_creator_installs_cached.cache_clear()


def find_creator(version_prefix: str | None = None) -> dict:
    """Find a specific or the latest installed Creator."""
    # Late-bound via the package namespace — see module docstring.
    from cocos.project import list_creator_installs as _lci
    installs = _lci()
    if not installs:
        raise RuntimeError(
            "no Cocos Creator install found locally. Try, in order:\n"
            "  1. Install from https://www.cocos.com/creator-download\n"
            "  2. If Creator lives in a non-standard location, set\n"
            "     COCOS_CREATOR_PATH=/path/to/3.8.6 (the version directory)\n"
            "  3. Or add the parent directory to COCOS_CREATOR_EXTRA_ROOTS\n"
            "  4. Or put the CocosCreator binary on your $PATH\n"
            "Then call cocos_list_creator_installs to verify."
        )
    if version_prefix:
        matching = [i for i in installs if i["version"].startswith(version_prefix)]
        if not matching:
            available = ", ".join(sorted({i["version"] for i in installs}))
            raise RuntimeError(
                f"no Creator install matching {version_prefix!r}. "
                f"Available: {available or '(none)'}. "
                f"Omit version_prefix to use the highest installed version."
            )
        installs = matching
    # Sort by version (string compare works for x.y.z forms)
    installs.sort(key=lambda i: i["version"], reverse=True)
    return installs[0]


def init_project(dst_path: str | Path, creator_version: str | None = None,
                 template: str = "empty-2d", project_name: str | None = None) -> dict:
    """Copy a Creator template into `dst_path` and patch package.json.

    Returns:
      {
        "project_path", "project_uuid", "creator_version",
        "creator_exe", "template",
        "skipped_files": list[str],   # template files NOT copied because
                                       # the destination already had something
                                       # with the same name (relative to dst).
                                       # Caller should sanity-check this — a
                                       # non-empty list means the project may
                                       # be inconsistent.
      }
    """
    creator = find_creator(creator_version)
    template_dir = Path(creator["template_dir"]) / template
    if not template_dir.exists():
        avail = [p.name for p in Path(creator["template_dir"]).iterdir() if p.is_dir()]
        raise FileNotFoundError(f"template {template!r} not found. Available: {avail}")

    dst = Path(dst_path).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)

    # Copy template contents (including dotfiles). Don't overwrite existing
    # files — but do report what got skipped so the caller knows the project
    # may be incomplete.
    skipped: list[str] = []
    for item in template_dir.iterdir():
        target = dst / item.name
        if target.exists():
            skipped.append(item.name)
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    # Patch package.json
    pkg_path = dst / "package.json"
    if pkg_path.exists():
        with open(pkg_path) as f:
            pkg = json.load(f)
    else:
        pkg = {}
    name = project_name or dst.name
    project_uuid = new_uuid()
    pkg.update({
        "creator": {"version": creator["version"]},
        "name": name,
        "type": "2d" if "2d" in template else "3d",
        "uuid": project_uuid,
        "version": pkg.get("version", "0.1.0"),
    })
    with open(pkg_path, "w") as f:
        json.dump(pkg, f, indent=2)

    # Create assets dirs
    for sub in ("scenes", "scripts", "textures", "prefabs", "resources"):
        (dst / "assets" / sub).mkdir(parents=True, exist_ok=True)

    return {
        "project_path": str(dst),
        "project_uuid": project_uuid,
        "creator_version": creator["version"],
        "creator_exe": creator["exe"],
        "template": template,
        "skipped_files": skipped,
    }

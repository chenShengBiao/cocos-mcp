"""Cocos Creator install detection + project init from template.

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
import shutil
import sys
from pathlib import Path

from ..uuid_util import new_uuid

# Where Cocos Dashboard installs Creator on each platform
INSTALL_ROOTS = {
    "darwin": [Path("/Applications/Cocos/Creator")],
    "win32": [Path("C:/CocosDashboard/Creator"), Path("C:/Program Files/Cocos/Creator")],
    "linux": [Path("/opt/Cocos/Creator")],
}


@functools.lru_cache(maxsize=1)
def _list_creator_installs_cached() -> tuple[dict, ...]:
    roots = INSTALL_ROOTS.get(sys.platform, [Path("/Applications/Cocos/Creator")])
    out: list[dict] = []
    for root in roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            version = child.name
            if sys.platform == "darwin":
                exe = child / "CocosCreator.app/Contents/MacOS/CocosCreator"
                template_dir = child / "CocosCreator.app/Contents/Resources/templates"
            elif sys.platform == "win32":
                exe = child / "CocosCreator.exe"
                template_dir = child / "resources/templates"
            else:
                exe = child / "CocosCreator"
                template_dir = child / "resources/templates"
            if exe.exists():
                out.append({
                    "version": version,
                    "exe": str(exe),
                    "template_dir": str(template_dir) if template_dir.exists() else None,
                })
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
            "no Cocos Creator install found locally — install from "
            "https://www.cocos.com/creator-download, then call "
            "cocos_list_creator_installs to verify before retrying"
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

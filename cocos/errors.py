"""Structured errors for MCP tool results.

The MCP caller is an LLM that cannot easily recover from a plain string
error — it needs a handle ("what kind of thing failed") and a next step
("which tool should I call, or what should I ask the user"). This module
centralizes those two pieces so error surface stays consistent across
tools instead of each raising a free-form string.

Two ways to use it:

* ``make_error(code, message, hint=None, **extra)`` — build the standard
  error dict ``{ok: False, error: {code, message, hint, ...}}`` for tools
  that already return a dict (e.g. ``cli_build`` which has success/failure
  in the same shape).
* ``classify_build_log(log_tail)`` — pattern-match common Cocos CLI log
  signatures to attach an actionable hint without asking the LLM to
  re-read the entire log.

When you raise instead of returning, include a hint in the message body
— FastMCP serializes exceptions to the caller as-is.
"""
from __future__ import annotations

import re
from typing import Any

# Known error codes. Keep the set small; each one should map to a clear
# recovery path the caller can act on.
CREATOR_NOT_FOUND = "CREATOR_NOT_FOUND"
CREATOR_VERSION_MISMATCH = "CREATOR_VERSION_MISMATCH"
TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
BUILD_TIMEOUT = "BUILD_TIMEOUT"
BUILD_FAILED = "BUILD_FAILED"
BUILD_MISSING_MODULE = "BUILD_MISSING_MODULE"
BUILD_TYPESCRIPT_ERROR = "BUILD_TYPESCRIPT_ERROR"
BUILD_ASSET_NOT_FOUND = "BUILD_ASSET_NOT_FOUND"


def make_error(code: str, message: str, hint: str | None = None,
               **extra: Any) -> dict:
    """Build a structured error dict.

    The shape ``{"ok": False, "error": {...}}`` is distinguishable from
    success results without requiring callers to probe for specific keys.
    """
    err: dict[str, Any] = {"code": code, "message": message}
    if hint:
        err["hint"] = hint
    err.update(extra)
    return {"ok": False, "error": err}


# ---------- build log classification ----------

# Each entry: (code, regex, hint). First match wins, so order is by
# specificity: the TypeScript error-code pattern (TS####:) runs before
# the generic "Cannot find module" pattern, because a line like
# "error TS2307: Cannot find module 'X'" is best reported as a TS error
# (the LLM should open the .ts file) rather than a module-resolution
# issue (the LLM would go hunt the UUID). Patterns are intentionally
# narrow — a false positive misdirects the LLM into running the wrong
# recovery tool, which is worse than no hint.
_BUILD_LOG_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (BUILD_TYPESCRIPT_ERROR,
     re.compile(r"\berror TS\d{4,5}\b|\bTS\d{4,5}:", re.I),
     "TypeScript compile error — read log_tail, fix the .ts file "
     "with cocos_add_script (overwrite), then rebuild"),

    (BUILD_MISSING_MODULE,
     re.compile(r"(?:RigidBody2D|BoxCollider2D|CircleCollider2D|PolygonCollider2D).*not (?:defined|registered)",
                re.I),
     "physics-2d module is off — enable with "
     "cocos_set_engine_module(module_name='physics-2d-box2d', enabled=True), "
     "then clean library/ and rebuild"),

    (BUILD_MISSING_MODULE,
     re.compile(r"Cannot find module\s+['\"]([\w./@-]+)['\"]", re.I),
     "an import path resolves to nothing — "
     "check that the referenced script exists "
     "(cocos_list_assets) and that the import spelling matches"),

    (BUILD_ASSET_NOT_FOUND,
     re.compile(r"(?:asset|resource|uuid) (?:not found|missing|does not exist)", re.I),
     "a referenced asset UUID has no backing file — "
     "run cocos_list_assets to confirm the UUID exists, "
     "or cocos_validate_scene to find stale {__uuid__} references"),
)


def classify_build_log(log_tail: str) -> tuple[str, str] | None:
    """Return ``(code, hint)`` for a recognized failure signature, else None.

    Meant to enrich a generic ``BUILD_FAILED`` result when the log contains
    a pattern we've seen before.
    """
    if not log_tail:
        return None
    for code, pattern, hint in _BUILD_LOG_PATTERNS:
        if pattern.search(log_tail):
            return code, hint
    return None


# Per-error regex for TypeScript compile failures. Captures the file,
# line, column, TS error code, and the message on the same line. The
# Cocos build log echoes the tsc diagnostic format verbatim, which is
# the format `tsc` itself prints: ``foo.ts:9:3 - error TS2304: ...``.
# Skip the exact-file match (we don't care if it's absolute or relative
# on this caller's platform) and just grab everything up to the first
# colon followed by digits.
_TS_ERROR_LINE = re.compile(
    r"^(?P<file>[^\s:]+\.ts):(?P<line>\d+):(?P<col>\d+)\s*-\s*"
    r"error\s+(?P<code>TS\d+):\s*(?P<message>.+?)$",
    re.MULTILINE,
)


def parse_ts_errors(log_tail: str) -> list[dict]:
    """Extract structured TypeScript errors from a build log tail.

    Returns a list of ``{file, line, col, code, message}`` dicts, one per
    diagnostic line in the log. Empty list when none match — callers
    treat that as "either no TS errors, or the format changed and we
    need a new regex".

    Strips the ``tsc``-style context lines (they follow each error line
    with source code + caret) since those aren't on the diagnostic line
    and don't match the header regex anyway.
    """
    if not log_tail:
        return []
    out: list[dict] = []
    for m in _TS_ERROR_LINE.finditer(log_tail):
        try:
            out.append({
                "file": m.group("file"),
                "line": int(m.group("line")),
                "col": int(m.group("col")),
                "code": m.group("code"),
                "message": m.group("message").rstrip("."),
            })
        except (ValueError, AttributeError):
            # Regex guarantees int-convertible line/col and named groups,
            # but fail-open rather than raise into the build-result path.
            continue
    return out

"""Declarative assertions — for AI-built games to self-verify.

The interact tools (click, press_key, read_preview_state) let the AI
drive and inspect a running preview. What those tools don't provide
is a *check*: a declarative "after doing X, state should be Y". Without
that, the AI has to manually compare read-back values against
expectations in free-form English, which is both error-prone and
unstructured.

This module closes the gap:

* ``assert_scene_state(scene_path, assertions)`` runs a list of
  expectations against a .scene / .prefab JSON file — the scene-level
  checks you'd want in unit-test-style regression guards ("Player node
  exists", "Enemy's health property is 100", "Canvas has a Camera ref").

* ``_check(actual, op, expected)`` + ``_resolve_path(root, path)`` are
  the shared primitives — ``interact.run_preview_sequence`` imports
  them to support ``{"kind": "assert", ...}`` actions inside a browser
  session so runtime-state assertions happen in the same session as
  the clicks that produced the state.

Operator vocabulary

  eq / ne                 equality
  gt / ge / lt / le       ordered comparison (numbers, strings, ...)
  in / not_in             membership in a list/dict/string
  contains                expected IN actual (inverted ``in``, for
                          substring / element checks)
  match                   regex search on str(actual)
  is_null / not_null      None checks
  type_is                 type name: 'int' / 'str' / 'list' / 'dict' /
                          'bool' / 'null'
  exists / not_exists     path resolution succeeded or didn't;
                          bypasses actual-value comparison

Path syntax

  "15._lpos.x"            → root[15]["_lpos"]["x"]
  "_components[0].__id__" → root["_components"][0]["__id__"]

Dotted segments are dict keys UNLESS the first segment is an integer
and the root is a list (then it's an index). Bracketed ``[N]`` is
always a list index. Missing keys / out-of-range indices raise
``LookupError`` so the assertion reports the path that didn't resolve
rather than crashing.

Find shortcuts

When the caller doesn't know the raw array index up front:

  {"find_node_by_name": "Player", "path": "_lpos.x", ...}
  {"find_component": {"type": "cc.Sprite", "on_node_named": "Enemy"},
   "path": "_color.r", ...}

These pre-resolve the root before path traversal.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .scene_builder._helpers import _load_scene

# Ops that compare an actual against an expected. These all return
# bool; callers surface False as a failure.
_BINARY_OPS = {
    "eq": lambda a, e: a == e,
    "ne": lambda a, e: a != e,
    "gt": lambda a, e: a > e,
    "ge": lambda a, e: a >= e,
    "lt": lambda a, e: a < e,
    "le": lambda a, e: a <= e,
    "in": lambda a, e: a in e,
    "not_in": lambda a, e: a not in e,
    "contains": lambda a, e: e in a,
    "match": lambda a, e: re.search(str(e), str(a)) is not None,
}

# Ops that don't compare — either unary on actual or structural
# (exists / not_exists are handled at the caller level because they
# need access to the path-resolution try/except).
_UNARY_OPS = {
    "is_null": lambda a: a is None,
    "not_null": lambda a: a is not None,
}


def _check(actual: Any, op: str, expected: Any) -> bool:
    """Evaluate an operator against (actual, expected).

    Raises ``ValueError`` for unknown ops. ``exists`` / ``not_exists``
    are NOT handled here — the caller decides those based on whether
    path resolution raised.
    """
    if op in _BINARY_OPS:
        return _BINARY_OPS[op](actual, expected)
    if op in _UNARY_OPS:
        return _UNARY_OPS[op](actual)
    if op == "type_is":
        if expected == "null":
            return actual is None
        return type(actual).__name__ == expected
    raise ValueError(
        f"unknown assertion op {op!r}. "
        f"Valid: eq ne gt ge lt le in not_in contains match "
        f"is_null not_null type_is exists not_exists"
    )


# Tokenize a path into (kind, value) pairs. ``kind`` is either 'key'
# (str, dict access), 'idx' (int, list/dict-int access), or 'brack'
# (int from ``[N]``, forced list-index).
_TOKEN_RE = re.compile(r"\[(\d+)\]|([^.[\]]+)")


def _resolve_path(root: Any, path: str) -> Any:
    """Descend ``root`` via the dotted path. Raises ``LookupError`` with
    a descriptive message when any segment can't be followed, so the
    caller can report which part of the path was wrong."""
    if not path:
        return root
    cur: Any = root
    for match in _TOKEN_RE.finditer(path):
        bracket_idx, name = match.group(1), match.group(2)
        if bracket_idx is not None:
            idx = int(bracket_idx)
            if not isinstance(cur, list):
                raise LookupError(
                    f"path segment [{idx}] requires list, got {type(cur).__name__} "
                    f"at {path!r}"
                )
            if idx < 0 or idx >= len(cur):
                raise LookupError(
                    f"path segment [{idx}] out of range (len={len(cur)}) at {path!r}"
                )
            cur = cur[idx]
            continue

        # A bare dotted segment: integer → list index (if list) or dict
        # int-key (if dict). Non-integer → dict key.
        assert name is not None
        if name.lstrip("-").isdigit():
            idx = int(name)
            if isinstance(cur, list):
                if idx < 0 or idx >= len(cur):
                    raise LookupError(
                        f"path segment {idx} out of range (len={len(cur)}) at {path!r}"
                    )
                cur = cur[idx]
                continue
            if isinstance(cur, dict) and idx in cur:
                cur = cur[idx]
                continue
            # Fall through to dict-by-string so callers asking for
            # a dict with integer-like keys still work:
        if isinstance(cur, dict):
            if name not in cur:
                raise LookupError(
                    f"key {name!r} not in dict (keys: {list(cur.keys())[:10]}) "
                    f"at {path!r}"
                )
            cur = cur[name]
        else:
            raise LookupError(
                f"can't read {name!r} from {type(cur).__name__} at {path!r}"
            )
    return cur


def _resolve_root(scene_data: list, assertion: dict) -> tuple[Any, str]:
    """Pick the object an assertion's ``path`` descends into.

    Three options:

    1. ``find_node_by_name``: str → first cc.Node with matching _name.
    2. ``find_component``: {type, on_node_named} → first component of
       that type attached to the named node.
    3. Neither → the raw scene array, so path's first segment must be
       an integer index.

    Raises ``LookupError`` when the find target isn't present.
    """
    if "find_node_by_name" in assertion:
        name = assertion["find_node_by_name"]
        for obj in scene_data:
            if (isinstance(obj, dict) and obj.get("__type__") == "cc.Node"
                    and obj.get("_name") == name):
                return obj, f"find_node_by_name({name!r})"
        raise LookupError(f"no cc.Node with _name == {name!r}")

    if "find_component" in assertion:
        spec = assertion["find_component"]
        if not isinstance(spec, dict):
            raise ValueError("find_component must be a dict with 'type' + 'on_node_named'")
        ctype = spec.get("type")
        on_name = spec.get("on_node_named")
        if not ctype or not on_name:
            raise ValueError(
                "find_component requires 'type' and 'on_node_named' keys"
            )
        # Find the named node
        node = None
        for obj in scene_data:
            if (isinstance(obj, dict) and obj.get("__type__") == "cc.Node"
                    and obj.get("_name") == on_name):
                node = obj
                break
        if node is None:
            raise LookupError(f"no cc.Node with _name == {on_name!r}")
        # Walk its components
        for cref in node.get("_components", []):
            if not isinstance(cref, dict):
                continue
            cid = cref.get("__id__")
            if cid is None or cid < 0 or cid >= len(scene_data):
                continue
            cmp = scene_data[cid]
            if isinstance(cmp, dict) and cmp.get("__type__") == ctype:
                return cmp, f"find_component({ctype} on {on_name!r})"
        raise LookupError(f"cc.Node {on_name!r} has no {ctype} component")

    return scene_data, "scene_array"


def _run_one_assertion(scene_data: list, assertion: dict) -> dict:
    """Return a result dict: ``{ok, assertion, actual, error?}``."""
    op = assertion.get("op", "exists")

    # exists / not_exists bypass the op-value comparison — they report
    # purely on whether path resolution succeeded.
    try:
        root, root_desc = _resolve_root(scene_data, assertion)
        actual = _resolve_path(root, assertion.get("path", ""))
    except (LookupError, ValueError) as e:
        if op == "not_exists":
            return {"ok": True, "assertion": assertion, "actual": None,
                    "note": f"path did not resolve ({e})"}
        return {"ok": False, "assertion": assertion, "actual": None,
                "error": str(e)}

    if op == "exists":
        return {"ok": True, "assertion": assertion, "actual": actual}
    if op == "not_exists":
        return {"ok": False, "assertion": assertion, "actual": actual,
                "error": "path resolved (expected not_exists)"}

    expected = assertion.get("value")
    try:
        passed = _check(actual, op, expected)
    except Exception as e:
        return {"ok": False, "assertion": assertion, "actual": actual,
                "error": f"{op} check raised: {e}"}

    if passed:
        return {"ok": True, "assertion": assertion, "actual": actual}
    return {"ok": False, "assertion": assertion, "actual": actual,
            "expected": expected}


def assert_scene_state(scene_path: str | Path,
                       assertions: list[dict]) -> dict:
    """Evaluate a list of assertions against a scene/prefab file.

    Returns::

        {
          "ok": bool,               # True iff every assertion passed
          "scene_path": str,
          "total": int,
          "passed_count": int,
          "failed_count": int,
          "passed": [ {assertion, actual, ...} ],
          "failed": [ {assertion, actual, error | expected, ...} ],
        }

    Runs EVERY assertion even if earlier ones fail — the point of a
    regression check is a full report, not a first-failure bail.
    """
    scene = _load_scene(scene_path)
    passed: list[dict] = []
    failed: list[dict] = []
    for a in assertions:
        result = _run_one_assertion(scene, a)
        if result["ok"]:
            passed.append(result)
        else:
            failed.append(result)
    return {
        "ok": not failed,
        "scene_path": str(scene_path),
        "total": len(assertions),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "passed": passed,
        "failed": failed,
    }

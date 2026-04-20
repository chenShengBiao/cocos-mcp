"""Structural types for tool return dicts.

Why TypedDict and not plain dicts everywhere:

* These dicts travel to the MCP caller (an LLM). When the shape drifts
  unnoticed — a key renamed in one branch but not the other, a new field
  added to one success path but not the error one — the LLM's downstream
  behavior drifts with it. TypedDict lets ``mypy`` / readers spot the
  mismatch at author-time, without forcing callers (MCP clients) to
  parse a rigid schema.
* ``total=False`` is used intentionally for optional-on-failure fields
  (``error_code``, ``hint``, ``timed_out``) so the type reflects the
  actual runtime shape instead of requiring every caller to populate
  every key.

Nothing in this module should have runtime behavior; it's documentation
that a type-checker can act on.
"""
from __future__ import annotations

from typing import TypedDict


# ---------- build pipeline ----------

class _BuildCommon(TypedDict):
    exit_code: int
    success: bool
    duration_sec: float
    log_path: str
    log_tail: str
    build_dir: str | None
    artifacts: list[str]


class BuildResult(_BuildCommon, total=False):
    """Result of ``cli_build`` / ``cocos_build``.

    Fields from ``_BuildCommon`` are always present. ``error_code``,
    ``hint``, ``error``, and ``timed_out`` appear only on failure.
    """
    error_code: str
    hint: str
    error: str
    timed_out: bool


class _PreviewStartCommon(TypedDict):
    port: int
    url: str | None
    serving: str


class PreviewStartResult(_PreviewStartCommon, total=False):
    """Result of ``start_preview`` / ``cocos_start_preview``.

    ``pid`` + ``log`` appear on success; ``error`` appears on failure.
    """
    pid: int
    log: str
    error: str


class _PreviewStopCommon(TypedDict):
    stopped: bool
    port: int


class PreviewStopResult(_PreviewStopCommon, total=False):
    """``was_serving`` + ``pid`` appear only when we actually stopped a
    tracked preview; ``note`` appears when we did nothing."""
    was_serving: str
    pid: int
    note: str


class PreviewStatusEntry(TypedDict):
    port: int
    pid: int
    serving: str


class PreviewStatusResult(TypedDict):
    running: list[PreviewStatusEntry]


# ---------- scene builder ----------

class SceneCreateResult(TypedDict):
    """Result of ``create_empty_scene``."""
    scene_path: str
    scene_uuid: str
    scene_node_id: int
    canvas_node_id: int
    ui_camera_node_id: int
    camera_component_id: int
    canvas_component_id: int


class ValidationResult(TypedDict):
    """Result of ``validate_scene`` / ``cocos_validate_scene``."""
    valid: bool
    object_count: int
    issues: list[str]


class BatchOpsResult(TypedDict):
    """Result of ``batch_ops`` / ``cocos_batch_scene_ops``.

    ``results`` is a heterogeneous list: each element is an int (new
    node/component id), True (set_* success), or an ``{"error": "..."}``
    dict when an individual op failed.
    """
    object_count: int
    ops_executed: int
    results: list


# ---------- structured error envelope ----------

class ErrorBody(TypedDict, total=False):
    code: str
    message: str
    hint: str


class StructuredError(TypedDict):
    """Shape produced by ``cocos.errors.make_error``."""
    ok: bool
    error: ErrorBody

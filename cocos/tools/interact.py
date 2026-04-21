"""MCP tools that let an AI client INTERACT with a running preview.

``cocos_screenshot_preview`` gave the LLM eyes; these tools give it
hands and a state probe — so it can actually play-test what it built
instead of guessing whether a click wired up correctly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import interact as inter

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- One-shot interactions ----------------

    @mcp.tool()
    def cocos_click_preview(url: str,
                            x: int,
                            y: int,
                            button: str = "left",
                            wait_ms: int = 200,
                            viewport_width: int = 960,
                            viewport_height: int = 640,
                            timeout_ms: int = 15000) -> dict:
        """Click at page coordinates ``(x, y)`` in a running preview.

        Use this to drive UI you just built — a "Start" button, a menu
        tab, a card. Coordinates are in PAGE space (top-left origin),
        NOT viewport-relative. ``button`` is 'left' / 'right' / 'middle'.
        ``wait_ms`` gives post-click animations/scene-changes time to
        settle before the tool returns.

        Requires the optional ``playwright`` dependency (same as
        cocos_screenshot_preview). Returns ``{ok: True}`` on success,
        raises on navigation/launch failure with an actionable hint.
        """
        inter.click_preview(url, x, y, button=button, wait_ms=wait_ms,
                            viewport_width=viewport_width,
                            viewport_height=viewport_height,
                            timeout_ms=timeout_ms)
        return {"ok": True}

    @mcp.tool()
    def cocos_press_key_preview(url: str,
                                key: str,
                                wait_ms: int = 200,
                                viewport_width: int = 960,
                                viewport_height: int = 640,
                                timeout_ms: int = 15000) -> dict:
        """Press a single key in the running preview.

        ``key`` uses Playwright's names — 'Enter', 'Space', 'ArrowUp',
        'Escape', 'a', 'F1', etc. Cocos's ``systemEvent`` KeyCode hook
        fires on keydown/keyup as expected. Use this for keyboard-driven
        input (pause menus, player movement, form submit).
        """
        inter.press_key(url, key, wait_ms=wait_ms,
                        viewport_width=viewport_width,
                        viewport_height=viewport_height,
                        timeout_ms=timeout_ms)
        return {"ok": True}

    @mcp.tool()
    def cocos_type_preview(url: str,
                           text: str,
                           wait_ms: int = 200,
                           viewport_width: int = 960,
                           viewport_height: int = 640,
                           timeout_ms: int = 15000) -> dict:
        """Type a string into whatever widget currently has focus.

        Ideal for filling name-entry fields, high-score initials, chat
        boxes. The text is emitted one char at a time via the keyboard
        API, so IME/input-event handlers fire per character.
        """
        inter.type_text(url, text, wait_ms=wait_ms,
                        viewport_width=viewport_width,
                        viewport_height=viewport_height,
                        timeout_ms=timeout_ms)
        return {"ok": True}

    @mcp.tool()
    def cocos_drag_preview(url: str,
                           from_x: int, from_y: int,
                           to_x: int, to_y: int,
                           steps: int = 5,
                           button: str = "left",
                           wait_ms: int = 200,
                           viewport_width: int = 960,
                           viewport_height: int = 640,
                           timeout_ms: int = 15000) -> dict:
        """Drag the mouse from ``(from_x, from_y)`` to ``(to_x, to_y)``.

        ``steps`` is the number of intermediate move events — bump it if
        Cocos isn't picking up the drag (some handlers need minimum
        motion per frame). 5 is enough for a typical slider or card move.
        """
        inter.drag_preview(url, from_x, from_y, to_x, to_y,
                           steps=steps, button=button, wait_ms=wait_ms,
                           viewport_width=viewport_width,
                           viewport_height=viewport_height,
                           timeout_ms=timeout_ms)
        return {"ok": True}

    # ---------------- State read ----------------

    @mcp.tool()
    def cocos_read_preview_state(url: str,
                                 expression: str = "window.game",
                                 wait_ms: int = 200,
                                 viewport_width: int = 960,
                                 viewport_height: int = 640,
                                 timeout_ms: int = 15000) -> dict:
        """Evaluate a JavaScript expression against the running preview
        and return the value.

        The preview page must expose state on ``window`` for this to be
        useful — the pattern is ``window.game = this`` inside a
        GameManager's ``onLoad``. Then you can read ``window.game.score``,
        ``cc.director.getScene().name``, etc.

        Returns ``{ok, value, error}``. On a JS exception, ``ok=False``
        and ``error`` carries the message — a bad expression can't
        crash the tool.
        """
        return inter.read_preview_state(
            url, expression=expression, wait_ms=wait_ms,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            timeout_ms=timeout_ms)

    @mcp.tool()
    def cocos_wait_for_preview(url: str,
                               ms: int = 500,
                               viewport_width: int = 960,
                               viewport_height: int = 640,
                               timeout_ms: int = 15000) -> dict:
        """Navigate, sleep ``ms``, close — useful between a build and
        a screenshot to let async asset loading finish."""
        inter.wait_for_preview(url, ms=ms,
                               viewport_width=viewport_width,
                               viewport_height=viewport_height,
                               timeout_ms=timeout_ms)
        return {"ok": True}

    # ---------------- Multi-step sequences ----------------

    @mcp.tool()
    def cocos_run_preview_sequence(url: str,
                                   actions: list[dict],
                                   viewport_width: int = 960,
                                   viewport_height: int = 640,
                                   timeout_ms: int = 15000) -> list[dict]:
        """Run a list of actions in a SINGLE browser session.

        Essential for play-testing: game state resets on every page
        reload, so a multi-step test plan (click Start → type name →
        press Enter → read score) MUST share one session.

        Each action is a dict with a ``kind`` + kind-specific keys:
          {"kind": "click", "x": int, "y": int, "wait_ms"?: int, "button"?: str}
          {"kind": "key", "key": str, "wait_ms"?: int}
          {"kind": "type", "text": str, "wait_ms"?: int}
          {"kind": "drag", "from_x": int, "from_y": int, "to_x": int, "to_y": int, "steps"?: int}
          {"kind": "wait", "ms": int}
          {"kind": "read_state", "expression": str}
          {"kind": "screenshot"}

        Returns a list parallel to ``actions``: each entry is
        ``{kind, ok, result, error}``. A single failed action does NOT
        abort the sequence, so earlier successful reads/screenshots
        still come back.

        ``screenshot`` results return ``{"png_bytes_hex": "..."}`` —
        decode with ``bytes.fromhex()`` to get raw PNG data (MCP JSON
        can't carry bytes natively).
        """
        return inter.run_preview_sequence(
            url, actions,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            timeout_ms=timeout_ms)

    # ---------------- Pixel diff (no playwright needed) ----------------

    @mcp.tool()
    def cocos_screenshot_preview_diff(before_png_path: str,
                                      after_png_path: str,
                                      threshold: int = 8) -> dict:
        """Compare two PNG files on disk and report the change.

        Lets an AI confirm whether an action actually DID something —
        e.g. take a screenshot, click, take another, diff: if
        ``diff_ratio`` is ~0 the click had no visible effect.

        ``threshold`` is a per-channel absolute delta; pixels below are
        considered identical (8 rejects typical PNG compression noise).

        Returns ``{width, height, total_pixels, different_pixels,
        diff_ratio}`` where ``diff_ratio`` is in [0, 1].

        This tool is pure Pillow — it does NOT need playwright /
        chromium installed. Both inputs must be file paths; save via
        cocos_screenshot_preview first.
        """
        return inter.snapshot_diff(before_png_path, after_png_path,
                                   threshold=threshold)

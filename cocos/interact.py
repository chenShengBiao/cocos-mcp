"""Playwright-driven interaction + state read for a running preview URL.

Closes the OTHER half of the visual-feedback loop: ``cocos_screenshot_preview``
lets an AI client SEE its game; this module lets it PLAY the game —
clicking, typing, dragging, reading runtime state off ``window.game``,
and diffing frames to tell whether an action actually changed anything.

Design mirrors ``cocos/screenshot.py`` verbatim:

* Playwright is a ~200 MB optional dep, so we lazy-import inside each
  function and raise a structured ImportError pointing at the install
  command. Users opt in with ``uv pip install playwright && playwright
  install chromium``.

* Synchronous API only. FastMCP tools are invoked synchronously and an
  event-loop-per-call adds complexity without benefit.

* Chromium is the only driven browser — closest render target to a
  deployed web-mobile build.

* Game state does NOT survive a page reload, so we expose
  ``run_preview_sequence`` for multi-step test plans that need a single
  browser session (click, assert score, click again, screenshot).

* ``snapshot_diff`` is deliberately playwright-free — pure Pillow — so
  tests and other callers can compare PNGs without chromium installed.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

# Duplicated from cocos/screenshot.py so a user with screenshot missing
# gets the identical guidance. Kept as a module constant so both raise
# sites say the exact same thing.
_INSTALL_HINT = (
    "playwright is not installed. Install with:\n"
    "    uv pip install playwright\n"
    "    playwright install chromium\n"
    "(~200 MB disk; needed only for cocos_screenshot_preview)"
)


def _launch_context(p: Any, viewport_width: int, viewport_height: int) -> tuple[Any, Any, Any]:
    """Boot chromium + context + page, mapping launch failures to the
    "did you run playwright install chromium?" message. Shared helper so
    every public function raises the same error on the same cause."""
    try:
        browser = p.chromium.launch(headless=True)
    except Exception as e:
        raise RuntimeError(
            f"failed to launch chromium: {e}. "
            "Run `playwright install chromium` to download the browser binary."
        ) from e
    context = browser.new_context(
        viewport={"width": viewport_width, "height": viewport_height},
    )
    page = context.new_page()
    return browser, context, page


def _goto(page: Any, url: str, timeout_ms: int) -> None:
    try:
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
    except Exception as e:
        raise RuntimeError(
            f"failed to navigate to {url}: {e}. "
            "Is the preview server actually running? "
            "Check cocos_preview_status."
        ) from e


def click_preview(url: str,
                  x: int,
                  y: int,
                  button: str = "left",
                  wait_ms: int = 200,
                  viewport_width: int = 960,
                  viewport_height: int = 640,
                  timeout_ms: int = 15000) -> None:
    """Navigate, click at ``(x, y)`` in page coordinates, wait for effects."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    with sync_playwright() as p:
        browser, _ctx, page = _launch_context(p, viewport_width, viewport_height)
        try:
            _goto(page, url, timeout_ms)
            page.mouse.click(x, y, button=button)
            page.wait_for_timeout(wait_ms)
        finally:
            browser.close()


def press_key(url: str,
              key: str,
              wait_ms: int = 200,
              viewport_width: int = 960,
              viewport_height: int = 640,
              timeout_ms: int = 15000) -> None:
    """Navigate, press+release ``key`` once via the keyboard API."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    with sync_playwright() as p:
        browser, _ctx, page = _launch_context(p, viewport_width, viewport_height)
        try:
            _goto(page, url, timeout_ms)
            page.keyboard.press(key)
            page.wait_for_timeout(wait_ms)
        finally:
            browser.close()


def type_text(url: str,
              text: str,
              wait_ms: int = 200,
              viewport_width: int = 960,
              viewport_height: int = 640,
              timeout_ms: int = 15000) -> None:
    """Navigate, type ``text`` one character at a time via keyboard.type."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    with sync_playwright() as p:
        browser, _ctx, page = _launch_context(p, viewport_width, viewport_height)
        try:
            _goto(page, url, timeout_ms)
            page.keyboard.type(text)
            page.wait_for_timeout(wait_ms)
        finally:
            browser.close()


def drag_preview(url: str,
                 from_x: int,
                 from_y: int,
                 to_x: int,
                 to_y: int,
                 steps: int = 5,
                 button: str = "left",
                 wait_ms: int = 200,
                 viewport_width: int = 960,
                 viewport_height: int = 640,
                 timeout_ms: int = 15000) -> None:
    """Navigate, press+drag from ``(from_x, from_y)`` to ``(to_x, to_y)``
    in ``steps`` linearly-interpolated moves. Cocos drag-detection usually
    ignores an A→B teleport, so we always emit intermediates."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    # At least one intermediate — otherwise we're back to a teleport.
    steps = max(1, steps)
    with sync_playwright() as p:
        browser, _ctx, page = _launch_context(p, viewport_width, viewport_height)
        try:
            _goto(page, url, timeout_ms)
            page.mouse.move(from_x, from_y)
            page.mouse.down(button=button)
            for i in range(1, steps + 1):
                t = i / steps
                ix = from_x + (to_x - from_x) * t
                iy = from_y + (to_y - from_y) * t
                page.mouse.move(ix, iy)
            page.mouse.up(button=button)
            page.wait_for_timeout(wait_ms)
        finally:
            browser.close()


def read_preview_state(url: str,
                       expression: str = "window.game",
                       wait_ms: int = 200,
                       viewport_width: int = 960,
                       viewport_height: int = 640,
                       timeout_ms: int = 15000) -> dict:
    """Navigate, evaluate a JS expression in page context, return the
    result. Designed for runtimes that stash state on ``window`` (e.g.
    ``window.game = this`` in a GameManager's onLoad).

    Returns ``{ok, value, error}`` — any exception thrown by the page's
    JS becomes ``ok=False`` with the message, so an arbitrary expression
    can't crash the MCP tool.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    with sync_playwright() as p:
        browser, _ctx, page = _launch_context(p, viewport_width, viewport_height)
        try:
            _goto(page, url, timeout_ms)
            page.wait_for_timeout(wait_ms)
            try:
                value = page.evaluate(expression)
                return {"ok": True, "value": value, "error": None}
            except Exception as e:
                return {"ok": False, "value": None, "error": str(e)}
        finally:
            browser.close()


def wait_for_preview(url: str,
                     ms: int = 500,
                     viewport_width: int = 960,
                     viewport_height: int = 640,
                     timeout_ms: int = 15000) -> None:
    """Navigate, sleep ``ms``, close — for letting async asset loads
    settle between a build and a subsequent screenshot/read."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    with sync_playwright() as p:
        browser, _ctx, page = _launch_context(p, viewport_width, viewport_height)
        try:
            _goto(page, url, timeout_ms)
            page.wait_for_timeout(ms)
        finally:
            browser.close()


def run_preview_sequence(url: str,
                         actions: list[dict],
                         viewport_width: int = 960,
                         viewport_height: int = 640,
                         timeout_ms: int = 15000) -> list[dict]:
    """Execute ``actions`` in ONE browser session. Returns a list with
    one entry per input action — ``{kind, ok, result, error}``. A failed
    action is reported but does NOT short-circuit the rest, so an AI
    caller still sees earlier successful reads.

    Supported action kinds (see module docstring for full schema):
      click / key / type / drag / wait / read_state / screenshot
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    results: list[dict] = []
    with sync_playwright() as p:
        browser, _ctx, page = _launch_context(p, viewport_width, viewport_height)
        try:
            _goto(page, url, timeout_ms)
            for action in actions:
                kind = action.get("kind", "?")
                try:
                    result = _run_one(page, action)
                    # ``assert`` returns a structured pass/fail — let its
                    # ``passed`` flag propagate to the sequence-level ok,
                    # otherwise a failed assertion would look like a
                    # successful tool call.
                    if kind == "assert" and isinstance(result, dict) and "passed" in result:
                        ok = bool(result["passed"])
                        err = result.get("error")
                        if not ok and not err:
                            err = (f"assertion failed: {result.get('op')} "
                                   f"actual={result.get('actual')!r} "
                                   f"expected={result.get('expected')!r}")
                    else:
                        ok = True
                        err = None
                    results.append({"kind": kind, "ok": ok,
                                    "result": result, "error": err})
                except Exception as e:
                    results.append({"kind": kind, "ok": False,
                                    "result": None, "error": str(e)})
        finally:
            browser.close()
    return results


def _run_one(page: Any, action: dict) -> dict | None:
    """Dispatch a single sequence action against an already-open page.
    Returns a result dict when the action produces data (read_state,
    screenshot), else None."""
    kind = action["kind"]
    if kind == "click":
        page.mouse.click(action["x"], action["y"],
                         button=action.get("button", "left"))
        page.wait_for_timeout(int(action.get("wait_ms", 200)))
        return None
    if kind == "key":
        page.keyboard.press(action["key"])
        page.wait_for_timeout(int(action.get("wait_ms", 200)))
        return None
    if kind == "type":
        page.keyboard.type(action["text"])
        page.wait_for_timeout(int(action.get("wait_ms", 200)))
        return None
    if kind == "drag":
        steps = max(1, int(action.get("steps", 5)))
        button = action.get("button", "left")
        fx, fy = action["from_x"], action["from_y"]
        tx, ty = action["to_x"], action["to_y"]
        page.mouse.move(fx, fy)
        page.mouse.down(button=button)
        for i in range(1, steps + 1):
            t = i / steps
            page.mouse.move(fx + (tx - fx) * t, fy + (ty - fy) * t)
        page.mouse.up(button=button)
        page.wait_for_timeout(int(action.get("wait_ms", 200)))
        return None
    if kind == "wait":
        page.wait_for_timeout(int(action["ms"]))
        return None
    if kind == "read_state":
        value = page.evaluate(action["expression"])
        return {"value": value}
    if kind == "screenshot":
        png_bytes = page.screenshot(type="png")
        # bytes don't survive JSON round-trip through MCP, so we hex-encode.
        # Caller decodes with bytes.fromhex().
        return {"png_bytes_hex": png_bytes.hex()}
    if kind == "assert":
        # Evaluate the expression, compare against expected via shared
        # asserts._check, return a structured pass/fail result. Using the
        # same page/browser as the rest of the sequence is the whole point:
        # runtime game state doesn't survive a reload, so assertions must
        # ride the same session as the clicks that produced the state.
        from .asserts import _check
        expression = action["expression"]
        op = action.get("op", "eq")
        expected = action.get("value")
        actual = page.evaluate(expression)
        try:
            passed = _check(actual, op, expected)
        except Exception as e:
            return {
                "passed": False, "actual": actual, "expected": expected,
                "op": op, "error": f"{op} check raised: {e}",
            }
        return {
            "passed": passed, "actual": actual, "expected": expected, "op": op,
        }
    raise ValueError(f"unknown action kind: {kind!r}")


def snapshot_diff(before_png: bytes | str | Path,
                  after_png: bytes | str | Path,
                  threshold: int = 8) -> dict:
    """Pixel-level diff of two PNGs. Returns ``{width, height, total_pixels,
    different_pixels, diff_ratio}``.

    ``threshold`` is a per-channel absolute delta — pixels whose max
    channel delta is < threshold are considered identical. Keeps routine
    compression jitter from registering as change (the default 8 rejects
    ~3% PNG noise while still catching a sprite appearing/disappearing).

    Playwright is NOT needed here — this is pure Pillow, so it works on
    any machine that can read PNGs.
    """
    from PIL import Image, ImageChops

    def _load(src: bytes | str | Path) -> Image.Image:
        if isinstance(src, (bytes, bytearray)):
            return Image.open(io.BytesIO(src)).convert("RGB")
        return Image.open(src).convert("RGB")

    before = _load(before_png)
    after = _load(after_png)
    if before.size != after.size:
        raise ValueError(
            f"image size mismatch: before={before.size} after={after.size}"
        )

    diff = ImageChops.difference(before, after)
    width, height = diff.size
    total = width * height
    # Walk bytes of the diff image once; for RGB that's 3 bytes/pixel
    # where a pixel counts as "different" when any channel >= threshold.
    # tobytes() is future-proof (getdata was deprecated for Pillow 14).
    raw = diff.tobytes()
    different = 0
    for i in range(0, len(raw), 3):
        if raw[i] >= threshold or raw[i + 1] >= threshold or raw[i + 2] >= threshold:
            different += 1
    ratio = (different / total) if total else 0.0
    return {
        "width": width,
        "height": height,
        "total_pixels": total,
        "different_pixels": different,
        "diff_ratio": ratio,
    }

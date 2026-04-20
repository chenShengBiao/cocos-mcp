"""Playwright-driven screenshots of a running preview URL.

Closes the visual-feedback loop for AI clients: after ``cocos_build`` +
``cocos_start_preview``, the LLM can capture a PNG of what the browser
actually renders and iterate on the UI with sight instead of guesswork.

Design notes:

* Playwright is a **hard ~200 MB dependency** (chromium + webkit + firefox
  binaries once you run ``playwright install``), so we deliberately do
  NOT list it in ``pyproject.toml``'s runtime deps. Import is lazy inside
  ``screenshot_url``; users who want this tool opt in with
  ``uv pip install playwright && playwright install chromium``.

* The function is synchronous — Playwright's async API is nicer but
  FastMCP tools are invoked synchronously and spawning an event loop
  per tool call adds complexity without benefit. We use the
  ``sync_api`` entry point.

* Chromium is the only browser we drive. Firefox/WebKit would add
  another ~150 MB and for checking a Cocos web-mobile output chromium
  is the closest render target to what the end user sees.

* ``wait_ms`` gives the page time to run scripts AFTER the
  ``networkidle`` event fires. Cocos's web build loads its engine
  bundle + assets, then kicks off rendering; ``networkidle`` can
  return before the first frame draws. 500ms is a conservative
  default that covers most scenes.
"""
from __future__ import annotations

# Install-guidance message that any ImportError path ends up showing.
# Kept as a single string so both raise sites say the exact same thing.
_INSTALL_HINT = (
    "playwright is not installed. Install with:\n"
    "    uv pip install playwright\n"
    "    playwright install chromium\n"
    "(~200 MB disk; needed only for cocos_screenshot_preview)"
)


def screenshot_url(url: str,
                   viewport_width: int = 960,
                   viewport_height: int = 640,
                   wait_ms: int = 500,
                   full_page: bool = False,
                   timeout_ms: int = 15000) -> bytes:
    """Navigate chromium to ``url`` and return the rendered PNG as bytes.

    Raises :class:`ImportError` with install instructions if playwright
    isn't available, :class:`RuntimeError` on navigation failure, or
    :class:`TimeoutError` when the page never settles.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(_INSTALL_HINT) from e

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            # Most often: "playwright install" was never run, so the
            # browser binary doesn't exist even though the python
            # package imports fine.
            raise RuntimeError(
                f"failed to launch chromium: {e}. "
                "Run `playwright install chromium` to download the browser binary."
            ) from e

        try:
            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as e:
                raise RuntimeError(
                    f"failed to navigate to {url}: {e}. "
                    "Is the preview server actually running? "
                    "Check cocos_preview_status."
                ) from e

            # Cocos's web build finishes asset loading before rendering
            # starts, so networkidle fires before the first frame is on
            # screen. Explicit sleep beats polling the canvas pixel
            # buffer, which isn't reliably visible via DOM APIs.
            page.wait_for_timeout(wait_ms)

            png_bytes = page.screenshot(full_page=full_page, type="png")
            return png_bytes
        finally:
            browser.close()

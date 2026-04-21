"""Tests for the closed-feedback-loop interaction module (cocos.interact).

These mirror tests/test_visual_feedback.py's Playwright-mocking style:
we patch sys.modules["playwright.sync_api"] with a MagicMock whose
``sync_playwright`` callable returns a fake context-manager chain, so
CI doesn't need a real chromium. The one tool that's pure Pillow
(``snapshot_diff``) gets exercised against real in-memory PNGs built
with PIL.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import interact as inter


# ---------- shared helpers ---------- #

def _fake_playwright():
    """Return (fake_pw_api_cm, fake_page) pair — wire the cm into
    sys.modules["playwright.sync_api"].sync_playwright and all six
    per-call tools will happily drive ``fake_page``."""
    fake_page = mock.MagicMock()
    # Default screenshot bytes for any screenshot-returning path.
    fake_page.screenshot.return_value = b"\x89PNG\r\n\x1a\nFAKE"

    fake_ctx = mock.MagicMock()
    fake_ctx.new_page.return_value = fake_page

    fake_browser = mock.MagicMock()
    fake_browser.new_context.return_value = fake_ctx

    fake_chromium = mock.MagicMock()
    fake_chromium.launch.return_value = fake_browser

    fake_pw_api = mock.MagicMock()
    fake_pw_api.__enter__.return_value = mock.MagicMock(chromium=fake_chromium)
    fake_pw_api.__exit__.return_value = None

    return fake_pw_api, fake_page, fake_browser


def _patch_playwright(fake_pw_api):
    """Context manager — swap sys.modules so lazy imports see our mock."""
    return mock.patch.dict(sys.modules, {
        "playwright": mock.MagicMock(),
        "playwright.sync_api": mock.MagicMock(sync_playwright=lambda: fake_pw_api),
    })


def _png_bytes(color: tuple[int, int, int], size=(16, 16)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ======================================================== #
# 1. ImportError path — same install hint as screenshot.py
# ======================================================== #

def test_click_preview_missing_playwright_raises_install_hint():
    with mock.patch.dict(sys.modules, {"playwright.sync_api": None}):
        with pytest.raises(ImportError, match="playwright install chromium"):
            inter.click_preview("http://localhost/", 10, 20)


def test_read_preview_state_missing_playwright_raises_install_hint():
    with mock.patch.dict(sys.modules, {"playwright.sync_api": None}):
        with pytest.raises(ImportError, match="playwright install chromium"):
            inter.read_preview_state("http://localhost/")


def test_run_sequence_missing_playwright_raises_install_hint():
    with mock.patch.dict(sys.modules, {"playwright.sync_api": None}):
        with pytest.raises(ImportError, match="playwright install chromium"):
            inter.run_preview_sequence("http://localhost/", [])


# ======================================================== #
# 2. click_preview wires through correctly
# ======================================================== #

def test_click_preview_wires_coords_and_viewport():
    fake_pw, fake_page, fake_browser = _fake_playwright()
    with _patch_playwright(fake_pw):
        inter.click_preview("http://example.com/",
                            x=123, y=456, button="right", wait_ms=77,
                            viewport_width=1280, viewport_height=720)
    fake_page.mouse.click.assert_called_once_with(123, 456, button="right")
    fake_page.wait_for_timeout.assert_called_with(77)
    # viewport propagated through new_context
    viewport = fake_browser.new_context.call_args.kwargs["viewport"]
    assert viewport == {"width": 1280, "height": 720}
    fake_browser.close.assert_called_once()


# ======================================================== #
# 3. press_key / type_text
# ======================================================== #

def test_press_key_calls_keyboard_press():
    fake_pw, fake_page, _ = _fake_playwright()
    with _patch_playwright(fake_pw):
        inter.press_key("http://example.com/", "Enter", wait_ms=100)
    fake_page.keyboard.press.assert_called_once_with("Enter")
    fake_page.wait_for_timeout.assert_called_with(100)


def test_type_text_calls_keyboard_type():
    fake_pw, fake_page, _ = _fake_playwright()
    with _patch_playwright(fake_pw):
        inter.type_text("http://example.com/", "Hello World!")
    fake_page.keyboard.type.assert_called_once_with("Hello World!")


# ======================================================== #
# 4. drag emits intermediate moves
# ======================================================== #

def test_drag_emits_down_intermediate_moves_up():
    fake_pw, fake_page, _ = _fake_playwright()
    with _patch_playwright(fake_pw):
        inter.drag_preview("http://x/", from_x=0, from_y=0,
                           to_x=100, to_y=100, steps=4)
    # Start move + 4 interpolated moves = 5 total. Down + up exactly once.
    assert fake_page.mouse.move.call_count == 5
    fake_page.mouse.down.assert_called_once()
    fake_page.mouse.up.assert_called_once()
    # Final interpolated move lands on the target.
    last_move_args = fake_page.mouse.move.call_args_list[-1].args
    assert last_move_args == (100, 100)


def test_drag_steps_floor_of_one_still_works():
    """steps=0 would give divide-by-zero. Guard floor-clamps to 1."""
    fake_pw, fake_page, _ = _fake_playwright()
    with _patch_playwright(fake_pw):
        inter.drag_preview("http://x/", 0, 0, 50, 50, steps=0)
    # 1 start move + 1 interpolated move = 2 total.
    assert fake_page.mouse.move.call_count == 2


# ======================================================== #
# 5. read_preview_state success + failure
# ======================================================== #

def test_read_preview_state_returns_value_on_success():
    fake_pw, fake_page, _ = _fake_playwright()
    fake_page.evaluate.return_value = {"score": 42}
    with _patch_playwright(fake_pw):
        out = inter.read_preview_state(
            "http://x/", expression="window.game", wait_ms=50)
    fake_page.evaluate.assert_called_once_with("window.game")
    assert out == {"ok": True, "value": {"score": 42}, "error": None}


def test_read_preview_state_catches_eval_errors():
    """Arbitrary JS can throw — tool must not let it escape as an
    unhandled exception, else one bad expression poisons the MCP call."""
    fake_pw, fake_page, _ = _fake_playwright()
    fake_page.evaluate.side_effect = RuntimeError("ReferenceError: foo is not defined")
    with _patch_playwright(fake_pw):
        out = inter.read_preview_state("http://x/", expression="foo.bar")
    assert out["ok"] is False
    assert out["value"] is None
    assert "foo is not defined" in out["error"]


# ======================================================== #
# 6. wait_for_preview
# ======================================================== #

def test_wait_for_preview_sleeps_then_closes():
    fake_pw, fake_page, fake_browser = _fake_playwright()
    with _patch_playwright(fake_pw):
        inter.wait_for_preview("http://x/", ms=333)
    fake_page.wait_for_timeout.assert_called_with(333)
    fake_browser.close.assert_called_once()


# ======================================================== #
# 7. run_preview_sequence — mixed actions, single session
# ======================================================== #

def test_run_preview_sequence_executes_mixed_actions_in_one_session():
    fake_pw, fake_page, fake_browser = _fake_playwright()
    fake_page.evaluate.return_value = 7
    fake_page.screenshot.return_value = b"\x89PNG\r\n\x1a\nZZZ"

    with _patch_playwright(fake_pw):
        out = inter.run_preview_sequence("http://x/", [
            {"kind": "click", "x": 10, "y": 20, "wait_ms": 50},
            {"kind": "key", "key": "Space"},
            {"kind": "type", "text": "hi"},
            {"kind": "drag", "from_x": 0, "from_y": 0,
             "to_x": 30, "to_y": 40, "steps": 3},
            {"kind": "wait", "ms": 10},
            {"kind": "read_state", "expression": "window.game.score"},
            {"kind": "screenshot"},
        ])

    # All 7 actions reported.
    assert len(out) == 7
    assert [e["kind"] for e in out] == [
        "click", "key", "type", "drag", "wait", "read_state", "screenshot"]
    assert all(e["ok"] for e in out)
    # read_state forwards the value.
    assert out[5]["result"] == {"value": 7}
    # screenshot is hex-encoded.
    assert out[6]["result"]["png_bytes_hex"] == b"\x89PNG\r\n\x1a\nZZZ".hex()
    # Browser launched / closed exactly once — single session.
    fake_browser.close.assert_called_once()


def test_run_preview_sequence_failed_action_doesnt_abort_rest():
    """A bad click mid-sequence must NOT kill the surrounding reads —
    otherwise an AI test plan loses all its hard-won state on one typo."""
    fake_pw, fake_page, _ = _fake_playwright()
    # The click will raise; read_state should still produce a value.
    fake_page.mouse.click.side_effect = RuntimeError("boom")
    fake_page.evaluate.return_value = "ok"

    with _patch_playwright(fake_pw):
        out = inter.run_preview_sequence("http://x/", [
            {"kind": "read_state", "expression": "a"},
            {"kind": "click", "x": 1, "y": 2},
            {"kind": "read_state", "expression": "b"},
        ])

    assert out[0]["ok"] is True
    assert out[0]["result"] == {"value": "ok"}
    assert out[1]["ok"] is False
    assert "boom" in out[1]["error"]
    assert out[2]["ok"] is True
    assert out[2]["result"] == {"value": "ok"}


def test_run_preview_sequence_unknown_kind_reports_error():
    fake_pw, _fake_page, _ = _fake_playwright()
    with _patch_playwright(fake_pw):
        out = inter.run_preview_sequence("http://x/", [
            {"kind": "moonwalk"},
        ])
    assert out[0]["ok"] is False
    assert "moonwalk" in out[0]["error"]


# ======================================================== #
# 8. snapshot_diff — pure Pillow, no playwright
# ======================================================== #

def test_snapshot_diff_identical_images_ratio_zero():
    png = _png_bytes((128, 64, 32))
    out = inter.snapshot_diff(png, png)
    assert out["diff_ratio"] == 0
    assert out["different_pixels"] == 0
    assert out["total_pixels"] == 16 * 16
    assert out["width"] == 16
    assert out["height"] == 16


def test_snapshot_diff_totally_different_ratio_one():
    black = _png_bytes((0, 0, 0))
    white = _png_bytes((255, 255, 255))
    out = inter.snapshot_diff(black, white)
    assert out["diff_ratio"] == 1.0
    assert out["different_pixels"] == 16 * 16


def test_snapshot_diff_below_threshold_not_counted():
    """Two nearly-identical images (delta 5) with threshold 8 should
    diff as zero — compression noise doesn't count as change."""
    a = _png_bytes((100, 100, 100))
    b = _png_bytes((105, 100, 100))  # 5-channel delta
    out = inter.snapshot_diff(a, b, threshold=8)
    assert out["diff_ratio"] == 0
    # Same pair with threshold=1 catches everything.
    out_strict = inter.snapshot_diff(a, b, threshold=1)
    assert out_strict["diff_ratio"] == 1.0


def test_snapshot_diff_accepts_file_paths(tmp_path: Path):
    a_path = tmp_path / "a.png"
    b_path = tmp_path / "b.png"
    a_path.write_bytes(_png_bytes((255, 0, 0)))
    b_path.write_bytes(_png_bytes((0, 255, 0)))
    out = inter.snapshot_diff(str(a_path), b_path)  # str OR Path both work
    assert out["diff_ratio"] == 1.0


def test_snapshot_diff_size_mismatch_raises():
    a = _png_bytes((0, 0, 0), size=(8, 8))
    b = _png_bytes((0, 0, 0), size=(16, 16))
    with pytest.raises(ValueError, match="size mismatch"):
        inter.snapshot_diff(a, b)


def test_snapshot_diff_works_without_playwright_installed():
    """Pure Pillow path — removing playwright from sys.modules should
    not affect snapshot_diff at all."""
    png = _png_bytes((42, 42, 42))
    with mock.patch.dict(sys.modules, {"playwright.sync_api": None}):
        out = inter.snapshot_diff(png, png)
    assert out["diff_ratio"] == 0


# ======================================================== #
# 9. chromium launch failure hint (parity with screenshot.py)
# ======================================================== #

def test_click_preview_launch_failure_message():
    fake_chromium = mock.MagicMock()
    fake_chromium.launch.side_effect = RuntimeError("executable not found")

    fake_pw_api = mock.MagicMock()
    fake_pw_api.__enter__.return_value = mock.MagicMock(chromium=fake_chromium)
    fake_pw_api.__exit__.return_value = None

    with mock.patch.dict(sys.modules, {
        "playwright": mock.MagicMock(),
        "playwright.sync_api": mock.MagicMock(sync_playwright=lambda: fake_pw_api),
    }):
        with pytest.raises(RuntimeError, match="playwright install chromium"):
            inter.click_preview("http://example.com/", 1, 2)

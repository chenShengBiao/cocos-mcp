"""Tests for the third UI/UX batch:

1. ``create_animation_clip`` now writes the caller-supplied wrap_mode
   (was hardcoded to 2 = Reverse, which silently broke every clip —
   regression guard keeps the fix from being reverted).
2. Four new animation presets: scale_in / bounce_in / pulse / shake.
3. ``cocos_screenshot_preview`` — Playwright-driven screenshots with
   lazy import + mocked Playwright so CI doesn't pull down chromium.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import project as cp
from cocos import scene_builder as sb
from cocos.project import animation as anim_mod


def _make_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    (p / "assets").mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "demo"}))
    return p


def _scene_in_project(proj: Path) -> tuple[Path, dict]:
    cp.set_ui_theme(str(proj), theme="dark_game")
    scene = proj / "assets" / "scenes" / "main.scene"
    scene.parent.mkdir(parents=True)
    info = sb.create_empty_scene(scene)
    return scene, info


def _clip_wrap_mode(clip_path: Path) -> int:
    with open(clip_path) as f:
        data = json.load(f)
    return data[0]["wrapMode"]


# ================================================ #
# 1. wrap_mode bug fix on create_animation_clip
# ================================================ #

def test_create_animation_clip_defaults_to_wrap_normal(tmp_path: Path):
    """Previously hardcoded to 2 (WrapMode.Reverse) which plays the
    clip once in reverse — the silent cause of 'my animation doesn't
    play'. New default is 1 (WrapMode.Normal = play once forward)."""
    proj = _make_project(tmp_path)
    res = anim_mod.create_animation_clip(
        str(proj), "test_clip", duration=1.0,
        tracks=[{"path": "", "property": "opacity",
                 "keyframes": [{"time": 0, "value": 0},
                               {"time": 1.0, "value": 255}]}],
    )
    assert _clip_wrap_mode(Path(res["path"])) == 1


def test_create_animation_clip_wrap_mode_passthrough(tmp_path: Path):
    """Explicit wrap_mode gets written verbatim — so callers needing
    Loop=4 or PingPong=22 can opt in."""
    proj = _make_project(tmp_path)
    for mode in (1, 2, 4, 22, 36):
        res = anim_mod.create_animation_clip(
            str(proj), f"wrap_{mode}", duration=0.5,
            tracks=[{"path": "", "property": "opacity",
                     "keyframes": [{"time": 0, "value": 0},
                                   {"time": 0.5, "value": 128}]}],
            wrap_mode=mode,
        )
        assert _clip_wrap_mode(Path(res["path"])) == mode, (
            f"wrap_mode={mode} not preserved in serialized clip")


def test_fade_in_uses_wrap_normal(tmp_path: Path):
    """Regression guard: fade_in must NOT loop forever (old behaviour
    emitted wrap_mode=2, which was Reverse — effectively no fade)."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Fader")
    res = sb.add_fade_in(scene, n)
    assert _clip_wrap_mode(Path(res["clip_path"])) == 1


def test_slide_in_uses_wrap_normal(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Panel", lpos=(50, 50, 0))
    res = sb.add_slide_in(scene, n)
    assert _clip_wrap_mode(Path(res["clip_path"])) == 1


# ================================================ #
# 2. New animation presets
# ================================================ #

def test_scale_in_produces_scale_track_from_zero_to_one(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    res = sb.add_scale_in(scene, n, from_scale=0.0, duration=0.3)
    with open(res["clip_path"]) as f:
        clip = json.load(f)
    # Three RealCurves (x/y/z scale channels)
    curves = [o for o in clip if o.get("__type__") == "cc.animation.RealCurve"]
    assert len(curves) == 3
    # Each channel starts at from_scale and ends at 1.0
    for curve in curves:
        assert curve["_values"][0]["value"] == 0.0
        assert curve["_values"][-1]["value"] == 1.0
    # wrap_mode = Normal (play once)
    assert clip[0]["wrapMode"] == 1


def test_scale_in_from_half_only_reaches_half_at_start(tmp_path: Path):
    """from_scale=0.5 means grow from half-size, not from zero."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    res = sb.add_scale_in(scene, n, from_scale=0.5)
    with open(res["clip_path"]) as f:
        clip = json.load(f)
    curves = [o for o in clip if o.get("__type__") == "cc.animation.RealCurve"]
    assert curves[0]["_values"][0]["value"] == 0.5


def test_bounce_in_overshoots_past_one_then_settles(tmp_path: Path):
    """bounce_in is a 3-keyframe curve: 0 → overshoot → 1.0. Without
    that middle keyframe it's just a scale_in."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    res = sb.add_bounce_in(scene, n, overshoot=1.2, duration=0.5)
    with open(res["clip_path"]) as f:
        clip = json.load(f)
    curves = [o for o in clip if o.get("__type__") == "cc.animation.RealCurve"]
    # Per-axis curve has 3 values: 0, 1.2, 1.0
    values = [v["value"] for v in curves[0]["_values"]]
    assert values == [0.0, 1.2, 1.0]


def test_pulse_uses_wrap_loop(tmp_path: Path):
    """pulse is the one preset that MUST loop — verify wrap_mode is Loop=4."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    res = sb.add_pulse(scene, n, strength=0.1, period=1.0)
    with open(res["clip_path"]) as f:
        clip = json.load(f)
    assert clip[0]["wrapMode"] == 4  # WrapMode.Loop
    # 3 keyframes: 1.0 → peak → 1.0 so it smoothly loops
    curves = [o for o in clip if o.get("__type__") == "cc.animation.RealCurve"]
    values = [v["value"] for v in curves[0]["_values"]]
    assert values == [1.0, 1.1, 1.0]


def test_shake_oscillates_around_current_position(tmp_path: Path):
    """Shake MUST read the node's _lpos and oscillate around it — not
    around (0,0,0), which would fling the node across the screen."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "Victim",
                    lpos=(300, 100, 0))
    res = sb.add_shake(scene, n, intensity=20.0, duration=0.3, axis="x")
    with open(res["clip_path"]) as f:
        clip = json.load(f)
    curves = [o for o in clip if o.get("__type__") == "cc.animation.RealCurve"]
    # x curve should oscillate near 300 (base position)
    x_values = [v["value"] for v in curves[0]["_values"]]
    assert max(x_values) <= 320  # base + full intensity
    assert min(x_values) >= 280  # base - full intensity
    assert x_values[-1] == 300   # final keyframe back at rest
    # y curve stays flat at 100 (base y) for axis="x"
    y_values = [v["value"] for v in curves[1]["_values"]]
    assert all(abs(v - 100) < 0.001 for v in y_values)


def test_shake_axis_both_moves_both_channels(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X", lpos=(0, 0, 0))
    res = sb.add_shake(scene, n, axis="both")
    with open(res["clip_path"]) as f:
        clip = json.load(f)
    curves = [o for o in clip if o.get("__type__") == "cc.animation.RealCurve"]
    x_values = [v["value"] for v in curves[0]["_values"]]
    y_values = [v["value"] for v in curves[1]["_values"]]
    # Both channels should have at least one non-zero displacement
    assert any(abs(v) > 0.1 for v in x_values)
    assert any(abs(v) > 0.1 for v in y_values)


def test_shake_rejects_bad_axis(tmp_path: Path):
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)
    n = sb.add_node(scene, info["canvas_node_id"], "X")
    with pytest.raises(ValueError, match="axis"):
        sb.add_shake(scene, n, axis="diagonal")


def test_all_new_presets_attach_cc_animation(tmp_path: Path):
    """Each preset must attach a cc.Animation pointing at its clip —
    otherwise the .anim file is orphaned and nothing plays."""
    proj = _make_project(tmp_path)
    scene, info = _scene_in_project(proj)

    for preset_fn, name in [(sb.add_scale_in, "ScaleNode"),
                            (sb.add_bounce_in, "BounceNode"),
                            (sb.add_pulse, "PulseNode"),
                            (sb.add_shake, "ShakeNode")]:
        n = sb.add_node(scene, info["canvas_node_id"], name)
        res = preset_fn(scene, n)
        with open(scene) as f:
            scene_data = json.load(f)
        anim_cmp = scene_data[res["anim_component_id"]]
        assert anim_cmp["__type__"] == "cc.Animation"
        assert anim_cmp["_defaultClip"]["__uuid__"] == res["clip_uuid"]


# ================================================ #
# 3. Screenshot tool — mocked Playwright
# ================================================ #

def test_screenshot_missing_playwright_raises_install_hint():
    """Users without playwright installed should get pointed at the
    install command, not a bare ImportError."""
    from cocos import screenshot as sshot

    # Temporarily hide playwright.sync_api so the import fails
    with mock.patch.dict(sys.modules, {"playwright.sync_api": None}):
        with pytest.raises(ImportError, match="playwright install chromium"):
            sshot.screenshot_url("http://localhost/")


def test_screenshot_url_calls_playwright_and_returns_bytes(tmp_path: Path):
    """End-to-end with mocked Playwright — verify the function wires
    through viewport, wait, and screenshot calls correctly."""
    from cocos import screenshot as sshot

    fake_png = b"\x89PNG\r\n\x1a\nFAKE"

    # Mock the sync_playwright context manager and the chain of calls
    fake_page = mock.MagicMock()
    fake_page.screenshot.return_value = fake_png

    fake_ctx = mock.MagicMock()
    fake_ctx.new_page.return_value = fake_page

    fake_browser = mock.MagicMock()
    fake_browser.new_context.return_value = fake_ctx

    fake_chromium = mock.MagicMock()
    fake_chromium.launch.return_value = fake_browser

    fake_pw_api = mock.MagicMock()
    fake_pw_api.__enter__.return_value = mock.MagicMock(chromium=fake_chromium)
    fake_pw_api.__exit__.return_value = None

    with mock.patch.dict(sys.modules, {
        "playwright": mock.MagicMock(),
        "playwright.sync_api": mock.MagicMock(sync_playwright=lambda: fake_pw_api),
    }):
        out = sshot.screenshot_url("http://example.com/",
                                   viewport_width=1280, viewport_height=720,
                                   wait_ms=200)

    assert out == fake_png
    # viewport is passed in via new_context
    fake_browser.new_context.assert_called_once()
    viewport_arg = fake_browser.new_context.call_args.kwargs["viewport"]
    assert viewport_arg == {"width": 1280, "height": 720}
    # goto called with networkidle wait condition
    fake_page.goto.assert_called_once()
    assert fake_page.goto.call_args.kwargs["wait_until"] == "networkidle"
    # wait_ms forwarded to wait_for_timeout
    fake_page.wait_for_timeout.assert_called_with(200)
    # screenshot called with format="png"
    fake_page.screenshot.assert_called_once()
    assert fake_page.screenshot.call_args.kwargs["type"] == "png"


def test_screenshot_browser_launch_failure_message(tmp_path: Path):
    """When chromium binary isn't downloaded (user skipped
    ``playwright install``), surface that cause rather than the raw
    Playwright exception."""
    from cocos import screenshot as sshot

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
            sshot.screenshot_url("http://example.com/")

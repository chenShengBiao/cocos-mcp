"""Tests for cocos.gen_asset — pure helpers + HTTP paths via mocked urllib.

Network calls are mocked so the suite stays offline + deterministic.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos import gen_asset as ga

# ============================================================
#  Pure helpers
# ============================================================

def test_snap_zhipu_size_picks_closest_aspect():
    # 16:9 (~1.78) → 1344x768 (1.75) is closer than 1440x720 (2.0)
    assert ga._snap_zhipu_size(1920, 1080) == (1344, 768)
    # Square in → square out
    assert ga._snap_zhipu_size(1024, 1024) == (1024, 1024)
    # 9:16 portrait (~0.563) → 768x1344 (~0.571) closer than 720x1440 (0.5)
    assert ga._snap_zhipu_size(720, 1280) == (768, 1344)
    # Extreme portrait 1:2 (0.5) snaps to 720x1440 (0.5) exactly
    assert ga._snap_zhipu_size(500, 1000) == (720, 1440)


def test_build_pollinations_url_encodes_prompt_and_params():
    url = ga.build_pollinations_url("a happy bird & dog", 800, 600, 42, "flux")
    # Prompt fully URL-encoded (spaces → %20, & → %26)
    assert "a%20happy%20bird%20%26%20dog" in url
    assert "width=800" in url
    assert "height=600" in url
    assert "seed=42" in url
    assert "model=flux" in url
    assert "nologo=true" in url
    assert url.startswith("https://image.pollinations.ai/prompt/")


# ============================================================
#  _save_as_png
# ============================================================

def _png_bytes(w: int = 8, h: int = 8, color=(255, 0, 0)) -> bytes:
    """Build a real in-memory PNG."""
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def test_save_as_png_converts_to_rgba(tmp_path: Path):
    raw = _png_bytes()  # RGB
    out = tmp_path / "x.png"
    size = ga._save_as_png(raw, out)
    assert size > 0
    img = Image.open(out)
    assert img.mode == "RGBA"


def test_save_as_png_handles_jpeg_input(tmp_path: Path):
    """Pollinations actually returns JPEG with .png extension — verify
    we re-encode to true PNG so make_transparent.py can chroma-key it."""
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 200, 30)).save(buf, "JPEG")
    out = tmp_path / "fromjpg.png"
    ga._save_as_png(buf.getvalue(), out)
    img = Image.open(out)
    assert img.format == "PNG"
    assert img.mode == "RGBA"


# ============================================================
#  _strip_zhipu_watermark
# ============================================================

def _zhipu_image_with_badge() -> Image.Image:
    """Build a 600x400 white image with a grey 'badge' in the bottom-right
    corner that mimics the AI生成 watermark Zhipu burns in."""
    img = Image.new("RGB", (600, 400), (255, 255, 255))
    px = img.load()
    # Solid grey rectangle ~200x70 in bottom-right
    for x in range(380, 580):
        for y in range(310, 380):
            px[x, y] = (160, 160, 160)
    return img


def test_strip_zhipu_watermark_replaces_badge_region(tmp_path: Path):
    img = _zhipu_image_with_badge()
    cleaned = ga._strip_zhipu_watermark(img)
    assert cleaned.mode == "RGBA"
    # Center of the original badge should now be white again (or nearly so)
    r, g, b, _ = cleaned.getpixel((480, 345))
    assert (r, g, b) == (255, 255, 255), \
        f"badge area should be whitened, got rgb=({r},{g},{b})"


def test_strip_zhipu_watermark_skips_when_no_badge():
    """If the image has no badge-like grey region in the corner, the function
    should leave the pixels alone (warns to stderr but returns RGBA copy)."""
    img = Image.new("RGB", (200, 200), (255, 255, 255))   # pure white, no badge
    cleaned = ga._strip_zhipu_watermark(img)
    assert cleaned.mode == "RGBA"
    # All pixels still white
    for x in (0, 100, 199):
        for y in (0, 100, 199):
            assert cleaned.getpixel((x, y))[:3] == (255, 255, 255)


# ============================================================
#  HTTP paths — mocked urllib
# ============================================================

class _FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _noisy_png_bytes(size_px: int = 64) -> bytes:
    """Build a high-entropy PNG that won't compress below 1 KB.

    gen_pollinations rejects payloads < 1024 bytes as 'likely an error',
    so test fixtures need actual entropy or PIL's PNG zlib compresses
    them down to ~200 bytes.
    """
    import os as _os
    img = Image.frombytes("RGB", (size_px, size_px), _os.urandom(size_px * size_px * 3))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_gen_pollinations_writes_png(tmp_path: Path, monkeypatch):
    payload = _noisy_png_bytes(64)
    assert len(payload) > 1024, f"fixture too small ({len(payload)} bytes)"
    monkeypatch.setattr(ga, "_http_get", lambda url, headers, timeout=180: payload)

    out = tmp_path / "p.png"
    size = ga.gen_pollinations("a cat", 64, 64, 7, "flux", out)
    assert size > 0
    assert Image.open(out).mode == "RGBA"


def test_gen_pollinations_rejects_too_small_response(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ga, "_http_get", lambda url, headers, timeout=180: b"err")
    with pytest.raises(RuntimeError, match="response too small"):
        ga.gen_pollinations("x", 64, 64, 1, "flux", tmp_path / "p.png")


def test_gen_zhipu_happy_path(tmp_path: Path, monkeypatch):
    """Mock both API calls: the JSON POST that returns an image URL,
    and the GET that downloads the image bytes."""
    monkeypatch.setenv("ZHIPU_API_KEY", "test-key-abc")
    img_payload = _noisy_png_bytes(64)  # >1 KB so it passes the size guard

    def fake_post(url, headers, body, timeout=180):
        assert "Bearer test-key-abc" in headers["Authorization"]
        assert body["prompt"] == "a sword"
        assert body["size"] == "1024x1024"
        return {"data": [{"url": "https://example.com/zhipu-output.png"}]}

    def fake_get(url, headers, timeout=180):
        assert url == "https://example.com/zhipu-output.png"
        return img_payload

    monkeypatch.setattr(ga, "_http_post_json", fake_post)
    monkeypatch.setattr(ga, "_http_get", fake_get)

    out = tmp_path / "sword.png"
    # strip_watermark=False — our synthetic 1024² is pure white with no badge
    size = ga.gen_zhipu("a sword", 1024, 1024, 0, "cogview-3-flash", out,
                       strip_watermark=False)
    assert size > 0
    assert Image.open(out).mode == "RGBA"


def test_gen_zhipu_raises_when_response_missing_url(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "k")
    monkeypatch.setattr(ga, "_http_post_json",
                        lambda *a, **kw: {"data": []})
    with pytest.raises(RuntimeError, match="missing image url"):
        ga.gen_zhipu("x", 1024, 1024, 0, "cogview-3-flash", tmp_path / "x.png")


def test_get_zhipu_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "env-key-123")
    assert ga._get_zhipu_key() == "env-key-123"


def test_get_zhipu_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    monkeypatch.setattr(ga, "_load_env_file", lambda p: {})  # no .env hit
    with pytest.raises(RuntimeError, match="ZHIPU_API_KEY not set"):
        ga._get_zhipu_key()

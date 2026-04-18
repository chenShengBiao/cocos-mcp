"""Tests for cocos.make_transparent — saturation+darkness chroma key.

The algorithm splits each pixel into three score buckets:
  * white / pale-grey background → score=0   → alpha=0   (transparent)
  * dark foreground (black metal) → score≥60 → alpha=255 (opaque)
  * colored foreground (any hue)  → score≥60 → alpha=255 (opaque)

We construct a synthetic 3-region image and assert each region falls into
the right bucket, then nudge --low/--high to verify the linear ramp.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.make_transparent import make_transparent


def _make_three_region_png(path: Path, w: int = 90, h: int = 30) -> None:
    """Left third white (background), middle red (colored fg), right black (dark fg)."""
    img = Image.new("RGB", (w, h), (255, 255, 255))
    px = img.load()
    third = w // 3
    for x in range(third, 2 * third):
        for y in range(h):
            px[x, y] = (220, 30, 30)  # vivid red, sat=190, darkness=110
    for x in range(2 * third, w):
        for y in range(h):
            px[x, y] = (10, 10, 10)   # near-black, sat=0, darkness=190
    img.save(path)


def test_chroma_key_preserves_color_and_dark_kills_white(tmp_path: Path):
    src = tmp_path / "src.png"
    out = tmp_path / "out.png"
    _make_three_region_png(src)
    make_transparent(src, out)

    img = Image.open(out).convert("RGBA")
    w, h = img.size
    third = w // 3
    bg_alpha = img.getpixel((third // 2, h // 2))[3]
    color_alpha = img.getpixel((third + third // 2, h // 2))[3]
    dark_alpha = img.getpixel((2 * third + third // 2, h // 2))[3]

    assert bg_alpha == 0, f"white background should be transparent, got alpha={bg_alpha}"
    assert color_alpha == 255, f"vivid red should be opaque, got alpha={color_alpha}"
    assert dark_alpha == 255, f"near-black should be opaque, got alpha={dark_alpha}"


def test_low_high_thresholds_control_ramp(tmp_path: Path):
    """A mid-grey pixel (~score 80) should:
      - be opaque under default thresholds (low=25, high=60)
      - become transparent under aggressive low=200
    """
    src = tmp_path / "g.png"
    Image.new("RGB", (4, 4), (140, 140, 140)).save(src)  # darkness=60, sat=0 → score=60

    out_default = tmp_path / "out1.png"
    make_transparent(src, out_default, low=25, high=60)
    a_def = Image.open(out_default).convert("RGBA").getpixel((2, 2))[3]
    assert a_def == 255  # score ≥ high → opaque

    out_aggressive = tmp_path / "out2.png"
    make_transparent(src, out_aggressive, low=200, high=400)
    a_agg = Image.open(out_aggressive).convert("RGBA").getpixel((2, 2))[3]
    assert a_agg == 0  # score < low → transparent


def test_intermediate_score_produces_partial_alpha(tmp_path: Path):
    """A pixel whose score is exactly mid-way between low and high should
    end up with alpha ≈ 128 (linear ramp)."""
    # Pure grey (200, 200, 200): sat=0, darkness=0 → score=0
    # Use (180, 180, 180): sat=0, darkness=20 → score=20
    src = tmp_path / "midgrey.png"
    Image.new("RGB", (4, 4), (180, 180, 180)).save(src)

    out = tmp_path / "out.png"
    # Low=10 high=30, score=20 → middle of ramp → alpha ≈ 127
    make_transparent(src, out, low=10, high=30)
    alpha = Image.open(out).convert("RGBA").getpixel((2, 2))[3]
    assert 100 <= alpha <= 155, f"expected mid-ramp alpha ~128, got {alpha}"


def test_feather_blurs_alpha_edge(tmp_path: Path):
    """feather > 0 applies a Gaussian blur to the alpha channel; edges
    should soften (no hard 0/255 transitions)."""
    src = tmp_path / "src.png"
    _make_three_region_png(src, w=60, h=20)
    out = tmp_path / "feathered.png"
    make_transparent(src, out, feather=4)

    img = Image.open(out).convert("RGBA")
    # Sample alphas across the white→red boundary; should pick up at least
    # one mid-range value (neither 0 nor 255) due to Gaussian smoothing.
    alphas = {img.getpixel((x, 10))[3] for x in range(15, 25)}
    mid_values = [a for a in alphas if 0 < a < 255]
    assert mid_values, f"expected feathered transition, alphas were {sorted(alphas)}"


def test_inplace_via_make_transparent_overwrites_input(tmp_path: Path):
    """Passing the same path as input and output should mutate the original."""
    p = tmp_path / "src.png"
    _make_three_region_png(p, w=30, h=10)
    before = Image.open(p).mode
    assert before == "RGB"  # input was RGB

    make_transparent(p, p)

    after_img = Image.open(p)
    assert after_img.mode == "RGBA", "after make_transparent the file should be RGBA"
    # Background pixel must now be transparent
    assert after_img.getpixel((2, 5))[3] == 0


def test_non_existent_input_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        make_transparent(tmp_path / "nope.png", tmp_path / "out.png")

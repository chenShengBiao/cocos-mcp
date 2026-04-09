#!/usr/bin/env python3
"""
make_transparent.py - 把 gen.py 生成的素材的浅色背景抠掉，输出真正透明 PNG。

算法：饱和度 + 暗度双信号 (saturation-bonus chroma key)
  对每个像素计算"前景分数"：
    saturation = max(R,G,B) - min(R,G,B)        # 彩色程度
    darkness   = max(0, 200 - (R+G+B)/3)        # 暗于浅灰的程度
    score      = saturation + darkness

  - 白底 / 浅灰底：sat≈0, lum 高 → score ≈ 0           → 全透明 ✓
  - 蓝色光晕：sat 高                                   → score 高 → 全保留 ✓
  - 黑色金属前景：sat≈0 但 lum 低 → darkness 高         → score 高 → 全保留 ✓
  - 内部白色高光：sat≈0, lum 高 → 当成背景透明（小范围损失可接受）

  最后线性映射 score → alpha：
    score ≤ low  → alpha=0
    score ≥ high → alpha=255
    中间区间    → 渐变（天然抗锯齿）

为什么不用 floodfill / 单一 manhattan distance：
  之前两版的失败：
  v1 floodfill: 不连通的"飞地"白底永远到不了；光晕环绕时撞光晕停
  v2 manhattan distance to bg color: Pollinations 的"白底"实际是
       渐变浅灰 (RGB 240~255)，4 角中位估计 + manhattan 把大块灰度
       渐变判成"半透明边缘"，整图发虚

  本版直接看像素自身的"是不是彩色 / 是不是暗色"，根本不依赖 4 角采样，
  对 AI 生成的浅色底图鲁棒得多。

为什么不用 rembg：
  rembg 依赖 ML 模型 (~100MB+)，对游戏素材这种"前景明确、背景近纯色"
  的场景过度设计。

适用场景：
  ✓ icon / item / pixel / ui (背景纯色)
  ✓ character (白底立绘)
  ✗ scene / tile / portrait (整图都有内容，没有"背景")
    → 这些 style 不应该调用本脚本

用法：
  python3 make_transparent.py <input.png>
  python3 make_transparent.py <input.png> --low 20 --high 80
  python3 make_transparent.py <input.png> --output custom.png
  python3 make_transparent.py <input.png> --inplace   # 直接覆盖原图

参数调优：
  --low N      (默认 25) 前景分数 ≤ N 的像素全透明。
                          背景没抠干净就调大；前景被吃就调小。
  --high N     (默认 60) 前景分数 ≥ N 的像素完全保留。
                          前景边缘半透明就调小。
  --feather N  (默认 0)  额外高斯羽化半径，通常不需要。
"""
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError:
    print("ERROR: Pillow not installed. Run: pip3 install Pillow", file=sys.stderr)
    sys.exit(1)


def make_transparent(
    input_path: Path,
    output_path: Path,
    low: int = 25,
    high: int = 60,
    feather: int = 0,
) -> None:
    img = Image.open(input_path).convert("RGBA")
    rgb = img.convert("RGB")
    r, g, b = rgb.split()

    # ── 信号 1: saturation = max(R,G,B) - min(R,G,B) ──
    # 越彩色越大；纯白/纯灰为 0
    max_ch = ImageChops.lighter(ImageChops.lighter(r, g), b)
    min_ch = ImageChops.darker(ImageChops.darker(r, g), b)
    saturation = ImageChops.subtract(max_ch, min_ch)

    # ── 信号 2: darkness bonus = max(0, 200 - luminance) ──
    # 让"暗灰/黑色前景"也能拿到高分（saturation 接近 0 但需要保留）
    # luminance 用 PIL 内置 RGB→L 转换（0.299R + 0.587G + 0.114B）
    luminance = rgb.convert("L")
    darkness = luminance.point(lambda v: max(0, 200 - v))

    # ── 综合分数 = saturation + darkness ──
    # ImageChops.add 在 255 处 clamp，但实际 score 会被 high 截断，无害
    score = ImageChops.add(saturation, darkness)

    # ── 线性映射 score → alpha ──
    span = max(1, high - low)

    def to_alpha(s: int, lo: int = low, hi: int = high, sp: int = span) -> int:
        if s <= lo:
            return 0
        if s >= hi:
            return 255
        return ((s - lo) * 255) // sp

    alpha = score.point(to_alpha)

    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=feather))

    img.putalpha(alpha)
    img.save(output_path, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove plain background from generated game assets (chroma key).",
    )
    parser.add_argument("input", help="Input PNG path")
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output path (default: <input>-transparent.png)",
    )
    parser.add_argument(
        "--inplace", action="store_true",
        help="Overwrite input file in place",
    )
    parser.add_argument(
        "--low", type=int, default=25,
        help="Foreground score ≤ this → fully transparent (default: 25). "
             "Increase if background residue remains; decrease if foreground gets eaten.",
    )
    parser.add_argument(
        "--high", type=int, default=60,
        help="Foreground score ≥ this → fully opaque (default: 60). "
             "Decrease if foreground edges become semi-transparent.",
    )
    parser.add_argument(
        "--feather", "-f", type=int, default=0,
        help="Extra Gaussian blur radius on alpha (default: 0). "
             "Chroma key already anti-aliases; "
             "set 1 only if foreground edge has speckle.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}", file=sys.stderr)
        return 1

    if args.inplace:
        output_path = input_path
    elif args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = input_path.with_name(input_path.stem + "-transparent.png")

    print(f"In   : {input_path}", file=sys.stderr)
    print(f"Out  : {output_path}", file=sys.stderr)
    print(f"Low={args.low}  High={args.high}  Feather={args.feather}", file=sys.stderr)

    try:
        make_transparent(
            input_path,
            output_path,
            low=args.low,
            high=args.high,
            feather=args.feather,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"OK   {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

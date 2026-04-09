#!/usr/bin/env python3
"""Generate game assets via Pollinations.ai (free) or 智谱 CogView (free, faster in CN)."""
import argparse
import hashlib
import json
import os
import random
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PROVIDERS = ("pollinations", "zhipu")

# 智谱 CogView-3-Flash 仅支持这几种固定尺寸；任意 W/H 会被 snap 到最近宽高比
ZHIPU_SIZES = [
    (1024, 1024),
    (768, 1344),
    (1344, 768),
    (864, 1152),
    (1152, 864),
    (720, 1440),
    (1440, 720),
]

STYLES = {
    "pixel": "pixel art, 16-bit retro game sprite, crisp pixels, {prompt}, transparent background, centered, clean",
    "icon": "game icon, {prompt}, clean vibrant design, centered composition, transparent background, high detail, sharp",
    "character": "game character concept art, {prompt}, full body, dynamic pose, highly detailed, white background",
    "tile": "seamless tileable texture, {prompt}, game asset, top-down view, repeating pattern",
    "ui": "game UI element, {prompt}, flat design, clean vector style, transparent background",
    "portrait": "character portrait, {prompt}, detailed face, expressive, game art style",
    "item": "game inventory item, {prompt}, centered, clean neutral background, icon style, highly detailed",
    "scene": "game scene concept art, {prompt}, cinematic lighting, detailed environment",
    "none": "{prompt}",
}

MODELS = ["flux", "flux-realism", "flux-anime", "flux-3d", "turbo", "any-dark"]

# Appended to every prompt by default — AI models can't render correct Chinese
# (or any complex text) reliably, so we suppress it at generation time and let
# overlay_text.py add real characters in post.
NO_TEXT_SUFFIX = (
    ", no text, no letters, no characters, no calligraphy, "
    "no writing, no signature, no watermark"
)


def _strip_zhipu_watermark(img):
    """智谱 cogview-3-flash 强制在右下角贴 'AI生成' 灰色 badge。本函数把它擦成白色。

    为什么白色填充：
      用户偏好是"所有素材最终都做透明 PNG"。后续 make_transparent.py
      会按 chroma key 把白底打成透明 alpha，所以"白色"正好就等于"透明"。
      不能直接 putalpha=0，因为 make_transparent 会按 RGB 重算 alpha 覆盖。

    算法 (flood fill from seed)：
      历史教训 —— 早期版本 1) 用 bbox 矩形填白：边缘硬切。
                      2) 用全图灰像素 mask + dilate：前景里的灰色光晕被
                         dilate 成离散小白方块。
      最终方案：在右下角小窗里找一个 badge 灰色种子像素 → BFS flood fill
      只扩散到连通的相似像素 → 严格限制扫描边界（绝不允许飞到中央主体）→
      mask + dilate ~15px → 贴白。
      这样无论前景里有多少灰色烟雾/光晕，只有真正连通到 badge 种子的灰
      像素才会被擦除，永远不会出现孤立小方块。
    """
    import sys as _sys
    from PIL import Image, ImageFilter
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    # Badge 实测大约位于右下角 200×80 px 的范围。把搜索窗稍微放大一点。
    seed_zone_x0 = max(0, w - 280)
    seed_zone_y0 = max(0, h - 130)

    def find_seed(sat_max: int, avg_min: int, avg_max: int):
        # 从右下角向左上方扫描，找第一个符合条件的灰色像素
        for y in range(h - 25, seed_zone_y0 - 1, -1):
            for x in range(w - 25, seed_zone_x0 - 1, -1):
                r, g, b = px[x, y]
                sat = max(r, g, b) - min(r, g, b)
                avg = (r + g + b) // 3
                if sat <= sat_max and avg_min <= avg <= avg_max:
                    return (x, y)
        return None

    # 严格 → 放宽 两 pass 找种子
    seed = find_seed(sat_max=18, avg_min=130, avg_max=195)
    if not seed:
        seed = find_seed(sat_max=30, avg_min=100, avg_max=215)

    if not seed:
        print(
            "WARN: zhipu watermark seed not found in bottom-right corner. "
            "Original badge may still be visible.",
            file=_sys.stderr,
        )
        return img.convert("RGBA")

    # BFS flood fill：
    #   - 起点 = seed
    #   - 接受像素：低饱和 (sat≤40) 任意亮度 (10-235) —— 既吃 badge 灰底也吃 'AI生成' 黑字
    #   - 严格边界：不允许跨出右下角 320×140 区域，避免飞到中央主体
    bound_x = max(0, w - 320)
    bound_y = max(0, h - 140)
    visited = bytearray(w * h)  # 0/1 标记，比 set 快很多
    found_xs: list[int] = []
    found_ys: list[int] = []
    stack = [seed]
    while stack:
        x, y = stack.pop()
        if x < bound_x or x >= w or y < bound_y or y >= h:
            continue
        idx = y * w + x
        if visited[idx]:
            continue
        visited[idx] = 1
        r, g, b = px[x, y]
        sat = max(r, g, b) - min(r, g, b)
        avg = (r + g + b) // 3
        if sat > 40 or not (10 <= avg <= 235):
            continue
        found_xs.append(x)
        found_ys.append(y)
        stack.append((x + 1, y))
        stack.append((x - 1, y))
        stack.append((x, y + 1))
        stack.append((x, y - 1))

    if len(found_xs) < 100:
        return img.convert("RGBA")

    # ── 验证 flood fill 区域确实像 badge，否则放弃（避免误擦前景） ──
    # 真实 badge 实测约 200×80 px，宽高比 ~2.5，必定贴到右边和下边
    min_x, max_x = min(found_xs), max(found_xs)
    min_y, max_y = min(found_ys), max(found_ys)
    bbox_w = max_x - min_x + 1
    bbox_h = max_y - min_y + 1
    bbox_area = bbox_w * bbox_h
    density = len(found_xs) / bbox_area if bbox_area else 0
    aspect = bbox_w / bbox_h if bbox_h else 0
    touches_right = max_x >= w - 25
    touches_bottom = max_y >= h - 25

    is_badge_like = (
        touches_right
        and touches_bottom
        and 1.5 <= aspect <= 5.0
        and 80 <= bbox_w <= 360
        and 30 <= bbox_h <= 140
        and density >= 0.25
    )

    if not is_badge_like:
        print(
            f"WARN: zhipu strip skipped — found region looks like noise, not a badge "
            f"(bbox={bbox_w}x{bbox_h}, density={density:.2f}, aspect={aspect:.1f}, "
            f"touches_right={touches_right}, touches_bottom={touches_bottom}). "
            f"This image probably has no watermark.",
            file=_sys.stderr,
        )
        return img.convert("RGBA")

    # 构造 mask 并膨胀
    mask = Image.new("L", (w, h), 0)
    mask_px = mask.load()
    for x, y in zip(found_xs, found_ys):
        mask_px[x, y] = 255
    mask = mask.filter(ImageFilter.MaxFilter(31))  # 15 px 半径，吃软边

    out = img.convert("RGBA").copy()
    white_layer = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    out.paste(white_layer, mask=mask)
    return out


def _save_as_png(
    data: bytes, out_path: Path, strip_zhipu_watermark: bool = False
) -> int:
    """把任意图像字节（JPEG/PNG/WEBP）统一保存为 RGBA PNG。

    Pollinations 实际返回 JPEG（无 alpha），智谱也只返回 PNG/JPEG URL，
    全都得重编码成真 PNG 才能让 make_transparent.py 工作。
    """
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(data))
        img = img.convert("RGBA")
        if strip_zhipu_watermark:
            img = _strip_zhipu_watermark(img)
        img.save(out_path, "PNG", optimize=True)
        return out_path.stat().st_size
    except ImportError:
        out_path.write_bytes(data)
        print(
            f"WARN: Pillow not installed, saved raw bytes to {out_path.name} "
            f"(actual format may be JPEG despite .png extension)",
            file=sys.stderr,
        )
        return len(data)


def _http_get(url: str, headers: dict, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_post_json(url: str, headers: dict, body: dict, timeout: int = 180) -> dict:
    payload = json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json", **headers}
    req = urllib.request.Request(url, data=payload, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_env_file(path: Path) -> dict:
    """读 KEY=VALUE 行格式的 .env，不解析引号、不展开变量，足够本脚本用。"""
    env: dict = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


def _get_zhipu_key() -> str:
    # 优先环境变量；其次 skill 目录下的 .env
    key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if key:
        return key
    env = _load_env_file(Path(__file__).parent / ".env")
    key = env.get("ZHIPU_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ZHIPU_API_KEY not set. Put it in env or in "
            f"{Path(__file__).parent / '.env'} as ZHIPU_API_KEY=xxx"
        )
    return key


def _snap_zhipu_size(width: int, height: int) -> tuple[int, int]:
    """智谱 CogView-3-Flash 只支持固定尺寸，按目标宽高比 snap 到最近一档。"""
    target_ratio = width / height
    return min(ZHIPU_SIZES, key=lambda s: abs(s[0] / s[1] - target_ratio))


def build_pollinations_url(
    prompt: str, width: int, height: int, seed: int, model: str
) -> str:
    encoded = urllib.parse.quote(prompt, safe="")
    params = (
        f"width={width}&height={height}&seed={seed}"
        f"&model={model}&nologo=true&enhance=false"
    )
    return f"https://image.pollinations.ai/prompt/{encoded}?{params}"


def gen_pollinations(
    prompt: str, width: int, height: int, seed: int, model: str, out_path: Path
) -> int:
    url = build_pollinations_url(prompt, width, height, seed, model)
    data = _http_get(url, {"User-Agent": "Mozilla/5.0 (claude-gen-asset)"})
    if len(data) < 1024:
        raise RuntimeError(f"response too small ({len(data)} bytes), likely an error")
    return _save_as_png(data, out_path, strip_zhipu_watermark=False)


def gen_zhipu(
    prompt: str,
    width: int,
    height: int,
    seed: int,
    model: str,
    out_path: Path,
    strip_watermark: bool = True,
) -> int:
    """智谱 CogView 文生图。cogview-3-flash 完全免费、不限量。

    seed 参数被忽略：智谱 API 不暴露 seed，每次都不同。如果需要可复现，
    用 pollinations 那条路。

    strip_watermark：是否对结果跑水印擦除。对 character/icon/item 这种白底
    前景图可以开；对 scene/tile/portrait 这种整图是内容的场景必须关 —— 否则
    算法可能把场景右下角的灰色画面区域误判为 badge 擦成白色矩形。
    """
    del seed  # unused
    snapped = _snap_zhipu_size(width, height)
    body = {
        "model": model,
        "prompt": prompt,
        "size": f"{snapped[0]}x{snapped[1]}",
    }
    headers = {"Authorization": f"Bearer {_get_zhipu_key()}"}
    resp = _http_post_json(
        "https://open.bigmodel.cn/api/paas/v4/images/generations",
        headers,
        body,
    )
    items = resp.get("data") or []
    if not items or not items[0].get("url"):
        raise RuntimeError(f"zhipu response missing image url: {resp}")
    img_url = items[0]["url"]
    img_bytes = _http_get(img_url, {"User-Agent": "Mozilla/5.0 (claude-gen-asset)"})
    if len(img_bytes) < 1024:
        raise RuntimeError(f"image too small ({len(img_bytes)} bytes)")
    return _save_as_png(img_bytes, out_path, strip_zhipu_watermark=strip_watermark)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate game assets via Pollinations.ai (free)",
    )
    parser.add_argument("prompt", help="Asset description")
    parser.add_argument(
        "--style", "-s", default="none", choices=list(STYLES.keys()),
        help="Style preset (default: none)",
    )
    parser.add_argument(
        "--provider", "-p", default="zhipu", choices=PROVIDERS,
        help="Image provider (default: zhipu — free CogView-3-Flash, faster in CN). "
             "'pollinations' is the original Flux backend (free, slower, may 429).",
    )
    parser.add_argument(
        "--model", "-m", default=None,
        help="Model name. Pollinations: flux/flux-realism/flux-anime/flux-3d/turbo/any-dark "
             "(default flux). Zhipu: cogview-3-flash (default, 免费不限量) / cogview-4 / "
             "cogview-4-250304.",
    )
    parser.add_argument("--width", "-W", type=int, default=1024)
    parser.add_argument("--height", "-H", type=int, default=1024)
    parser.add_argument(
        "--count", "-n", type=int, default=1, help="How many variations (default: 1)",
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="Fixed seed (default: random)",
    )
    parser.add_argument(
        "--out", "-o", default=None,
        help="Output dir (default: ~/GameAssets)",
    )
    parser.add_argument(
        "--allow-text", action="store_true",
        help="Do NOT append the 'no text' negative suffix. Use only when you "
             "actually want the model to try drawing text (rarely works well; "
             "for accurate Chinese, use overlay_text.py instead).",
    )
    args = parser.parse_args()

    final_prompt = STYLES[args.style].format(prompt=args.prompt)
    if not args.allow_text:
        final_prompt = final_prompt + NO_TEXT_SUFFIX

    # provider-specific 默认 model
    if args.model is None:
        args.model = "cogview-3-flash" if args.provider == "zhipu" else "flux"
    if args.provider == "pollinations" and args.model not in MODELS:
        print(
            f"WARN: model '{args.model}' is not a known pollinations model "
            f"(known: {MODELS}); proceeding anyway.",
            file=sys.stderr,
        )

    out_dir = Path(args.out).expanduser() if args.out else Path.home() / "GameAssets"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = hashlib.md5(args.prompt.encode()).hexdigest()[:6]

    actual_size = (args.width, args.height)
    if args.provider == "zhipu":
        actual_size = _snap_zhipu_size(args.width, args.height)

    print(f"Provider: {args.provider}", file=sys.stderr)
    print(f"Style   : {args.style}", file=sys.stderr)
    print(f"Model   : {args.model}", file=sys.stderr)
    print(
        f"Size    : {args.width}x{args.height}"
        + (
            f"  (snapped → {actual_size[0]}x{actual_size[1]})"
            if actual_size != (args.width, args.height)
            else ""
        ),
        file=sys.stderr,
    )
    print(f"Prompt  : {final_prompt}", file=sys.stderr)
    print(f"Outdir  : {out_dir}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    # scene / tile 是整图内容、没有"背景"概念，水印擦除算法会误伤右下角，禁掉
    zhipu_strip = args.style not in ("scene", "tile")

    results = []
    for i in range(args.count):
        seed = args.seed if args.seed is not None else random.randint(1, 2**31 - 1)

        suffix = f"-{i + 1}" if args.count > 1 else ""
        # 智谱不支持 seed → 文件名标记 zh- 前缀以区分
        seed_tag = f"-zh{seed}" if args.provider == "zhipu" else f"-s{seed}"
        filename = f"{timestamp}-{args.style}-{slug}{suffix}{seed_tag}.png"
        out_path = out_dir / filename

        print(f"[{i + 1}/{args.count}] seed={seed} ...", file=sys.stderr, flush=True)
        try:
            if args.provider == "zhipu":
                size = gen_zhipu(
                    final_prompt, args.width, args.height, seed, args.model, out_path,
                    strip_watermark=zhipu_strip,
                )
            else:
                size = gen_pollinations(
                    final_prompt, args.width, args.height, seed, args.model, out_path,
                )
            line = f"OK  {out_path}  ({size // 1024} KB)"
            print(line)
            results.append(str(out_path))
        except Exception as e:
            print(f"ERR {e}", file=sys.stderr)

    if not results:
        print("All generations failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

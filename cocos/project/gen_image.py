"""AI asset generation + import — wraps cocos/gen_asset.py + make_transparent.py."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .assets import add_image


def generate_and_import_image(
    project_path: str | Path,
    prompt: str,
    name: str,
    style: str = "icon",
    width: int = 1024,
    height: int = 1024,
    provider: str = "zhipu",
    transparent: bool = True,
    as_resource: bool = False,
) -> dict:
    """Generate a game asset via AI, make it transparent, and import into project.

    Built-in: uses cocos/gen_asset.py (智谱 CogView-3-Flash free / Pollinations Flux).
    No external dependencies needed — just set ZHIPU_API_KEY env var or
    create cocos-mcp/.env with ZHIPU_API_KEY=xxx.

    Args:
        prompt: Image description (English recommended for better quality)
        name: Output filename (without extension)
        style: icon/pixel/character/tile/ui/portrait/item/scene/none
        transparent: Whether to remove white background (skip for scene/tile)
        as_resource: Put in assets/resources/ for runtime loading

    Returns {path, uuid, sprite_frame_uuid, generated_png, transparent_png}
    """
    # Use built-in scripts (shipped with cocos-mcp). cocos_dir is the parent
    # package directory (cocos/), not this submodule's (cocos/project/).
    cocos_dir = Path(__file__).resolve().parent.parent
    gen_py = cocos_dir / "gen_asset.py"
    make_trans_py = cocos_dir / "make_transparent.py"

    if not gen_py.exists():
        raise FileNotFoundError(f"gen_asset.py not found at {gen_py}")

    # Load .env for ZHIPU_API_KEY if not in environment.
    # Reuses gen_asset's parser so KEY="quoted-value" works identically here.
    env = dict(os.environ)
    if "ZHIPU_API_KEY" not in env:
        from ..gen_asset import _load_env_file
        env_file = cocos_dir.parent / ".env"
        env.update(_load_env_file(env_file))

    p = Path(project_path).expanduser().resolve()
    tmp_dir = Path(tempfile.gettempdir()) / "cocos-mcp-gen"
    tmp_dir.mkdir(exist_ok=True)

    # 1. Generate image
    cmd = [
        sys.executable, str(gen_py), prompt,
        "--style", style,
        "--width", str(width),
        "--height", str(height),
        "--provider", provider,
        "--out", str(tmp_dir),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"gen_asset.py failed: {result.stderr[-500:]}")

    # Find the generated PNG (newest file in tmp_dir)
    pngs = sorted(tmp_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not pngs:
        raise RuntimeError("gen_asset.py produced no PNG output")
    generated_png = pngs[0]

    # 2. Make transparent (if requested and not scene/tile)
    transparent_png = generated_png
    if transparent and style not in ("scene", "tile"):
        subprocess.run(
            [sys.executable, str(make_trans_py), str(generated_png)],
            capture_output=True, text=True, timeout=60,
        )
        trans_path = generated_png.with_name(
            generated_png.stem + "-transparent.png"
        )
        if trans_path.exists():
            transparent_png = trans_path

    # 3. Import into project
    final_name = f"{name}.png"
    import_result = add_image(
        str(p), str(transparent_png),
        rel_path=final_name,
        as_resource=as_resource,
    )

    return {
        **import_result,
        "generated_png": str(generated_png),
        "transparent_png": str(transparent_png),
    }

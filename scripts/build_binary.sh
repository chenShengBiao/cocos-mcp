#!/usr/bin/env bash
# cocos-mcp 本地二进制打包脚本 —— 调 Nuitka 编出 --onefile 单文件 binary。
# 输出到 dist/cocos-mcp-<platform>-<arch>
#
# 用法：
#   ./scripts/build_binary.sh            # 当前平台的 release 产物
#   ./scripts/build_binary.sh --verify   # 编完跑启动 + MCP 握手验证
#   ./scripts/build_binary.sh --debug    # 保留中间产物，便于排查
set -euo pipefail

# ---------- 平台检测 ----------
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
  Darwin)               PLATFORM="darwin" ;;
  Linux)                PLATFORM="linux"  ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="win32"  ;;
  *) echo "unsupported OS: $OS" >&2; exit 1 ;;
esac
case "$ARCH" in
  x86_64|amd64)   ARCH_TAG="x64"   ;;
  arm64|aarch64)  ARCH_TAG="arm64" ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac
TARGET="cocos-mcp-${PLATFORM}-${ARCH_TAG}"

# ---------- 参数 ----------
VERIFY=0
DEBUG=0
for arg in "${@:-}"; do
  case "$arg" in
    --verify) VERIFY=1 ;;
    --debug)  DEBUG=1  ;;
    "")       ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# ---------- 依赖检查 ----------
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || {
  echo "需要 .venv —— 跑 'uv venv .venv && uv pip install .'" >&2
  exit 3
}
.venv/bin/python -m nuitka --version >/dev/null 2>&1 || {
  echo "Nuitka 未装到 .venv —— 跑 '.venv/bin/pip install nuitka'" >&2
  exit 4
}

# ---------- 编译 ----------
echo "==> 目标平台: ${TARGET}"
mkdir -p dist
NUITKA_ARGS=(
  --onefile
  --output-dir=dist
  --output-filename="${TARGET}"
  --include-package=cocos
  --include-package=mcp
  --include-package=PIL
  --nofollow-import-to=playwright
  --nofollow-import-to=tkinter
  --nofollow-import-to=unittest
  --nofollow-import-to=test
  --assume-yes-for-downloads
  --lto=no
)
[ $DEBUG -eq 1 ] || NUITKA_ARGS+=(--remove-output)

echo "==> Nuitka 编译（约 30-60 秒）..."
time .venv/bin/python -m nuitka "${NUITKA_ARGS[@]}" server.py

OUT="dist/${TARGET}"
[ -x "$OUT" ] || { echo "FAIL: $OUT 没产出" >&2; exit 5; }
SIZE="$(du -sh "$OUT" | cut -f1)"
echo "==> 产出 ${OUT} (${SIZE})"

# ---------- 验证（可选）----------
if [ $VERIFY -eq 1 ]; then
  echo "==> 跑启动 + MCP 握手验证"
  .venv/bin/python scripts/verify_binary.py "$OUT"
fi

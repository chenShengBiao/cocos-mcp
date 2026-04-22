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

# ---------- 依赖检查（跨平台 venv 定位）----------
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
  PYTHON=".venv/bin/python"
elif [ -f .venv/Scripts/python.exe ]; then
  PYTHON=".venv/Scripts/python.exe"
else
  echo "需要 .venv —— 跑 'python -m venv .venv && .venv/bin/pip install . nuitka'" >&2
  exit 3
fi
"$PYTHON" -m nuitka --version >/dev/null 2>&1 || {
  echo "Nuitka 未装到 .venv —— 跑 '$PYTHON -m pip install nuitka'" >&2
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
time "$PYTHON" -m nuitka "${NUITKA_ARGS[@]}" server.py

# Windows 下 Nuitka 自动加 .exe 后缀
if [ "$PLATFORM" = "win32" ] && [ -f "dist/${TARGET}.exe" ]; then
  OUT="dist/${TARGET}.exe"
elif [ -f "dist/${TARGET}" ]; then
  OUT="dist/${TARGET}"
else
  echo "FAIL: dist/${TARGET} 或 dist/${TARGET}.exe 没产出" >&2
  exit 5
fi
SIZE="$(du -sh "$OUT" | cut -f1 | tr -d '[:space:]')"
echo "==> 产出 ${OUT} (${SIZE})"

# ---------- 验证（可选）----------
if [ $VERIFY -eq 1 ]; then
  echo "==> 跑启动 + MCP 握手验证"
  "$PYTHON" scripts/verify_binary.py "$OUT"
fi

#!/usr/bin/env bash
# cocos-mcp 一键安装脚本（macOS / Linux）
#
# 用法：
#   curl -fsSL https://github.com/heitugongzuoshi/cocos-mcp/raw/main/install.sh | bash
#
# 做的事：
#   1. 检测平台（macOS arm64 / macOS x64 / Linux x64）
#   2. 从 GitHub Releases 下载匹配平台的单文件 binary
#   3. 放到 ~/.claude/mcp-servers/cocos-mcp/
#   4. macOS 自动解 Gatekeeper 隔离
#   5. 注册到 Claude Code（如有 `claude` CLI）
#   6. 打印 Claude Desktop / Cursor / Windsurf 的手动配置片段
#
# Windows 用户：请下载 cocos-mcp-win32-x64.exe 并手动配置（见 README）。
set -euo pipefail

REPO="heitugongzuoshi/cocos-mcp"
INSTALL_DIR="${HOME}/.claude/mcp-servers/cocos-mcp"
BIN_NAME="cocos-mcp"

# ---------- 平台探测 ----------
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
  Darwin) PLATFORM="darwin" ;;
  Linux)  PLATFORM="linux"  ;;
  *) echo "❌ 不支持的系统: $OS（Windows 请下 .exe 手装，见 README）" >&2; exit 1 ;;
esac
case "$ARCH" in
  x86_64|amd64)   ARCH_TAG="x64"   ;;
  arm64|aarch64)  ARCH_TAG="arm64" ;;
  *) echo "❌ 不支持的 arch: $ARCH" >&2; exit 1 ;;
esac
FILENAME="cocos-mcp-${PLATFORM}-${ARCH_TAG}"

echo "==> 检测到平台: ${PLATFORM}/${ARCH_TAG}"
echo "==> 目标 binary: ${FILENAME}"

# ---------- 依赖检查 ----------
command -v curl >/dev/null 2>&1 || { echo "❌ 需要 curl" >&2; exit 2; }

# ---------- 下载 ----------
URL="https://github.com/${REPO}/releases/latest/download/${FILENAME}"
mkdir -p "$INSTALL_DIR"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "==> 从 GitHub Releases 下载..."
echo "    $URL"
if ! curl -fL --progress-bar "$URL" -o "$TMP"; then
  echo "" >&2
  echo "❌ 下载失败。可能原因：" >&2
  echo "   1. 版本未发布 —— 访问 https://github.com/${REPO}/releases 确认" >&2
  echo "   2. 网络原因 —— 国内用户可试 Gitee 镜像（见 README）" >&2
  exit 3
fi

# 基本体积检查（binary 应 >10 MB）
SIZE_KB=$(wc -c <"$TMP" | tr -d '[:space:]')
if [ "$SIZE_KB" -lt 10000000 ]; then
  echo "❌ 下载到的文件只有 $((SIZE_KB / 1024)) KB，太小了" >&2
  echo "   很可能下到了 404 页面。检查仓库 / 版本是否正确。" >&2
  exit 4
fi

mv "$TMP" "$INSTALL_DIR/$BIN_NAME"
chmod +x "$INSTALL_DIR/$BIN_NAME"
echo "==> 已装到 $INSTALL_DIR/$BIN_NAME ($(du -h "$INSTALL_DIR/$BIN_NAME" | cut -f1))"

# ---------- macOS 解隔离 ----------
if [ "$PLATFORM" = "darwin" ]; then
  echo "==> 清除 macOS 隔离属性"
  xattr -dr com.apple.quarantine "$INSTALL_DIR/$BIN_NAME" 2>/dev/null || true
fi

# ---------- 注册到 Claude Code ----------
if command -v claude >/dev/null 2>&1; then
  echo "==> 注册到 Claude Code"
  claude mcp remove cocos-mcp -s user 2>/dev/null || true
  claude mcp add -s user cocos-mcp -- "$INSTALL_DIR/$BIN_NAME"
  echo "    ✓ 完成"
else
  echo "ℹ️  没检测到 Claude Code CLI（可选）。其他 MCP 客户端的配置片段在下方。"
fi

# ---------- 完成提示 ----------
cat <<EOF

══════════════════════════════════════════════════
  ✓ cocos-mcp 安装完成（184 个工具）
══════════════════════════════════════════════════

Binary 位置：$INSTALL_DIR/$BIN_NAME

如果你用 **Claude Code**：
   重启 Claude Code 就能用，试试说「做一个 Flappy Bird」

如果你用 **Claude Desktop / Cursor / Windsurf**：
   把下面 JSON 加到对应配置里的 mcpServers：

   {
     "mcpServers": {
       "cocos-mcp": {
         "command": "$INSTALL_DIR/$BIN_NAME"
       }
     }
   }

   配置文件位置：
     Claude Desktop (macOS): ~/Library/Application Support/Claude/claude_desktop_config.json
     Cursor:                 ~/.cursor/mcp.json
     Windsurf:               ~/.codeium/windsurf/mcp_config.json

前置：已安装 Cocos Creator 3.8+（https://www.cocos.com/creator-download）

卸载：rm -rf $INSTALL_DIR && claude mcp remove cocos-mcp -s user
EOF

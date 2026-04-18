#!/bin/bash
# cocos-mcp 一键安装脚本
# 用法：curl -sSL https://gitee.com/csbcsb/cocos-mcp/raw/main/install.sh | bash
set -e

INSTALL_DIR="$HOME/.claude/mcp-servers/cocos-mcp"

echo "Installing cocos-mcp..."

# 检查依赖
command -v git >/dev/null || { echo "需要 git"; exit 1; }
command -v uv >/dev/null || { echo "需要 uv (https://docs.astral.sh/uv/)"; exit 1; }
command -v claude >/dev/null || { echo "需要 Claude Code CLI"; exit 1; }

# 克隆或更新
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "更新已有安装..."
    cd "$INSTALL_DIR" && git pull
else
    echo "克隆仓库..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone https://gitee.com/csbcsb/cocos-mcp.git "$INSTALL_DIR"
fi

# 创建 venv + 装依赖
cd "$INSTALL_DIR"
if [ ! -d ".venv" ]; then
    uv venv .venv --python 3.12
fi
source .venv/bin/activate
uv pip install -q "mcp[cli]" Pillow

# 注册到 Claude Code
claude mcp remove cocos-mcp -s user 2>/dev/null || true
claude mcp add -s user cocos-mcp -- bash "$INSTALL_DIR/run.sh"

echo ""
echo "✓ cocos-mcp 安装完成（90+ 个工具）"
echo "  重启 Claude Code 即可使用"
echo "  试试说：「做一个贪吃蛇游戏」"

#!/usr/bin/env bash
# 把 main + tags 推到所有配置的公开镜像远端（GitHub / Gitee public）。
#
# 一次性准备（只跑一次）：
#   git remote add github     https://github.com/heitugongzuoshi/cocos-mcp.git
#   git remote add gitee-pub  https://gitee.com/heitugongzuoshi/cocos-mcp.git
#   # 然后确保两个远端仓库已创建（空仓即可）
#
# 之后发版：
#   git tag v1.2.0
#   ./scripts/push_mirrors.sh              # push main + 所有 tags 到镜像
#
# 注意：origin 仓库（gitee.com/csbcsb）保持私有，只作源码仓。
# 镜像仓是"公开门面" —— 只让 GitHub Actions release.yml 在那里跑
# + 让用户从 Releases 页下 binary。
set -euo pipefail

cd "$(dirname "$0")/.."

# 所有公开镜像 remote 的候选名字（存在几个推几个）
MIRROR_CANDIDATES=(github gitee-pub)

# 探测已配置的 remote
configured=()
for name in "${MIRROR_CANDIDATES[@]}"; do
  if git remote | grep -qx "$name"; then
    configured+=("$name")
  fi
done

if [ ${#configured[@]} -eq 0 ]; then
  cat >&2 <<'EOF'
没找到任何镜像 remote。请先配置（一次性）：

  git remote add github     https://github.com/<YOUR>/cocos-mcp.git
  git remote add gitee-pub  https://gitee.com/<YOUR>/cocos-mcp.git

并在对应平台创建空的公开仓库。
EOF
  exit 1
fi

# 推 main 分支 + 所有 tags 到每个镜像
for remote in "${configured[@]}"; do
  echo "==> pushing to ${remote}..."
  git push "$remote" main
  git push "$remote" --tags
  echo "    OK"
done

echo ""
echo "==> 所有镜像推送完成（${#configured[@]} 个）"
echo "    tag push 应已触发 GitHub Actions release.yml，去"
for remote in "${configured[@]}"; do
  url="$(git remote get-url "$remote")"
  echo "      $remote: ${url%.git}/actions"
done
echo "    看构建进度。"

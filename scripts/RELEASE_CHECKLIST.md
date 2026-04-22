# 发版清单

从"代码 ready"到"用户能装"的操作手册。**每次发版按序走一遍**。

---

## 🔑 一次性准备（只做一次）

### 1. 创建公开门面仓库

在 **GitHub** 上建空仓：`https://github.com/<YOUR>/cocos-mcp`（必须公开，才能挂 Release + 跑 GitHub Actions）。

可选在 **Gitee** 建公开镜像：`https://gitee.com/<YOUR>/cocos-mcp`（国内用户下载快）。

**注意**：私有源码仓保持在 `gitee.com/csbcsb/cocos-mcp` 不变。公开仓是"发布门面"，用户从这个看 README + 下 binary。

### 2. 本地加 remote

```bash
cd ~/Documents/projects/mcp/cocos-mcp
git remote add github    https://github.com/<YOUR>/cocos-mcp.git
git remote add gitee-pub https://gitee.com/<YOUR>/cocos-mcp.git   # 可选

# 首次全量推（把所有历史 + main 分支同步过去）
git push github main
git push gitee-pub main   # 如果配了
```

### 3. 确认 GitHub Actions 能跑

- 打开 `https://github.com/<YOUR>/cocos-mcp/actions`
- 应该能看到 `.github/workflows/release.yml`（workflow name: **release**）
- 触发方式：推 tag 或 手动 `workflow_dispatch`

---

## 🚀 每次发版

### 1. 确保代码 ready

```bash
# 本地跑一遍所有质量门
.venv/bin/python -m pytest
.venv/bin/python -m ruff check cocos server.py tests
.venv/bin/python -m mypy cocos
```

### 2. 打 tag

```bash
# 更新 pyproject.toml 里的 version，比如从 1.2.0.dev0 → 1.2.0
# 提交
git commit -am "chore: 发版 v1.2.0"

# 打 tag
git tag -a v1.2.0 -m "v1.2.0 release"
```

### 3. 推镜像（**触发 CI**）

```bash
./scripts/push_mirrors.sh
```

这会 push main + tags 到所有配置的镜像。**GitHub Actions 的 release.yml 在 tag 进入 GitHub 后自动触发**，开始 4 平台并行编译。

### 4. 监控构建

打开 `https://github.com/<YOUR>/cocos-mcp/actions` 看实时进度。4 个 Runner 并行，整体约 **5-10 分钟**：

- macos-14 arm64：~3 min
- macos-13 x64：~3 min
- ubuntu-latest x64：~3 min
- windows-latest x64：~8 min（最慢）

所有 4 个 job 绿了以后，`Publish GitHub Release` job 会自动跑，创建 Release 挂上 4 个 binary + checksums.txt。

### 5. 烟雾测试

下载自己发的 binary 装一遍：

```bash
# 在另一台机器 / 另一个用户目录跑
curl -fsSL https://github.com/<YOUR>/cocos-mcp/raw/main/install.sh | bash
```

装完：
- Claude Code 里说"做一个 Flappy Bird 游戏" → 看能不能跑
- 浏览器打开 preview URL → 看游戏是否确实能玩

### 6. 同步到 Gitee Release（可选）

Gitee 没有接入 GitHub Actions，手动挂：

- 登录 Gitee
- 进公开镜像仓 → 发行版 → 新建发行版
- tag 选 `v1.2.0`，title / notes 从 GitHub Release 复制
- 上传 4 个 binary + checksums.txt

国内用户会从 Gitee 下载更快。

---

## 🐛 踩坑参考

### macOS Gatekeeper 拦 binary

未签名的 Nuitka 产物会触发 "cocos-mcp-darwin-... 无法打开，因为无法验证开发者"。

**短期**：install.sh 已经自动跑 `xattr -dr com.apple.quarantine`，大部分用户无感。
**长期**：买 Apple Developer 账号 $99/yr → `codesign --sign "Developer ID Application: ..."` → `notarytool submit`。

### Windows SmartScreen 警告

未签名的 Windows .exe 会弹 "Windows 已保护你的电脑"。点"更多信息 → 仍要运行"能跑。

**长期**：EV Code Signing cert（DigiCert / Sectigo ~$300/yr）能消警告。

### CI 编译失败

常见原因：
- **Nuitka 版本对 Python 3.12 兼容问题** → 锁 Nuitka 版本到 pyproject.toml
- **Pillow C 扩展** 在某个平台上找不到 headers → 看 CI log，加 `--include-module`
- **路径大小写**在 Windows / Linux 不一致 → 检查 import

失败了点 CI log 看哪一 step 红的，定位到平台后本地复现（用对应 Runner 的 image）。

### tag 推错了想撤

```bash
# 删除远端 tag（会停掉 CI 但不会撤销已创建的 Release）
git push github :refs/tags/v1.2.0
git tag -d v1.2.0
# Release 本身要去 GitHub UI 手动删
```

---

## 📊 Release 质量门

一个 release 满足以下才能打稳定版（去掉 `-alpha/-beta` 后缀）：

- [ ] 4 平台 CI 全绿（含 `verify_binary.py` 4/4 过）
- [ ] `checksums.txt` 存在且 4 个 binary 的 SHA-256 都列齐
- [ ] install.sh 在**自己机器 + 另一台干净机器**上都能一键装
- [ ] Claude Code 里能用至少 1 个游戏 demo（Flappy / Click / Breakout 任一）
- [ ] 至少 1 个真实用户（不是你自己）装成功

前 4 项是技术门槛，最后一项是现实门槛（防止"发了但没人看懂怎么装"）。

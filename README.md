# cocos-mcp

> **🔒 Private · Closed Source**
> 商用许可项目，源码不公开。如需访问、试用或合作请联系作者。
>
> 当前定位：内部工具 / Private Alpha，正在向商业化产品演进中。

无头 Cocos Creator 3.8 MCP 服务器 —— 让 AI 在**不打开编辑器**的情况下自主开发完整的 Cocos 游戏。

---

## 是什么

一个 Python MCP server，把 Cocos Creator 3.8 的项目操作（场景搭建、组件配置、资源导入、headless 构建、平台发布）封装成 **109 个结构化工具**，给 AI 客户端（Claude Code / Cursor / Claude Desktop / 自部署 OpenAI 兼容客户端）调用。

实际效果：用户跟 AI 说一句"做一个 Flappy Bird"，AI 30 分钟内交付一个能跑能玩的游戏，全程不需要打开 Cocos Creator GUI、不需要写一行 .ts 代码。

技术栈完全独立 —— 直接读写 .scene/.prefab JSON、调 Cocos CLI 构建、生成 .meta、跑跨平台预览 server。

---

## 接入方式

> 仓库为 private。需要先取得访问权限（联系作者拿 access token / 加入协作者）再安装。

获得访问权限后：

```bash
# 1. 克隆（用你的访问凭证）
git clone https://gitee.com/csbcsb/cocos-mcp.git ~/.claude/mcp-servers/cocos-mcp

# 2. 装依赖
cd ~/.claude/mcp-servers/cocos-mcp
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install .
# 开发：uv pip install ".[dev]"

# 3. 注册到 Claude Code
claude mcp add -s user cocos-mcp -- bash ~/.claude/mcp-servers/cocos-mcp/run.sh

# 4. 重启 Claude Code
```

## 前置环境

- [Cocos Creator](https://www.cocos.com/creator-download) 3.x（测试过 3.8.6）
- Python 3.11+
- 任何支持 MCP 的 AI 客户端（Claude Code / Claude Desktop / Cursor 等）

## 使用

装好后重启 Claude Code，直接说：

- "做一个贪吃蛇游戏"
- "做一个 2048"
- "做一个带物理碰撞的平台跳跃"
- "把这个角色 prefab 在场景里实例化 10 个"
- "把游戏打包成微信小游戏，levels/ 走分包"

Claude 会自动调用 109+ MCP 工具完成全流程：初始化项目 → 写脚本 → 构建场景 → headless 编译 → 浏览器预览 → 发布到 iOS/Android/微信小游戏。**全程不用打开 Cocos Creator 编辑器。**

## 内置示例

仓库自带 3 个一键运行的演示项目（验证整个工具链通畅）：

```bash
.venv/bin/python examples/flappy-bird/build_flappy.py /tmp/flappy --port 8080
.venv/bin/python examples/click-counter/build_click_counter.py /tmp/click --port 8081
.venv/bin/python examples/breakout/build_breakout.py
```

运行后打开 `http://localhost:8080` 即可玩。

## 109+ 个工具

> 启动时 stderr 打印实际注册数量（`cocos-mcp: N tools registered…`）；下表是大类别概览。

| 类别 | 数量 | 包含 |
|---|---|---|
| **UUID** | 3 | 生成 / 压缩到 23 字符短形式 / 解压 |
| **项目** | 4 | 检测 Creator 安装 / init / 项目信息 / 资源列表 |
| **资源** | 8 | 脚本 / 图片 / 音频 / 通用文件 / meta 升级 / **9-slice border** / SpriteFrame UUID / 常量表 |
| **场景节点** | 10 | 创建 / 移动 / 删除 / 复制 / 位置 / 缩放 / 旋转 / 层级 / 查找 / 列表 |
| **基础组件** | 6 | UITransform / Sprite / Label / Graphics / Widget / 通用 add_component |
| **物理 2D** | 4 + 9 | RigidBody2D + Box/Circle/Polygon Collider，加上**全套 9 种 Joint2D**（Distance/Hinge/Spring/Mouse/Slider/Wheel/Weld/Relative/Motor） |
| **UI** | 10 | Button / Layout / ProgressBar / ScrollView / Toggle / EditBox / Slider / PageView / ToggleContainer / MotionStreak |
| **渲染扩展** | 6 | Camera / Mask / RichText / 9-slice Sprite / Tiled Sprite / Filled Sprite |
| **特效** | 4 | UIOpacity / BlockInputEvents / SafeArea / **VideoPlayer** |
| **媒体** | 3 | AudioSource / Animation / ParticleSystem2D |
| **骨骼动画** | 4 | Spine + 资源导入 / DragonBones + 资源导入 |
| **TiledMap** | 3 | TiledMap / TiledLayer / TMX 资源导入 |
| **场景全局** | 3 | **set_ambient / set_skybox / set_shadows** —— 配置场景光照 |
| **预制体** | 2 | 创建空 prefab / **实例化 prefab 到场景**（带 fileId 唯一化） |
| **AI 素材** | 2 | `generate_asset`（CogView-3-Flash / Pollinations，自带 SHA-256 缓存）/ `create_sprite_atlas` |
| **动画文件** | 1 | AnimationClip 关键帧生成器 |
| **事件** | 2 | ClickEvent / 通用 EventHandler |
| **脚本** | 4 | 挂载 / link_property / set_property / set_uuid_property |
| **场景工具** | 5 | 验证 / 节点列表 / 对象查看 / 对象计数 / **批量操作（27 op，130x 提速）** |
| **构建发布** | 4 | headless 构建 / 预览 / 停止 / 状态 |
| **项目设置** | 6 | 起始场景 / 场景列表 / 微信 appid / 物理配置 / 设计分辨率 / 清理（严格 level 校验） |
| **引擎模块** | 2 | 获取 / 启用-禁用引擎模块 |
| **商业化发布** | 3 | **`set_native_build_config`**（iOS/Android 包名 + 签名 + 朝向 + icon/splash） / **`set_bundle_config`**（Asset Bundle）/ **`set_wechat_subpackages`**（微信 4 MB 主包分包） |

## 性能与可调优

| 旋钮 | 默认 | 效果 |
|---|---|---|
| `cocos_batch_scene_ops` | — | 一次 read/write 跑多个 op；27 种 op 类型；**实测 200 个工具调用 4293ms → 33ms (130x)** |
| `COCOS_MCP_SCENE_COMPACT=1` | off | scene 写盘改用 compact JSON（无缩进）；**500 对象场景 -41% 文件大小** —— CI / 批量构建打开 |
| `gen_asset.py` 缓存 | on | SHA-256(provider+model+prompt+size+seed) → 落盘 PNG；同 prompt 二次调用秒回（智谱 ~3-5s API 跳过）。`--no-cache` 可绕过 |
| Pillow lazy-import | — | 不触发图片操作的工具不需要 Pillow，slim 环境装得更轻 |

## 商业化发布

```python
# iOS / Android 包元数据 + 签名
cocos_set_native_build_config(
    project, "android",
    package_name="com.foo.game",
    orientation="landscape",
    android_min_api=21, android_target_api=33,
    android_use_debug_keystore=False,
    android_keystore_path="/keys/release.jks",
    android_keystore_password="…",
    android_keystore_alias="prod",
    android_keystore_alias_password="…",
    android_app_bundle=True,   # 出 .aab
)

# 把 assets/levels/ 标记成 Asset Bundle，运行时 cc.assetManager.loadBundle('levels')
cocos_set_bundle_config(project, "assets/levels",
    compression_type={"web-mobile": "merge_dep", "wechatgame": "subpackage"})

# 微信小游戏分包（4 MB 主包硬限制）
cocos_set_wechat_subpackages(project, [
    {"name": "level1", "root": "assets/levels/world1"},
    {"name": "audio", "root": "assets/audio"},
])
```

## 项目结构

```
cocos-mcp/
├── server.py                         # MCP 入口（仅 60 行：FastMCP + tools.register_all）
├── run.sh
├── cocos/
│   ├── uuid_util.py                  # UUID 压缩算法
│   ├── meta_util.py                  # .meta 文件读写（含 9-slice border setter）
│   ├── project.py                    # 项目初始化 / 资源导入 / AI 素材生成
│   ├── build.py                      # CLI 构建 / 跨平台预览 / 引擎-平台-发布配置
│   ├── gen_asset.py                  # AI 生图（CogView / Pollinations + 缓存）
│   ├── make_transparent.py           # chroma key 抠白底
│   ├── scene_builder/                # 场景 JSON 构造（package）
│   │   ├── __init__.py               # 公共 API（add_node / add_*等 70+ 函数）
│   │   ├── _helpers.py               # 私有 factory（_make_node / _vec3 / _attach_component …）
│   │   └── batch.py                  # batch_ops 大型 dispatch
│   └── tools/                        # MCP 工具薄包装，按职责拆 5 模块
│       ├── core.py                   # UUID / project / asset / 常量
│       ├── scene.py                  # scene / node / 基础组件 / 光照 / prefab / batch
│       ├── physics_ui.py             # 物理 + UI 组件 + 9 个 Joint2D
│       ├── media.py                  # audio / anim / particle / Spine / DB / TiledMap / 渲染扩展 / VideoPlayer
│       └── build.py                  # 构建 / 预览 / 平台-发布配置
├── examples/                         # 3 个一键示例
├── tests/                            # 166 个 pytest 单元测试，72% 覆盖率
├── .github/workflows/test.yml        # Ubuntu / macOS / Windows × Python 3.11 / 3.12
├── Dockerfile
├── CHANGELOG.md
└── pyproject.toml
```

## 质量保障

- **166 个 pytest 测试**，本地 < 5s 跑完。覆盖：UUID、meta、scene_builder、batch、9 个 Joint、prefab 实例化、所有发布工具、AI 素材生成（HTTP mock）、chroma key、跨平台预览。
- **CI**：GitHub Actions matrix —— Ubuntu / macOS / Windows × Python 3.11 / 3.12，每个组合都跑 `ruff` + `mypy` + `pytest`。
- **类型检查**：`mypy cocos/` 0 errors。
- **Lint**：`ruff check` 0 errors。
- **跨平台**：所有外部进程调用走 `sys.executable` / socket / `tempfile.gettempdir()`，Windows / macOS / Linux 都能跑。

---

## 协议 / License

**Proprietary · All Rights Reserved · Copyright © heitugongzuoshi**

未经书面授权，**不得复制、修改、分发、二次发布或将本项目用于任何商业用途**。
仅授权给已被邀请的协作者用于内部评估、试用与开发。

如需获取使用授权、商业合作、二次开发或定制服务，请通过以下方式联系：

- Email: 2282059276@qq.com

> 旧版本（v1.1.0 及之前）以 MIT 协议发布，相关分发已停止。本仓库当前版本 (Unreleased / 1.2-dev) 起转为闭源。

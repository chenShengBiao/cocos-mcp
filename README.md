# cocos-mcp

> **🔒 Private · Closed Source**
> 商用许可项目，源码不公开。如需访问、试用或合作请联系作者。
>
> 当前定位：内部工具 / Private Alpha，正在向商业化产品演进中。

无头 Cocos Creator 3.8 MCP 服务器 —— 让 AI 在**不打开编辑器**的情况下自主开发完整的 Cocos 游戏。

---

## 是什么

一个 Python MCP server，把 Cocos Creator 3.8 的项目操作（场景搭建、组件配置、资源导入、headless 构建、平台发布）封装成 **135 个结构化工具**，给 AI 客户端（Claude Code / Cursor / Claude Desktop / 自部署 OpenAI 兼容客户端）调用。2D 和基础 3D 小游戏都覆盖。

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

Claude 会自动调用 135+ MCP 工具完成全流程：初始化项目 → 写脚本 → 构建场景 → headless 编译 → 浏览器预览 → 发布到 iOS/Android/微信小游戏。**全程不用打开 Cocos Creator 编辑器。**

## 内置示例

仓库自带 3 个一键运行的演示项目（验证整个工具链通畅）：

```bash
.venv/bin/python examples/flappy-bird/build_flappy.py /tmp/flappy --port 8080
.venv/bin/python examples/click-counter/build_click_counter.py /tmp/click --port 8081
.venv/bin/python examples/breakout/build_breakout.py
```

运行后打开 `http://localhost:8080` 即可玩。

## 135+ 个工具

> 启动时 stderr 打印实际注册数量（`cocos-mcp: N tools registered…`）；下表是大类别概览。

| 类别 | 数量 | 包含 |
|---|---|---|
| **UUID** | 3 | 生成 / 压缩到 23 字符短形式 / 解压 |
| **项目** | 4 | 检测 Creator 安装 / init / 项目信息 / 资源列表 |
| **资源** | 8 | 脚本 / 图片 / 音频 / 通用文件 / meta 升级 / **9-slice border** / SpriteFrame UUID / 常量表 |
| **场景节点** | 10 | 创建 / 移动 / 删除 / 复制 / 位置 / 缩放 / 旋转 / 层级 / 查找 / 列表 |
| **基础组件** | 6 | UITransform / Sprite / Label / Graphics / Widget / 通用 add_component |
| **物理 2D** | 4 + 8 | RigidBody2D + Box/Circle/Polygon Collider，加上 Cocos 3.8 全套 **8 种 Joint2D**（Distance / **Fixed** / Hinge / Spring / Mouse / Slider / Wheel / Relative） |
| **🆕 物理 3D** | 13 | RigidBody + 8 个 Collider（Box/Sphere/Capsule/Cylinder/Cone/Plane/Mesh/Terrain）+ 2 个 CharacterController（Box/Capsule）+ `set_physics_3d_config` + `create_physics_material` |
| **🆕 3D 渲染** | 5 | DirectionalLight / SphereLight / SpotLight / MeshRenderer / SkinnedMeshRenderer |
| **UI** | 13 | Button / Layout / ProgressBar / ScrollView / Toggle / EditBox / Slider / PageView / ToggleContainer / MotionStreak / **ScrollBar** / **PageViewIndicator** / **WebView** |
| **渲染扩展** | 6 | Camera / Mask / RichText / 9-slice Sprite / Tiled Sprite / Filled Sprite |
| **特效** | 4 | UIOpacity / BlockInputEvents / SafeArea / VideoPlayer |
| **媒体** | 3 | AudioSource / Animation / ParticleSystem2D |
| **骨骼动画** | 4 | Spine + 资源导入 / DragonBones + 资源导入 |
| **TiledMap** | 3 | TiledMap / TiledLayer / TMX 资源导入 |
| **场景全局** | 4 | set_ambient / set_skybox / set_shadows / **set_fog**（fourth global，LINEAR/EXP/EXP²/LAYERED 四种模型） |
| **预制体** | 2 | 创建空 prefab / 实例化 prefab 到场景（带 fileId 唯一化） |
| **AI 素材** | 2 | `generate_asset`（CogView-3-Flash / Pollinations，自带 SHA-256 缓存）/ `create_sprite_atlas` |
| **动画文件** | 1 | AnimationClip 关键帧生成器 |
| **事件** | 2 | ClickEvent / 通用 EventHandler |
| **脚本** | 4 | 挂载 / link_property / set_property / set_uuid_property |
| **场景工具** | 6 | 验证 / 节点列表 / 对象查看 / 对象计数 / **批量操作（27 op，130x 提速）**/ **`cocos_audit_scene_modules`**（组件→引擎模块一致性检查，防"build 成功但 RigidBody2D 跑不起来"） |
| **构建发布** | 4 | headless 构建 / 预览 / 停止 / 状态；`cocos_build` 新增 `source_maps` / `md5_cache` / `skip_compress_texture` / `inline_enum` / `mangle_properties` / `build_options` 自由 k=v |
| **🆕 构建后补丁** | 4 | `register_post_build_patch` / `list` / `remove` / `apply` —— 声明式 JSON 修改 / 正则替换 / 文件覆盖，`cocos_build` 成功后自动跑 |
| **项目设置** | 7 | 起始场景 / 场景列表 / 微信 appid / 2D 物理 / **3D 物理** / 设计分辨率 / 清理（严格 level 校验） |
| **引擎模块** | 2 | 获取 / 启用-禁用引擎模块 |
| **商业化发布** | 3 | `set_native_build_config`（iOS/Android 包名 + 签名 + 朝向 + icon/splash）/ `set_bundle_config`（Asset Bundle）/ `set_wechat_subpackages`（微信 4 MB 主包分包） |

## 性能与可调优

| 旋钮 | 默认 | 效果 |
|---|---|---|
| `cocos_batch_scene_ops` | — | 一次 read/write 跑多个 op；27 种 op 类型；**实测 200 个工具调用 4293ms → 33ms (130x)**。tool 描述首行写了 "PREFERRED for ≥3 sequential mutations"，LLM 会优先用 |
| **场景读缓存** | on | `_load_scene` 按绝对路径 + `st_mtime_ns` 缓存解析结果（LRU 容量 8）；外部写盘会自动失效。连续多次 tool 调用命中时省掉 JSON parse |
| **Creator 安装缓存** | on | `list_creator_installs` 用 `functools.lru_cache`，session 内不重复扫 `/Applications/Cocos/Creator`。`invalidate_creator_installs_cache()` 可清 |
| `COCOS_CREATOR_PATH` | — | 指定一个 Creator 版本目录，优先级最高（适合 CI / Docker / 非标位置安装） |
| `COCOS_CREATOR_EXTRA_ROOTS` | — | 追加扫描路径（POSIX `:` 分隔，Windows `;` 分隔）；叠加在默认根之上 |
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

## 构建后补丁（解决 build/ 里改完下次被刷掉）

Cocos 每次 `cocos_build` 会从头生成 `build/<platform>/`，手动改的 `style.css` / `project.config.json` 等下次全被覆盖。通过下面三种声明式补丁登记一次，之后每次构建自动应用：

```python
cocos_register_post_build_patch(project, patches=[
    # ① JSON 精准 key 覆盖（解决 WeChat appid 被重置）
    {"platform": "wechatgame", "file": "project.config.json",
     "kind": "json_set", "path": "appid", "value": "wx000000000000demo"},

    # ② 正则替换（解决 style.css body 背景色）
    {"platform": "web-mobile", "file": "style.css",
     "kind": "regex_sub",
     "find": r"background:\s*#[0-9a-fA-F]{3,6}",
     "replace": "background: #1c2833"},

    # ③ 整文件覆盖（自定义 index.html 模板）
    {"platform": "web-mobile", "file": "index.html",
     "kind": "copy_from", "source": "custom/index.html"},
])

# 之后 cocos_build 自动应用；补丁存在 settings/v2/packages/post-build-patches.json
# 跟着 git 走，换机器 / 队友不会丢
```

安全阀：注册时校验 regex 编译 + 路径注入（拒绝 `..` / 绝对路径）；应用时 regex 不匹配立刻报错（防 Cocos 升级后静默失效）；首个 patch 失败即止损不连锁；`dry_run=True` 预检；`cocos_build(apply_patches=False)` 一键关闭。

## 3D mini-game 快速上手

2D + 3D 全部都是一条消息的事情：

```python
# 1. 初始化 + 开启 3D 物理（默认 gravity = -10 m/s² 不是 -320 像素）
cocos_init_project("/tmp/roll3d")
cocos_set_physics_3d_config("/tmp/roll3d", gravity_y=-9.8)

# 2. 造个有摩擦系数的物理材质
ice = cocos_create_physics_material("/tmp/roll3d", "ice", friction=0.02, restitution=0.3)

# 3. 场景：Ball（RigidBody + SphereCollider + 冰材质）+ Ground（PlaneCollider）+ 方向光
scene = cocos_create_scene("/tmp/roll3d/assets/scenes/game.scene")
canvas = scene["canvas_node_id"]

sun = cocos_create_node(scene_path, canvas, "Sun")
cocos_add_directional_light(scene_path, sun, illuminance=65000, shadow_enabled=True)

ball = cocos_create_node(scene_path, canvas, "Ball", lpos=[0, 5, 0])
cocos_add_rigidbody_3d(scene_path, ball, body_type=1)          # DYNAMIC=1（不是 0，是 bitmask）
col = cocos_add_sphere_collider_3d(scene_path, ball, radius=0.5)
cocos_set_uuid_property(scene_path, col, "_material", ice["uuid"])
cocos_add_mesh_renderer(scene_path, ball, mesh_uuid=ball_mesh_uuid, material_uuids=[mat_uuid])

ground = cocos_create_node(scene_path, canvas, "Ground")
cocos_add_plane_collider_3d(scene_path, ground, normal=(0, 1, 0))

# 4. （可选）加雾增加氛围
cocos_set_fog(scene_path, enabled=True, fog_type=1, density=0.05)  # EXP

# 5. 发布时用 release 选项
cocos_build("/tmp/roll3d", debug=False, source_maps=False, md5_cache=True, skip_compress_texture=False)
```

## 项目结构

```
cocos-mcp/
├── server.py                         # MCP 入口（仅 60 行：FastMCP + tools.register_all）
├── run.sh
├── cocos/
│   ├── uuid_util.py                  # UUID 压缩算法
│   ├── meta_util.py                  # .meta 文件读写（含 9-slice border setter）
│   ├── errors.py                     # 结构化错误 + build log 模式识别（8 种 error_code）
│   ├── types.py                      # TypedDict 返回契约（BuildResult / ValidationResult 等）
│   ├── build.py                      # CLI 构建 / 跨平台预览 / 平台-发布配置 / 2D+3D 物理 config
│   ├── gen_asset.py                  # AI 生图（CogView / Pollinations + 缓存）
│   ├── make_transparent.py           # chroma key 抠白底
│   ├── project/                      # 项目初始化 + 资源导入（按域拆子模块）
│   │   ├── __init__.py               # 公共 API re-export
│   │   ├── installs.py               # Creator 检测（+ env var 逃生出口 + $PATH 探测）
│   │   ├── assets.py                 # add_script / image / audio / resource + list_assets
│   │   ├── animation.py              # .anim AnimationClip 文件生成
│   │   ├── skeletal.py               # Spine + DragonBones 资源导入
│   │   ├── tiled.py                  # TiledMap .tmx 导入
│   │   ├── atlas.py                  # SpriteAtlas .pac 生成
│   │   ├── physics_material.py       # cc.PhysicsMaterial (.pmat) 资源
│   │   ├── post_build_patches.py     # 构建后补丁 registry + json_set/regex_sub/copy_from 引擎
│   │   └── gen_image.py              # AI 素材生成 + 自动导入
│   ├── scene_builder/                # 场景 JSON 构造（按域拆子模块）
│   │   ├── __init__.py               # 核心 scene 生命周期 + node / 基础组件 + re-export
│   │   ├── _helpers.py               # 私有 factory + **mtime-invalidated 场景读缓存**
│   │   ├── batch.py                  # batch_ops 大型 dispatch
│   │   ├── physics.py                # RigidBody2D + 3 碰撞器 + 8 Joint2D
│   │   ├── physics_3d.py             # RigidBody + 8 Collider + 2 CharacterController
│   │   ├── ui.py                     # 按钮/布局/滑块/richtext/sprite 变体/ScrollBar/WebView 等
│   │   ├── media.py                  # audio / anim / particle / spine / DB / tiled / video / 场景全局 setters
│   │   ├── rendering.py              # 3 lights + MeshRenderer + SkinnedMeshRenderer
│   │   ├── prefab.py                 # create_prefab + instantiate_prefab
│   │   └── modules.py                # COMPONENT_REQUIRES_MODULE + audit_scene_modules
│   └── tools/                        # MCP 工具薄包装，按职责拆 7 模块
│       ├── core.py                   # UUID / project / asset / 常量
│       ├── scene.py                  # scene / node / 基础组件 / 光照 + fog / prefab / batch
│       ├── physics_ui.py             # 2D 物理 + UI 组件（ScrollBar / PageViewIndicator / WebView 等）
│       ├── physics_3d.py             # 3D 物理工具
│       ├── rendering_3d.py           # 3D 光源 + MeshRenderer
│       ├── media.py                  # audio / anim / particle / Spine / DB / TiledMap / VideoPlayer
│       └── build.py                  # 构建 / 预览 / 平台-发布配置（build_options 透传）
├── examples/                         # 3 个一键示例
├── tests/                            # 266 个 pytest 单元测试
├── .github/workflows/test.yml        # Ubuntu / macOS / Windows × Python 3.11 / 3.12
├── Dockerfile
├── CHANGELOG.md
└── pyproject.toml
```

## 质量保障

- **266 个 pytest 测试**，本地 < 5s 跑完。覆盖：UUID、meta、scene_builder、batch、8 个 Joint2D、**3D 物理（18 个）**、**3D 渲染（10 个）**、prefab 实例化、所有发布工具、AI 素材生成（HTTP mock）、chroma key、跨平台预览、**结构化错误分类器 + TS 诊断解析**、**TypedDict 契约漂移检测**、**场景读缓存命中 / mtime 失效 / LRU 淘汰**、**引擎模块 audit**、**构建后补丁 CRUD + 三种 kind + 路径注入防御 + drift 保护**、**Creator 安装 env var / PATH 探测**。
- 所有 3D 组件字段默认值**逐一对齐 cocos-engine v3.8.6 源码**（如 `ERigidBodyType.DYNAMIC=1 / STATIC=2 / KINEMATIC=4` 是 bitmask 不是 0/1/2，已用回归测试锁定）。
- **CI**：GitHub Actions matrix —— Ubuntu / macOS / Windows × Python 3.11 / 3.12，每个组合都跑 `ruff` + `mypy` + `pytest`。
- **类型检查**：`mypy cocos/` 0 errors。
- **Lint**：`ruff check` 0 errors。
- **跨平台**：所有外部进程调用走 `sys.executable` / socket / `tempfile.gettempdir()`，Windows / macOS / Linux 都能跑。

## 可观测性 / AI 友好度

- **结构化错误** —— `cocos_build` 失败时返回 `{error_code, hint}`，9 种类型（`BUILD_TYPESCRIPT_ERROR` / `BUILD_MISSING_MODULE` / `BUILD_ASSET_NOT_FOUND` / `BUILD_TIMEOUT` / `POST_BUILD_PATCH_FAILED` / …）。AI 不用读日志尾也能决定下一步（比如自动调用 `cocos_set_engine_module` 打开 physics-2d-box2d）。
- **TS 错误结构化** —— `BUILD_TYPESCRIPT_ERROR` 时 `BuildResult` 额外带 `ts_errors: [{file, line, col, code, message}]`，AI 直接 Read+Edit 目标文件就行，不用 regex 日志。
- **场景预检** —— `cocos_audit_scene_modules(scene, project?)` 扫场景组件 vs 项目 `engine.json`，返回 `{ok, disabled, actions: [...]}`；`actions` 是可以直接复制粘贴的 `cocos_set_engine_module` + `cocos_clean_project` 命令链。
- **TypedDict 返回契约** —— `BuildResult` / `ValidationResult` / `BatchOpsResult` 等 8 个 TypedDict。`tests/test_types.py` 反射 `__annotations__` 和运行时字典比对，谁改字段忘同步会直接失败。
- **`cocos_constants`** —— 一个 tool 返回所有 layer mask / blend factor / alignment / physics group / ERigidBodyType 等 enum 整数值，AI 不用猜也不用靠 hardcoded 魔数。
- **Creator 安装逃生出口** —— 没找到 Creator 时错误信息列出 4 种解法（下载 / `COCOS_CREATOR_PATH` pin / `COCOS_CREATOR_EXTRA_ROOTS` 扩展扫描 / `$PATH` 放 binary）。

## 可靠性护栏

- **构建后补丁** —— `cocos_register_post_build_patch` 登记 `json_set`/`regex_sub`/`copy_from` 三类补丁，`cocos_build` 每次成功后自动在 `build/<platform>/` 应用。补丁跟着 git 走（`settings/v2/packages/post-build-patches.json`），换机器不丢。**路径注入防御**（拒绝 `..` / 绝对路径）、**regex 编译验证**、**drift 保护**（正则不再匹配就报错而非静默跳过）、**dry_run** 预检、**首个 patch 失败即止损**，都是上游默认开启。
- **引擎模块映射表** —— 内置 `COMPONENT_REQUIRES_MODULE`（30+ 条：RigidBody2D → physics-2d-box2d，Spine → spine，VideoPlayer → video，…），`physics-2d-box2d` 子模块的启用被识别为满足 `physics-2d` 父模块需求（匹配 Cocos 自己的语义）。
- **脚本 UUID 自适配** —— `cocos_add_script` 同时接受 23 字符短形式和 36 字符标准 UUID，标准形式自动压缩；之前传 36 字符是静默 bug（组件变空壳）。

---

## 协议 / License

**Proprietary · All Rights Reserved · Copyright © heitugongzuoshi**

未经书面授权，**不得复制、修改、分发、二次发布或将本项目用于任何商业用途**。
仅授权给已被邀请的协作者用于内部评估、试用与开发。

如需获取使用授权、商业合作、二次开发或定制服务，请通过以下方式联系：

- Email: 2282059276@qq.com

> 旧版本（v1.1.0 及之前）以 MIT 协议发布，相关分发已停止。本仓库当前版本 (Unreleased / 1.2-dev) 起转为闭源。

# cocos-mcp

> 无头 Cocos Creator 3.8 MCP 服务器 —— 让 AI 不打开编辑器、不写一行 `.ts` 代码，30 分钟内交付一个能跑能玩的完整 2D / 基础 3D 小游戏。

[🇺🇸 English](./README.en.md)

![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-v1.2-green)
![Platforms](https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![Cocos Creator](https://img.shields.io/badge/Cocos%20Creator-3.8%2B-orange)
![Tools](https://img.shields.io/badge/tools-184-brightgreen)
![Tests](https://img.shields.io/badge/tests-741%20passing-success)
![License](https://img.shields.io/badge/license-Proprietary-red)

> 🔐 **商业授权项目 · 源码闭源**
> 需要试用 / 合作 / 定制：📧 **2282059276@qq.com**
> 旧版本（≤v1.1.0）以 MIT 开源，现版本起转闭源。

---

## ✨ 核心能力

- 🎮 **完全 Headless** —— 直接读写 `.scene` / `.prefab` / `.meta` JSON，不依赖编辑器 GUI；业界唯一
- ⚡ **一句话交付游戏** —— "做一个 Flappy Bird" / "做 2048" / "做一个带物理的平台跳跃"，AI 自动调 184 工具完成全流程
- 🔁 **Playwright 闭环反馈** —— AI 能点击 / 按键 / 读状态 / 视觉 diff，"自己玩自己做的游戏"
- 🎯 **9 个游戏逻辑脚手架** —— player / enemy / spawner / game_loop / input / score / audio / camera_follow / ui_screen，canonical TypeScript 模板直接挂节点
- 🎨 **5 内置 UI 主题 + 6 UI 模式预设** —— dark_game / neon_arcade / pastel_cozy / ...；`add_dialog_modal` / `add_main_menu` / `add_hud_bar` 一次搭完整 UI 块
- 🏭 **一键多端发布** —— iOS / Android 原生包 + Asset Bundle + 微信小游戏分包 + 构建后补丁

## 📋 Requirements

- [Cocos Creator 3.8+](https://www.cocos.com/creator-download)（测试过 3.8.6）
- Python 3.11 或 3.12
- 任意 MCP 客户端：[Claude Desktop](https://claude.com/download) · [Claude Code](https://claude.com/claude-code) · [Cursor](https://cursor.com) · [Windsurf](https://codeium.com/windsurf) · VS Code

## 🚀 Quick Start

> 仓库为私有仓库。先联系作者获取访问权限（邮箱：`2282059276@qq.com`）。

```bash
# 1. 克隆（用你的访问凭证）
git clone https://gitee.com/csbcsb/cocos-mcp.git ~/.claude/mcp-servers/cocos-mcp

# 2. 装依赖
cd ~/.claude/mcp-servers/cocos-mcp
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install .

# 3. 注册到你的 MCP 客户端（见下方 Client Configuration）
```

然后重启客户端，直接说：

> "做一个贪吃蛇游戏"
> "做一个带物理碰撞的平台跳跃"
> "把这个角色 prefab 在场景里实例化 10 个"
> "打包成微信小游戏，`levels/` 走分包"

## ⚙️ Client Configuration

<details>
<summary><b>Claude Code（推荐）</b></summary>

一行命令注册：

```bash
claude mcp add -s user cocos-mcp -- bash ~/.claude/mcp-servers/cocos-mcp/run.sh
```

重启 Claude Code 生效。

</details>

<details>
<summary><b>Claude Desktop</b></summary>

编辑配置文件（macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`；Windows：`%APPDATA%\Claude\claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "cocos-mcp": {
      "command": "bash",
      "args": ["/Users/YOU/.claude/mcp-servers/cocos-mcp/run.sh"]
    }
  }
}
```

</details>

<details>
<summary><b>Cursor</b></summary>

编辑 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "cocos-mcp": {
      "command": "bash",
      "args": ["/Users/YOU/.claude/mcp-servers/cocos-mcp/run.sh"]
    }
  }
}
```

</details>

<details>
<summary><b>Windsurf</b></summary>

编辑 `~/.codeium/windsurf/mcp_config.json`：

```json
{
  "mcpServers": {
    "cocos-mcp": {
      "command": "bash",
      "args": ["/Users/YOU/.claude/mcp-servers/cocos-mcp/run.sh"]
    }
  }
}
```

</details>

<details>
<summary><b>VS Code（含 GitHub Copilot Chat）</b></summary>

在项目根或 `~/.vscode/settings.json` 里：

```json
{
  "mcp": {
    "servers": {
      "cocos-mcp": {
        "type": "stdio",
        "command": "bash",
        "args": ["/Users/YOU/.claude/mcp-servers/cocos-mcp/run.sh"]
      }
    }
  }
}
```

</details>

> **Windows 用户**：把 `bash /path/to/run.sh` 换成 `cmd /c /path/to/run.bat`，或直接用 `python server.py` 启动（需先激活 venv）。

## 🔄 升级

已经装过的用户拉新版本（以默认安装路径 `~/.claude/mcp-servers/cocos-mcp` 为例）：

```bash
cd ~/.claude/mcp-servers/cocos-mcp
git pull
uv pip install --python .venv/bin/python .   # 同步依赖（pyproject 可能新增包）
```

然后 **完整重启 MCP 客户端**（Claude Code / Desktop / Cursor / ...）。
理由：MCP server 是常驻子进程，Python 代码已加载进内存；不重启客户端就还在跑旧版本。

快速校验本地安装没坏：

```bash
~/.claude/mcp-servers/cocos-mcp/.venv/bin/python -c "import cocos, server; print('import OK')"
```

> Windows 用户：把 `.venv/bin/python` 换成 `.\.venv\Scripts\python.exe`。

## 🧰 Tools (184 total)

> 启动时 stderr 会打印实际注册数量：`cocos-mcp: N tools registered…`

<details>
<summary><b>UUID / 项目 / 资源（15 工具）</b></summary>

- UUID：`new_uuid` / `compress_uuid`（生成 23 字符短形式）/ `decompress_uuid`
- 项目：`list_creator_installs` / `init_project` / `get_project_info` / `list_assets`
- 资源：`add_script` / `add_image` / `add_audio_file` / `add_resource_file` / `upgrade_image_meta` / `set_sprite_frame_border`（9-slice）/ `get_sprite_frame_uuid` / `constants`
</details>

<details>
<summary><b>场景节点 + 基础组件（16 工具）</b></summary>

- 节点：`create_scene` / `create_node` / `move_node` / `delete_node` / `duplicate_node` / `set_node_position/scale/rotation/active/layer` / `find_node_by_name` / `list_scene_nodes`
- 基础组件：`add_uitransform` / `add_sprite` / `add_label` / `add_graphics` / `add_widget` / `add_component`（通用）
</details>

<details>
<summary><b>2D 物理（12 工具）</b></summary>

- `add_rigidbody2d` + 3 种 Collider（Box / Circle / Polygon）
- 全套 **8 种 Joint2D**：Distance / Fixed / Hinge / Spring / Mouse / Slider / Wheel / Relative
- `set_physics_2d_config`（重力 / 睡眠阈值 / 子步数）
</details>

<details>
<summary><b>3D 物理 + 渲染（18 工具）</b></summary>

- 3D 物理：`add_rigidbody_3d` + 8 种 Collider（Box / Sphere / Capsule / Cylinder / Cone / Plane / Mesh / Terrain）+ 2 种 CharacterController + `set_physics_3d_config` + `create_physics_material`
- 3D 渲染：`add_directional_light` / `add_sphere_light` / `add_spot_light` / `add_mesh_renderer` / `add_skinned_mesh_renderer`
- 所有字段默认值**逐一对齐 cocos-engine v3.8.6 源码**，`ERigidBodyType.DYNAMIC=1 / STATIC=2 / KINEMATIC=4` 这类 bitmask 都有 regression test
</details>

<details>
<summary><b>UI 组件 + 模式预设 + 响应式（29 工具）</b></summary>

- 经典组件（13）：Button / Layout / ProgressBar / ScrollView / Toggle / EditBox / Slider / PageView / ToggleContainer / MotionStreak / ScrollBar / PageViewIndicator / WebView
- **UI 模式预设（6）**：`add_dialog_modal` / `add_main_menu` / `add_hud_bar` / `add_card_grid` / `add_toast` / `add_loading_spinner` —— AI 一次搭完整 UI 块
- **响应式助手（5）**：`make_fullscreen` / `anchor_to_edge` / `center_in_parent` / `stack_vertically` / `stack_horizontally` —— 告别 Widget bitmask
- **文本合成（1）**：`add_styled_text_block` —— 标题 + 副标题 + 分割线 + 正文
- **渲染扩展（4）**：Camera / Mask / RichText / 9-slice Sprite / Tiled Sprite / Filled Sprite
</details>

<details>
<summary><b>动画 + 主题 + UI Lint（11 工具）</b></summary>

- **入场动画（6）**：`add_fade_in` / `add_slide_in` / `add_scale_in` / `add_bounce_in` / `add_pulse` / `add_shake`
- **UI 主题（4）**：`set_ui_theme`（5 内置：dark_game / light_minimal / neon_arcade / pastel_cozy / corporate）/ `get_ui_tokens` / `list_builtin_themes` / `hex_to_rgba`
- **UI 质量 lint（1）**：`cocos_lint_ui` —— 8 条规则（touch target / 长文本剪字 / UI layer / WCAG 对比度 / 按钮重叠 / 字号框 / 按钮多无 Layout / 嵌套 Mask）
</details>

<details>
<summary><b>🔁 Playwright 闭环反馈（8 工具）</b></summary>

让 AI 真正能"玩"自己做的游戏：

- `cocos_click_preview` / `cocos_press_key_preview` / `cocos_drag_preview`
- `cocos_fill_preview`（文字输入）
- `cocos_read_state_preview`（读任意 JS 表达式，如 `window.game.score`）
- `cocos_wait_preview` / `cocos_run_preview_sequence`（序列批执行）
- `cocos_screenshot_preview_diff`（纯 Pillow 视觉回归，不依赖 Playwright）

Playwright 是**可选依赖**（~200 MB chromium），没装时工具返回明确的 install hint。
</details>

<details>
<summary><b>🎯 游戏脚手架（9 工具）</b></summary>

生成 canonical `.ts` 模板，返回压缩 UUID 直接挂节点：

- `scaffold_input_abstraction` —— WASD + 方向键 + 触屏统一成 InputManager 单例
- `scaffold_score_system` —— 当前/最高分 + localStorage + Label 自动渲染
- `scaffold_player_controller` —— **4 kinds**：platformer / topdown / flappy / click_only
- `scaffold_enemy_ai` —— **3 kinds**：patrol / chase / shoot
- `scaffold_spawner` —— **2 kinds**：time 定时 / proximity 靠近触发
- `scaffold_game_loop` —— menu / play / over 状态机
- `scaffold_audio_controller` / `scaffold_camera_follow` / `scaffold_ui_screen`

所有模板字段都走 `@property` 让 Inspector 可调；numeric 字段带 `{ tooltip }` 注解。
</details>

<details>
<summary><b>媒体 / 骨骼 / 粒子 / 瓦片（14 工具）</b></summary>

- 媒体：AudioSource / Animation / ParticleSystem2D / VideoPlayer
- 骨骼动画：Spine + 资源导入 / DragonBones + 资源导入
- TiledMap：TiledMap / TiledLayer / TMX 资源导入
- AI 素材生成：`generate_asset`（CogView-3-Flash / Pollinations，SHA-256 缓存）/ `create_sprite_atlas`
- AnimationClip 关键帧生成器
</details>

<details>
<summary><b>场景工具 + Prefab + 批量操作（12 工具）</b></summary>

- Prefab：`create_prefab` / `instantiate_prefab`（带 fileId 唯一化）/ **`save_subtree_as_prefab`**
- 场景：`validate_scene` / `audit_scene_modules`（组件 vs 引擎模块一致性）/ `get_object` / `get_object_count` / `list_scene_nodes`
- **`batch_scene_ops`**：一次 read/write 跑多个 op；27 种 op 类型；**实测 200 工具调用 4293ms → 33ms（130x）**
- 场景全局：`set_ambient` / `set_skybox` / `set_shadows` / `set_fog`（LINEAR / EXP / EXP² / LAYERED）
</details>

<details>
<summary><b>🏭 构建 + 发布 + 构建后补丁（11 工具）</b></summary>

- `cocos_build`：headless 构建 web-mobile / wechatgame / ios / android，带 `source_maps` / `md5_cache` / `skip_compress_texture` / `inline_enum` / `mangle_properties`
- `cocos_start_preview` / `stop_preview` / `preview_status`
- **构建后补丁（4）**：`register_post_build_patch` / `list` / `remove` / `apply` —— 声明式 `json_set` / `regex_sub` / `copy_from`，`cocos_build` 成功后自动应用，跟着 git 走
- 项目设置：`set_native_build_config`（iOS/Android 包名/签名/朝向/icon）/ `set_bundle_config` / `set_wechat_subpackages`（4 MB 主包分包）
- 引擎模块：`get_engine_modules` / `set_engine_module`（开关 physics-2d-box2d / spine / video 等）
</details>

## 💡 Examples

仓库自带 3 个一键运行的演示项目：

```bash
.venv/bin/python examples/flappy-bird/build_flappy.py /tmp/flappy --port 8080
.venv/bin/python examples/click-counter/build_click_counter.py /tmp/click --port 8081
.venv/bin/python examples/breakout/build_breakout.py
```

运行后打开 `http://localhost:8080` 即可玩。

<details>
<summary><b>3D 滚球 Demo（mini 代码）</b></summary>

```python
# 1. 初始化 + 开启 3D 物理（默认 gravity = -10 m/s² 不是 -320 像素）
cocos_init_project("/tmp/roll3d")
cocos_set_physics_3d_config("/tmp/roll3d", gravity_y=-9.8)

# 2. 造个有摩擦系数的物理材质
ice = cocos_create_physics_material("/tmp/roll3d", "ice", friction=0.02, restitution=0.3)

# 3. 场景：Ball + Ground + 方向光
scene = cocos_create_scene("/tmp/roll3d/assets/scenes/game.scene")
canvas = scene["canvas_node_id"]

sun = cocos_create_node(scene_path, canvas, "Sun")
cocos_add_directional_light(scene_path, sun, illuminance=65000, shadow_enabled=True)

ball = cocos_create_node(scene_path, canvas, "Ball", lpos=[0, 5, 0])
cocos_add_rigidbody_3d(scene_path, ball, body_type=1)      # DYNAMIC=1（bitmask）
col = cocos_add_sphere_collider_3d(scene_path, ball, radius=0.5)
cocos_set_uuid_property(scene_path, col, "_material", ice["uuid"])

# 4. 雾 + release 构建
cocos_set_fog(scene_path, enabled=True, fog_type=1, density=0.05)  # EXP
cocos_build("/tmp/roll3d", debug=False, md5_cache=True)
```

</details>

## 🏭 商业化发布

<details>
<summary><b>iOS / Android 原生打包</b></summary>

```python
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
```

</details>

<details>
<summary><b>Asset Bundle</b></summary>

```python
# 把 assets/levels/ 标记成 Bundle，运行时 cc.assetManager.loadBundle('levels')
cocos_set_bundle_config(project, "assets/levels",
    compression_type={"web-mobile": "merge_dep", "wechatgame": "subpackage"})
```

</details>

<details>
<summary><b>微信小游戏分包（4 MB 主包分包）</b></summary>

```python
cocos_set_wechat_subpackages(project, [
    {"name": "level1", "root": "assets/levels/world1"},
    {"name": "audio", "root": "assets/audio"},
])
```

</details>

<details>
<summary><b>构建后补丁 —— 解决 build/ 每次重生成被刷掉的问题</b></summary>

Cocos 每次构建都会重新生成 `build/<platform>/`，手动改的 `style.css` / `project.config.json` 全被刷掉。通过声明式补丁登记一次，之后每次构建自动应用：

```python
cocos_register_post_build_patch(project, patches=[
    # ① JSON 精准 key 覆盖（解决 WeChat appid 被重置）
    {"platform": "wechatgame", "file": "project.config.json",
     "kind": "json_set", "path": "appid", "value": "wx000000000000demo"},

    # ② 正则替换
    {"platform": "web-mobile", "file": "style.css",
     "kind": "regex_sub",
     "find": r"background:\s*#[0-9a-fA-F]{3,6}",
     "replace": "background: #1c2833"},

    # ③ 整文件覆盖
    {"platform": "web-mobile", "file": "index.html",
     "kind": "copy_from", "source": "custom/index.html"},
])
```

**安全阀**：regex 编译预检 + 路径注入防御（拒绝 `..` / 绝对路径）+ drift 保护（正则不匹配报错而非静默跳过）+ `dry_run=True` 预检。

</details>

## ⚡ 性能调优

| 旋钮 | 默认 | 效果 |
|---|---|---|
| `cocos_batch_scene_ops` | — | 一次 read/write 跑多个 op；**200 工具调用 4293ms → 33ms（130x）** |
| 场景读缓存 | on | 按绝对路径 + `st_mtime_ns` LRU(8) 缓存；外部写盘自动失效 |
| Creator 安装缓存 | on | `list_creator_installs` 走 `functools.lru_cache`，session 内不重复扫 |
| `COCOS_CREATOR_PATH` | — | 指定 Creator 版本目录，优先级最高（CI / Docker） |
| `COCOS_CREATOR_EXTRA_ROOTS` | — | 追加扫描路径（POSIX `:` / Windows `;` 分隔） |
| `COCOS_MCP_SCENE_COMPACT=1` | off | scene 写盘 compact JSON（**500 对象 -41% 大小**） |
| Pillow lazy-import | — | 不触发图片操作的工具不需要 Pillow |

## 🎯 AI 友好度 / 可靠性护栏

- **结构化错误** —— `cocos_build` 失败返回 `{error_code, hint}`，9 种类型（`BUILD_TYPESCRIPT_ERROR` / `BUILD_MISSING_MODULE` / `BUILD_ASSET_NOT_FOUND` / `BUILD_TIMEOUT` / ...）
- **TS 错误结构化** —— `BuildResult` 带 `ts_errors: [{file, line, col, code, message}]`，AI 直接 Read+Edit
- **场景预检** —— `audit_scene_modules` 扫组件 vs `engine.json`，返回可复制的 `cocos_set_engine_module` 命令链
- **引擎模块映射表** —— 内置 `COMPONENT_REQUIRES_MODULE`（30+ 条）
- **脚本 UUID 幂等** —— `add_script` 接受 23 / 36 字符 UUID，re-add 保持 UUID 不变
- **构建后补丁** —— drift 保护 + 首个失败止损
- **TypedDict 契约** —— `BuildResult` / `ValidationResult` / `BatchOpsResult` 8 个 TypedDict，改字段忘同步自动失败

## 🐛 Troubleshooting

<details>
<summary><b>找不到 Cocos Creator 安装</b></summary>

默认扫描 `/Applications/Cocos/Creator` (macOS) 或 `%LOCALAPPDATA%\Programs\CocosDashboard\resources\.editors` (Windows)。如果路径非标：

```bash
export COCOS_CREATOR_PATH=/custom/path/to/CocosCreator.app
# 或追加扫描目录
export COCOS_CREATOR_EXTRA_ROOTS=/opt/cocos:/shared/editors
```

</details>

<details>
<summary><b>构建超时</b></summary>

首次构建 Creator 要 import 所有资源，可能超过默认 5 分钟。显式传 timeout：

```python
cocos_build(project, timeout_sec=900)
```

</details>

<details>
<summary><b>场景组件不生效（但构建成功）</b></summary>

多半是组件需要的引擎模块没启用。跑：

```python
cocos_audit_scene_modules(scene_path)
# → { ok: false, disabled: ["physics-2d"], actions: [...] }
```

把 actions 里的命令复制粘贴跑一遍即可。

</details>

<details>
<summary><b>微信小游戏 appid 被重置</b></summary>

Creator 每次重写 `project.config.json`。用构建后补丁：

```python
cocos_register_post_build_patch(project, patches=[
    {"platform": "wechatgame", "file": "project.config.json",
     "kind": "json_set", "path": "appid", "value": "wx000000000000demo"},
])
```

跟着 git 走，换机器 / 队友不会丢。

</details>

## 📊 质量保障

- **741 pytest 单元测试**，本地 < 15s 跑完
- **GitHub Actions CI 矩阵**：Ubuntu / macOS / Windows × Python 3.11 / 3.12
- **`mypy cocos/` 0 errors**
- **`ruff check` 0 errors**
- 所有 3D 组件字段默认值**逐一对齐 cocos-engine v3.8.6 源码**（含 regression 测试锁定）
- 跨平台：所有外部进程调用走 `sys.executable` / socket / `tempfile.gettempdir()`

## 🔐 Security & Privacy

- 所有操作**本地文件 I/O**，不上传项目代码
- `generate_asset` 默认走 CogView-3-Flash 国内免费 API；可切 Pollinations 或本地模型
- Playwright 闭环反馈仅访问**本地 preview server**
- 无任何遥测 / 埋点

## 📂 项目结构（简）

```
cocos-mcp/
├── server.py                 # MCP 入口（60 行 FastMCP + tools.register_all）
├── run.sh / run.bat
├── cocos/
│   ├── tools/                # MCP 工具薄包装，10 模块
│   ├── scene_builder/        # 场景 JSON 构造（physics / ui / ui_patterns / prefab ...）
│   ├── project/              # 资源导入 / UI token / 构建后补丁
│   ├── scaffolds/            # 9 个游戏逻辑 .ts 模板
│   ├── build.py              # CLI 构建 + 跨平台预览
│   ├── interact.py           # Playwright 闭环反馈
│   ├── gen_asset.py          # AI 生图（CogView / Pollinations + 缓存）
│   ├── errors.py / types.py / uuid_util.py / meta_util.py
├── examples/                 # 3 个一键 demo
├── tests/                    # 741 pytest
└── .github/workflows/test.yml
```

## 📄 License

**Proprietary · All Rights Reserved · Copyright © heitugongzuoshi**

未经书面授权，**不得复制、修改、分发、二次发布或将本项目用于任何商业用途**。
仅授权给已被邀请的协作者用于内部评估、试用与开发。

旧版本（≤v1.1.0）以 MIT 协议发布，相关分发已停止。本仓库当前版本（`1.2-dev`）起转为闭源。

---

### 商业授权 / 合作 / 定制

📧 **2282059276@qq.com**

服务内容：
- 商用授权（团队 / 公司）
- 定制开发（专属工具 / 特殊平台适配）
- 技术咨询（Cocos 3.8 AI 工作流 / headless CI 集成）
- 企业培训（AI + 游戏开发工作流）

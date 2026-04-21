# 设计决策笔记

[🇺🇸 English](./DESIGN_NOTES.en.md)

> 这份文档是 cocos-mcp 的**工程日志** —— 沉淀设计决策的"为什么"。
>
> Release notes（每个版本做了什么）移到 [Gitee Releases](https://gitee.com/csbcsb/cocos-mcp/releases)。
> 这里只留：**dogfood 反馈、Cocos 3.8 字段漂移对齐、Bug A/B 回归、架构取舍** —— 这些东西不适合塞进一行 git log，但将来有人问"为什么这个字段是 1 不是 0"时要能追溯。
>
> **中文版**是主线，按**主题**组织，面向维护者。
> **英文版**（[DESIGN_NOTES.en.md](./DESIGN_NOTES.en.md)）是**按 release 平铺**的历史详细记录，v1.2 起不再主动维护，作为冻结的历史参考。

---

## 📊 当前状态（2026-04）

- **184 工具**（起步 80）· **741 pytest**（起步 45）· **mypy 0 / ruff 0**
- CI 矩阵：Ubuntu / macOS / Windows × Python 3.11 / 3.12
- 3D 组件字段默认值**逐一对齐 cocos-engine v3.8.6 源码**

---

## 🔁 dogfood 驱动的关键修复

首次完整 dogfood（Flappy Bird，详见 [dogfood-flappy-report.md](./dogfood-flappy-report.md)）暴露了最常用工具里的三个**静默损坏型**问题，都做了回归测试锁定。

### Bug A — `cocos_add_script` 覆盖时重写 UUID

**现象**：改一个 `.ts` 文件的内容再调用 `add_script` 会**静默**生成新 UUID，改写 `.ts.meta`。场景 JSON 里原来通过压缩 UUID 引用这个脚本的 Component 瞬间变哑——组件还在但不执行任何代码。调用方没有任何错误提示。

**影响**：dogfood 里 GameScore.ts 重写一次，3 个引用它的节点全炸，排查了半小时才定位到 meta 里 UUID 被替换。

**修复**：
- 默认无 `uuid=` 参数时，存在 `.ts.meta` 就**复用原 UUID**，只覆盖源码
- 确实要强行换 UUID 的调用方显式传 `uuid=<new>`
- 返回值加 `created: bool` 字段，调用方能区分"新建"还是"沿用"
- 损坏的 meta（JSON parse 失败）自动回退到新建——避免 partial-write 永久毒化资源

文件：[cocos/project/assets.py::add_script](../cocos/project/assets.py)

### Bug B — `add_node` 在 prefab 文件上不写 PrefabInfo 子节点

**现象**：prefab 要求**每个节点**都有自己的 `cc.PrefabInfo` 入口，`fileId` 要唯一（Creator 用它对齐 per-instance override）。老代码对 prefab 文件上的 `add_node` 沿用了 scene 节点的默认 `_prefab: null`——在 scene 里是对的，但在 prefab 里就是破格式。

**影响**：实例化这种 prefab 时子节点 override 解析会崩；Creator 不会报错，只会把 override 静默丢掉。

**修复**：`add_node` / `batch_scene_ops.add_node` 检测 `.prefab` 路径后自动生成 PrefabInfo + `fileId`，并保证同 prefab 内 fileId 唯一。

### Bug C — MCP 工具目录有时刷新不及时

**现象**：deferred tool 目录会 cache 在 Claude 客户端的 session 启动时，**之后注册的新工具看不到**。dogfood 里一开始找不到 scaffolds / lint / audit / save-subtree 等工具，还以为没实现，最后发现是目录 stale。

**修复**：新增 `cocos_list_tools` 做运行时自省，返回 server 当前真正注册的工具表，按 16 个 category 分桶。agent 可以自诊断"这套工具版本是不是最新的"。

---

## 🧩 Cocos 3.8 字段漂移对齐

Cocos 小版本升级会静默改字段名、默认值、甚至枚举编码。直接读写 JSON 这种路线的本质风险就是得一个个追。以下是截至 3.8.6 验证过的关键漂移：

### AutoAtlas `.pac` shape（3.8 改了序列化布局）

| 维度 | 老写法（错） | 3.8 正确写法 |
|---|---|---|
| `.pac` body | 打包配置 in-line（maxWidth / padding / algorithm） | 单行 marker `{"__type__": "cc.SpriteAtlas"}`，**配置全挪到 `.pac.meta` userData** |
| Meta `ver` | `"1.0.7"` | **`"1.0.8"`**（版本闸门，不匹配**静默拒绝**）|
| Meta `userData` | `{}` | **17 个必需 key**：`removeTextureInBundle` / `removeImageInBundle` / `compressSettings` / 嵌套 `textureSetting` / ... |
| Algorithm | `"MaxRect"` | **`"MaxRects"`**（注意复数）|
| Defaults | 2048 / powerOfTwo=true / filterUnused=false | 3.8 默认 **1024 / false / true** |

这些错误**不会构建失败**，Creator 只会"按默认兜底"——hurts that 就是"构建成功但没打 atlas，draw call 没降"这种幽灵 bug。

### UI + Audio 字段漂移

`Button` / `Layout` / `AudioSource` 等组件在 3.8 里有若干字段重命名或形状变化。典型的：

- `AudioSource._clip` vs `clip`
- `Button._pressedColor` 的 Color 形状从 4 元数组变 object / 反过来
- `Layout` 的 spacing / padding 默认值调整

修复方式：每个漂移点都加了一个针对性的回归测试（`tests/test_new_features.py`、`tests/test_ui_batch*.py`），值 drift 一旦出现就测试失败。

### 物理字段漂移 + ERigidBodyType bitmask

**最坑的一个**：`ERigidBodyType.DYNAMIC = 1 / STATIC = 2 / KINEMATIC = 4`——这是 **bitmask 不是序数**。当时我们写成 0/1/2，引擎就按 0 = none 处理，rigid body 变成不受重力也不响应冲量的"鬼魂"。

**教训**：Cocos 的所有"看起来像枚举"的数字字段都要查 engine 源码确认是 enum 还是 bitmask。回归测试里用**显式数值**锁定：

```python
# tests/test_physics_3d.py
assert ERigidBodyType.DYNAMIC == 1   # NOT 0
assert ERigidBodyType.STATIC == 2
assert ERigidBodyType.KINEMATIC == 4
```

### `physics-2d-box2d` 子模块识别

Cocos 引擎模块有父子关系：`physics-2d` 是父，`physics-2d-box2d` / `physics-2d-builtin` 是子实现。RigidBody2D 要求的是**父模块存在 + 至少一个子实现启用**。

内置的 `COMPONENT_REQUIRES_MODULE` 映射表里把这层识别做对了——启用 `physics-2d-box2d` 也能满足 `physics-2d` 要求，跟 Cocos 自己的语义一致。

### `batch_ops` 参数对齐（dogfood v2 follow-up）

`batch_ops` 里的 `add_node` / `set_position` / `set_scale` 参数名**曾经**跟 `sb.add_node` / `set_node_*` 直接 API 不一样：

```python
# 直接 API
sb.add_node(scene, parent, "Bird", lpos=[0, 0, 0], lscale=[1, 1, 1])

# 老的 batch_ops
{"op": "add_node", "name": "Bird", "x": 0, "y": 0, "z": 0, "sx": 1, ...}  # 不同名
```

agent 按直接 API 的签名传 `lpos=(x, y, z)` tuple 给 batch，**静默被忽略**，节点全在 (0,0,0)、缩放默认 1。更糟的：batch 版的 `add_node` **从来就没读 lscale**（不管 tuple 还是 scalar），已经是 latent bug 一年了。

**修复**：三个统一 helper（`_resolve_lpos` / `_resolve_lscale` / `_resolve_xyz`）接受**两种形式**，tuple 优先，老的 scalar 写法向后兼容。

---

## 🎯 架构决策

### `cocos_batch_scene_ops` 为什么是第一优先级工具

**动机**：首次 dogfood 暴露了"200 次工具调用跑单节点 add / setter" → 每次 tool call 都要重新解析 scene JSON → 巨慢。

**测量**：
- 200 个工具调用：**4293ms → 33ms（130×）**
- 单次 read + 单次 write 跑完整批 op；27 种 op 类型

**实现**：`cocos/scene_builder/batch.py` 里统一 dispatch，同一个 `_load_scene` LRU 缓存 + 最后一次 `_save_scene`。错误捕获**per-op**，一个 op 失败不中断整批，返回 `{index: error}`。

**推广**：工具描述首行写了 `PREFERRED for ≥3 sequential mutations`，LLM 会优先使用。

**dogfood v2 扩展**：batch 加了 9 个新 op——polygon collider2d + 8 个 joint2d + `add_audio_source`——以前的"rigid body + collider + joint"10 个独立调用压到 1 个 batch。

### 场景读 LRU(8) + mtime 失效

**动机**：batch_ops 之外，连续多次独立 tool 调用（比如 agent 一个个 set_node_position）仍然每次 parse JSON。

**实现**：`cocos/scene_builder/_helpers.py::_load_scene` 走 `functools.lru_cache(8)`，key 是 `(abs_path, st_mtime_ns)`。外部进程写盘 → mtime 变 → 下次读自动 miss。

**容量 8**：覆盖 typical 工作流里同时开的 scene + 几个 prefab；再多会驱逐，但驱逐是 LRU，最近一次 batch 里摸过的文件一定在缓存。

### 构建后补丁为什么独立于 Creator build hooks

Creator 有 `onAfterBuild` 官方钩子，但：

- 要在 `package.json` 里配 `contributions.builder`，项目侵入性强
- 钩子只能 Creator 开着才跑，CI 里不行
- 每个 hook 是一个 TypeScript 文件，agent 写起来麻烦

**我们的方案**：`register_post_build_patch(patches=[...])` 把补丁声明**落 JSON** 到 `settings/v2/packages/post-build-patches.json`，跟着 git 走。`cocos_build` 成功后 Python 这边自动扫这个 JSON 跑补丁。

三种 patch 类型：
- `json_set` —— 精准 key 覆盖（典型场景：wechat appid 被刷掉）
- `regex_sub` —— 正则替换（style.css 主题色）
- `copy_from` —— 整文件覆盖（自定义 index.html）

**安全阀**：regex 注册时预编译 + 路径注入防御（拒绝 `..` / 绝对路径）+ drift 保护（正则不匹配直接报错，不静默跳过）+ `dry_run` 预检 + 首个 patch 失败 **止损**（不连锁）。

### 结构化错误 + TS 诊断结构化

**动机**：AI 读构建日志尾部非常蠢且不可靠。构建失败原因（typescript 错 / missing module / asset not found / timeout）应该结构化返回。

**实现**：
- `cocos_build` 返回 `{ok: False, error_code: "BUILD_TYPESCRIPT_ERROR", hint: "...", ts_errors: [{file, line, col, code, message}]}`
- 9 种 error_code，每种带 hint 告诉 AI 下一步该调什么工具
- TS 错误用正则从构建日志提取，agent 直接 Read + Edit 目标文件定位

**配套**：`cocos_audit_scene_modules` 返回 `actions: [cocos_set_engine_module(...), cocos_clean_project(...)]` **可复制粘贴的命令链**，agent 不用思考。

### TypedDict 契约漂移检测

**动机**：工具返回值的字段（比如 `BuildResult.error_code`）被意外改名 / 删除时，调用方沉默接受，一直用到运行时才炸。

**实现**：`cocos/types.py` 里 8 个 TypedDict（`BuildResult` / `ValidationResult` / `BatchOpsResult` / ...）。`tests/test_types.py` 用反射比对 `TypedDict.__annotations__` 和真实返回值的 keys。漏字段 / 多字段 / 改名都直接测试失败。

### 脚手架为什么生成 TS 源码而不是内置组件

**选择**：6 个 `scaffold_*` 工具生成 canonical `.ts` 模板写到用户项目里，返回压缩 UUID，不是 built-in 运行时组件。

**原因**：
1. **用户可改**：生成后是普通 `.ts`，用户的游戏逻辑调整不会受 cocos-mcp 版本束缚
2. **可读**：Inspector 可调（`@property` + `{ tooltip }` 注解），不是黑箱
3. **版本解耦**：cocos-mcp 升级不会 break 用户已生成的脚本
4. **跨项目可移植**：generated .ts 可以被 copy 到不走 MCP 的项目

**代价**：每个游戏项目里堆一份脚本，占几 KB；但对游戏项目这点 overhead 可忽略。

### 脚手架 kinds 枚举

- `player_controller`：4 种（platformer / topdown / flappy / click_only）
- `enemy_ai`：3 种（patrol / chase / shoot）
- `spawner`：2 种（time 定时 / proximity 靠近触发）
- `game_loop`：state 机（menu / play / over，每 state 两个 Inspector 回调）
- `input`：WASD + 方向键 + 触屏统一成 InputManager 单例
- `score`：当前 + 最高 + localStorage + 可选 Label 自动渲染

**单例安全**：InputManager null 安全——玩家脚本 null-check 它不存在也不 crash。agent 可以按任意顺序挂载脚本。

### UI 模式预设 + 响应式助手 + 主题

**UI 模式预设**（6 个）：`add_dialog_modal` / `add_main_menu` / `add_hud_bar` / `add_card_grid` / `add_toast` / `add_loading_spinner`。Agent 一次搭完整 UI 块，不用 6-8 步堆节点+Layout。

**响应式助手**（5 个）：`make_fullscreen` / `anchor_to_edge` / `center_in_parent` / `stack_vertically` / `stack_horizontally`。告别手填 Widget bitmask（12 种 flag 组合）。

**UI token 系统**（5 内置主题）：dark_game / light_minimal / neon_arcade / pastel_cozy / corporate。主题切换 = 一个 `set_ui_theme`，scene 里所有 token-aware 组件更新颜色 + 字号。

**UI lint**（8 条规则）：touch target 48×48 / 长文本剪字 / UI layer 错置 / WCAG 对比度 / 按钮重叠 / 字号框爆边 / 多按钮无 Layout / 嵌套 Mask。

---

## 🏭 商业化决策

### 从 MIT 转闭源（v1.2-dev 起）

**决策**：≤v1.1.0 是 MIT，v1.2-dev 起 Proprietary。

**原因**：
- MCP 生态 2025-2026 爆发式增长（官方 registry 破 1200 servers，8M downloads / MoM 85%），但 **<5% 的 MCP 做了付费**——像 App Store 早期
- 游戏引擎 MCP 赛道独立开发者仍有商业化窗口（Unity MCP 5.8k stars、Unreal MCP 1.2k stars、Cocos **零竞品**）
- cocos-mcp 的护城河不是源码，是"**对齐 Cocos 3.8 + 184 工具 + 字段漂移持续对齐**"，闭源更多是法律层面防无授权商业复用

**执行**：
- 旧 MIT 分发已停止；LICENSE 文件更新为 Proprietary 声明
- README 顶部 CTA：`📧 2282059276@qq.com`

### 发布走 Gitee Releases 而不是 PyPI

**决策**：不上 PyPI；分发方式是 Nuitka 编二进制 → GitHub / Gitee Releases。

**原因**：
- **PyPI 跟真闭源不兼容**：哪怕上 Nuitka wheel，PyPI 定位是开放包分发，闭源心智不匹配
- **Gitee Releases 对国内用户友好**：npm.org / PyPI 在国内企业网常被 block，Gitee 不会
- **Two-Repo 模式**：私有源码仓 + 公开发布门面仓（只有 README + Releases 挂二进制）
- **控制力**：版本能瞬间下架 / 加 EULA 点击同意 / 加 license key 校验

**对比 npm 路线**：npm + Nuitka + optionalDependencies 工程量 3-5 天；GitHub/Gitee Releases 工程量 1-2 天；后者对这个项目性价比更高。

### 双语文档（中文主版本 + 英文对照）

**决策**：所有文档都是 `FOO.md`（中文）+ `FOO.en.md`（英文）双版本。

**原因**：
- 目标用户一半在国内，中文是母语
- MCP 国际 registry / awesome-mcp / Smithery / MCPMarket 需要英文
- 中文为主保持作者维护效率；英文对照支持海外传播

---

## 📂 项目结构演化

### `server.py` 瘦身

历史：`server.py` 曾是 1200 行的 `@mcp.tool()` 大杂烩。

现在：60 行 = `FastMCP("cocos-mcp")` + `tools.register_all(mcp)`。所有工具在 `cocos/tools/<concern>.py` 下分 10 个模块：

```
cocos/tools/
├── core.py                 # UUID / project / asset / 常量 / UI token
├── scene.py                # scene / node / 基础组件 / 光照 / fog / prefab / batch / lint
├── physics_ui.py           # 2D 物理 + UI 组件
├── physics_3d.py           # 3D 物理
├── rendering_3d.py         # 3D 光源 + MeshRenderer
├── media.py                # audio / anim / particle / Spine / DB / TiledMap / VideoPlayer
├── ui_patterns.py          # UI 模式 + 响应式 + styled_text + 动画预设
├── interact.py             # Playwright 闭环反馈
├── scaffolds.py            # 6 个脚手架工具
├── composites.py           # 复合工具（add_physics_body2d / add_button_with_label）
└── build.py                # 构建 / 预览 / 发布配置 / 构建后补丁
```

按 **concern**（关注点）分，不是按 type（组件 / 资源）分——让相关工具挤在一起方便 grep 和理解。

### `scene_builder/` 按域拆分

`scene_builder/` 下也按 concern 拆：`physics.py` / `physics_3d.py` / `ui.py` / `ui_patterns.py` / `ui_lint.py` / `responsive.py` / `animation_presets.py` / `rendering.py` / `media.py` / `prefab.py` / `batch.py` / `modules.py`。

`__init__.py` 只做 re-export + 核心 scene 生命周期 + 基础 node / 组件工厂。

---

## 🚨 兼容性与未来方向

### 硬要求

- **Python 3.11+**（用到了 `Self` / `TypeAlias` / `match`）
- **Cocos Creator 3.8+**（测试过 3.8.6；<3.8 字段漂移不同不支持）
- **Pillow lazy-import**：不触发图片操作的工具不装 Pillow 也能跑（slim 环境 CI 友好）
- **Playwright 可选**：~200 MB chromium，不装时 Playwright 工具返回明确的 install hint；视觉 diff 走纯 Pillow，不依赖 Playwright

### 短期跟进（需要时做）

- `@cocos/ccbuild` + Nuitka 打包 → GitHub/Gitee Releases
- 英文文档的 awesome-mcp / Smithery / MCPMarket 提交
- code signing（macOS $99/year + Windows EV cert）
- 首次使用的交互引导（Claude Desktop / Cursor 的一键安装 badge）

### 明确不做的（曾考虑但放弃）

- **Route D（完全不依赖 Creator 构建）**：理论可行（引擎 bundle 里已有 `deserializeDynamic` 能读编辑器格式 JSON），但要重编引擎带 `BUILD=false` + 自研 SpriteFrame/Texture2D 编辑器格式生成器，每次 Cocos 升级都要重新对齐。**维护成本不值**——"对齐 Creator 一步"比"对齐整个 Creator build pipeline"简单一个量级。
- **Route C（改 Creator 官方 builder ccbuild）**：同上，cocos/cocos-engine 里 `editor-extends/utils/serialize/` 是 Creator 专利闭源代码（`.ccc` 加密，不在 `cocos-engine` 开源仓库）。绕过的收益不够。

---

## 📌 版本节点简表

| 版本 | 日期 | 主要变化 |
|---|---|---|
| ≤v1.1.0 | 2024 | MIT 开源；80 工具；45 测试；基础工具齐全 |
| v1.2-dev | 2026 | 闭源启动；184 工具；741 测试；dogfood v1+v2 反馈全量修复；3D 物理+渲染齐全；UI 模式预设 + 脚手架；Playwright 闭环反馈；构建后补丁 |

详细 per-release changelog 见 [DESIGN_NOTES.en.md](./DESIGN_NOTES.en.md)。

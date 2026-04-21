# Dogfood 报告：用 cocos-mcp 做 Flappy Bird

[🇺🇸 English](./dogfood-flappy-report.en.md)

cocos-mcp 的**首次真人 dogfood**。环境：macOS，**未安装 Cocos Creator**（所以没跑 `cocos_build`，没做运行时验证）。纯粹验证 scene / prefab / script / settings JSON 直写层。

---

## 1. 摘要

用大约 **45 次 cocos-mcp 工具调用**、**一次 session**，搭出了一个结构完整的 Flappy Bird 骨架：scene + prefab + 8 个脚本 + Menu/Play/GameOver 三态 UI + 物理 + 音频。Scene 校验干净（`valid=true, 76 objects, 0 issues`）；Prefab 校验有 3 个预期内的警告。**达成 ~75% 预定目标**。

两个硬阻碍：
1. 运行中的 MCP server **stale**，本该提供的 scaffold / lint / audit / assert / save-subtree 工具在 deferred 目录里找不到
2. `cocos_create_node` / `batch_scene_ops.add_node` 在 **prefab 文件**上**不写 PrefabInfo 子节点**——子节点全是 `_prefab: null`，运行时会坏（真 bug）

**体感**：核心 scene-building 工具干净可批量，但：
- 返回值贫瘠（裸 int，没有命名键）
- Prefab 支持明显二等公民
- "写脚本"路径有坑：覆盖同路径会换 UUID，静默损坏场景

**结论**：我会再用。比手写 scene JSON 好太多。但**离"描述一下，游戏就出来了"还有距离**——agent 仍然要在脑子里追 20 多个 id，还要懂 Cocos 的一些内部概念（PrefabInfo / 压缩 UUID / `__id__` 引用）。

---

## 2. 时间线

| # | 步骤 | 工具调用数 | 成功率 |
|---|---|---|---|
| 1 | Bootstrap（bash mkdir + package.json）| 0（不走 MCP，因为 `cocos_init_project` 要 Creator）| — |
| 2 | 场景 + 物理 + 分辨率（4 调用）| 4 | **首次全过** |
| 3 | 写 8 个脚本（`cocos_add_script` × 8）| 8 | 全过 |
| 4 | 压缩 8 个 UUID（`cocos_compress_uuid` × 8）| 8 | ⚠️ **应该是 1 调用的 5 步工作流**——`add_script` 返回里就该带 `uuid_compressed` |
| 5 | 一次 batch 造 8 个节点 | 1 batch | 漂亮 |
| 6 | 挂 4 个 singleton 脚本到 GameManager（`attach_script` × 4）| 4 | 返回裸 int，要自己心算 InputManager=21 / GameScore=22 / ... |
| 7 | Bird 的 UITransform+Sprite + 容器们 | 1 batch (8 ops) | 过 |
| 8 | Bird + Ground + Ceiling 物理 | **10 个独立调用** | **batch_ops 不支持物理/collider ops，摩擦** |
| 9 | 连 `Bird.rb → RigidBody2D` | 1 | 过 |
| 10 | Menu / GameOver / HUD 节点 | 1 batch (9 ops) | 过 |
| 11 | UI label + button | 1 batch (18 ops) | 过 |
| 12 | 连 2 个按钮点击事件 | 2+2 | 过，但返回的 dict 带 `_componentId: ""` 让人不舒服 |
| 13 | 连 5 个 `@property` | 1 batch | 过 |
| 14 | 创建 Pipe prefab | 1 | 过 |
| 15 | 填充 prefab 子节点 | batch + 独立 | **踩 Bug B（PrefabInfo 缺失）** |
| 16 | 挂 Pipe.ts 到 prefab root + 连 `PipeSpawner.pipePrefab` | 1 | 过 |
| 17 | 覆盖 GameScore.ts 加一个 `finalScoreLabel` 字段 | 1 | **踩 Bug A（UUID 被重写）**，手工 Edit 回滚 meta |
| 18 | 连 `finalScoreLabel` | 1 | 过 |
| 19 | 两个 AudioSource + 连 bgm/sfx | 4 | 过 |
| 20 | 启用 ui / 2d / audio 引擎模块 | 3 | 过 |
| 21 | 设起始场景 + 加入 build list | 2 | 过 |
| 22 | 最终 `cocos_validate_scene` | 1 | `valid=true, 76 objects, 0 issues` 🎉 |

### 明显应该合并成 1 步的 5+ 步工作流

- **"写脚本 + 挂节点"** = `add_script` → `compress_uuid` → `attach_script`（3 次，永远）→ 应有 `cocos_add_and_attach_script`
- **"造个普通按钮"** = `add_node` → `add_uitransform` → `add_sprite` → `add_button` → `add_node(label)` → `add_label`（6 步）→ 应有 `cocos_add_button_with_label(parent, text, click_events, width, height)`
- **"刚体+碰撞体"** = `add_rigidbody2d` + `add_box_collider2d`（恒两步）→ 应有 `cocos_add_physics_body2d(node_id, shape, ...)`
- **"批量结果拿回来连 @property"**：要记 batch 结果的 component_id 位置，然后 `link_property`。如果 `batch_scene_ops` 接受 per-op `name` 并返回 name→id map，就一行搞定

---

## 3. 摩擦点排序

### 🔴 HIGH - scaffold / validator / save-subtree 工具在 session 里拿不到

**工具**：9 个 scaffolds、`cocos_audit_scene_modules`、`cocos_lint_ui`、`cocos_assert_scene_state`、`cocos_save_subtree_as_prefab`、`cocos_add_hud_bar`。都在 `cocos/tools/{scaffolds,scene,ui_patterns}.py` 里有（grep 能看到）。但**连到 MCP 客户端的 server 是旧的**——deferred tool list 只有 139 个 `cocos_*`，仓库里其实已经注册了 179 个。

- **试过什么**：`ToolSearch query="scaffold"` 返回空；`select:mcp__cocos-mcp__cocos_scaffold_player_controller` 返回 "No matching deferred tools found"
- **实际怎么做**：硬手写 8 个游戏脚本（`cocos_add_script`），只用可见的 `cocos_validate_scene`
- **建议修复**：
  - 确保安装后重新生成 MCP 目录
  - 加一个 top-level `cocos_list_tools` 做运行时自省，让 agent 能自诊断

### 🔴 HIGH - `cocos_add_script` 覆盖同路径时重写 UUID

**工具**：`cocos_add_script`
- **试过什么**：第二次调 `add_script` 同一个 `rel_path`，想加一个 `@property` 字段到 `GameScore.ts`
- **发生了什么**：**静默**生成新 UUID（`72c085d6-…`），重写 meta。场景还引用老的压缩 UUID `07768bD07FFE4/Gy+SO/0mm`，所有组件变哑
- **实际怎么做**：手工 `Edit` 改回 `.ts.meta` 里的 UUID。**用户如果没文件写权限就卡死**
- **建议修复**：
  - 文件存在 → 复用 meta 里的 UUID（**幂等模式**）
  - 或加 `cocos_update_script(rel_path, source)` 明确保持身份
  - 或拒绝覆盖 + 返回 existing UUID 让调用方自己决策

### 🔴 HIGH - `batch_scene_ops` 返回值用位置 index 无命名

**工具**：`cocos_batch_scene_ops`
- **试过什么**：一次 batch 造 8 个节点，`results: [13,14,15,16,17,18,19,20]`
- **发生了什么**：我得把 op list 回头看一遍才知道哪个 id 对应哪个节点。18 ops 的 UI batch 更难，要精确数到 "op #13 是 GameOverBest 那个 label"
- **建议修复**：op 可选传 `name: "myHudLabel"`，返回 `results: {byIndex: [...], byName: {myHudLabel: 65}}`。或更丰富：`results: [{op: "add_node", name: "GameManager", object_id: 13}]`

### 🔴 HIGH - 物理 / joint ops 不在 `batch_scene_ops` 里

**工具**：`cocos_batch_scene_ops`
- **试过什么**：想一个 batch 跑完 Bird/Ground/Ceiling 的刚体+碰撞体+Boundaries
- **发生了什么**：读文档后发现 op list 只覆盖 UI / 结构 / 脚本 ops，不含物理。没尝试
- **实际怎么做**：10 个独立调用——RigidBody2D × 3 + BoxCollider2D × 3 + Boundaries × 3 + 冗余 1
- **建议修复**：扩展 batch ops 覆盖 `add_rigidbody2d` / `add_*_collider2d` / 8 个 joint / `add_audio_source` / generic `attach_component`

### 🟡 MEDIUM - prefab 文件上的 `cocos_create_node` 不写 PrefabInfo 子节点

**工具**：`cocos_create_node` / `batch_scene_ops.add_node`（当 `scene_path` 以 `.prefab` 结尾时）
- **试过什么**：对 `Pipe.prefab` 调 `add_node parent_id=1` 添加 `PipeTop` / `PipeBottom`
- **观察**：子节点写成 `_prefab: null`，没有旁边的 `cc.PrefabInfo`。根 Pipe 节点是对的：`_prefab: {__id__: 2}` → `cc.PrefabInfo{fileId: <prefab_uuid>}`。**Cocos 运行时期望 prefab 里每个节点有自己的 PrefabInfo + 唯一 `instanceId`**
- **影响**：实例化时可能崩或静默丢数据。`cocos_validate_scene` 也检测不出
- **建议修复**：检测 `.prefab` 后缀 → 每个新节点自动插一个 `cc.PrefabInfo`，共享 root `fileId`。可以在 `cocos/scene/prefab_writer.py` 里新做一个，让 `create_node` 对 `.prefab` 路径委托到它

### 🟡 MEDIUM - `cocos_validate_scene` 对 prefab 和 scene 一视同仁

- 对 `Pipe.prefab` 调用返回 3 个假阳性 issue："*UITransform on node 'Pipe'(#1) is NOT under any Canvas*"
- 实际：prefab 是运行时挂 canvas 下的，不该查
- **建议修复**：自动检测 `.prefab` 跳过 canvas 检查。或加 `cocos_validate_prefab` 带 prefab 语义

### 🟡 MEDIUM - mutation 工具返回裸 `{"result": N}` int

- `attach_script` 返回 `{"result": 21}` —— **component_id 还是 node_id?**（答案：component_id）
- `link_property` 返回 `{"result": "linked 24.bgm -> 74"}` —— 人类能读，程序无用
- **建议修复**：结构化返回
  - `attach_script` → `{component_id: 21, node_id: 13, type: "cc.CustomComponent", script_uuid: "…"}`
  - `link_property` → `{success: true, component_id: 24, prop: "bgm", target_id: 74}`

### 🟢 LOW - `cocos_add_script` 只返回 36 字符 UUID，没给压缩形式

已在上面的"1-call composite"里提了，单独再标一次。

### 🟢 LOW - `cocos_make_click_event` 返回的 dict 要 `_componentId: ""`

这是 Cocos 内部 quirk（引擎优先按 class 名认而不是 id）。docstring 里写清楚原因，或自动删掉这个字段。

### 🟢 LOW - 没有"改 meta"工具

踩 Bug A 后我需要修 meta 的 UUID——没有 MCP 路径，只能用 `Edit`。加个轻量 `cocos_patch_meta(path, changes)` 能闭环。

---

## 4. 确认的 Bug

### Bug A — `add_script` 覆盖同路径**静默**换 UUID
- **重现**：`cocos_add_script(project, "assets/scripts/Foo.ts", "...")` → 再 `cocos_add_script(project, "assets/scripts/Foo.ts", "new source")`。第二次**静默**返回新 UUID 并重写 `Foo.ts.meta`。所有通过压缩 UUID 引用 `Foo` 的场景全变哑
- **影响**：🔴 HIGH。迭代脚本时静默损坏场景
- **建议修复**：幂等模式。文件+meta 都在 → 保留 UUID 只更新源码

### Bug B — `create_node` / `batch_scene_ops.add_node` 对 `.prefab` 文件不写 PrefabInfo
- **重现**：见 HIGH 5
- **影响**：🟠 MEDIUM-HIGH。带子节点的 prefab 实例化可能不对
- **建议修复**：`scene_path.endswith(".prefab")` → 自动每个节点插 `cc.PrefabInfo` + 连 `_prefab: {__id__: N}`

### Bug C（疑似，未确认）— ToolSearch 找不到 scaffold / lint / audit 工具
- `cocos/tools/{scaffolds,scene,ui_patterns}.py` 里确实有，但 ToolSearch keyword 和 exact name 都找不到
- 可能原因：
  - MCP server 进程 stale（最可能——deferred list 比仓库新 commit 晚 ~5 个）
  - FastMCP 没 re-register
  - 目录缓存
- **如果不是 stale-server 问题**：真注册 bug，值得查。验证 `tools/__init__.py register_all` 是否真把所有 submodule 接到了运行中的 server

---

## 5. 缺失的工具（按优先级）

1. **`cocos_add_and_attach_script`** — 合 `add_script` + `compress_uuid` + `attach_script`。**最想要的复合工具**。今天做了 8 次这个三步曲
2. **`cocos_update_script`** — 显式幂等的源码替换，保留 UUID。闭 Bug A
3. **`cocos_add_button_with_label`** — 造按钮 + 子 label 一次搞定。每个 UI 至少 3 个
4. **`cocos_add_physics_body2d`** — 合 RigidBody2D + 形状 collider。每 session 至少 3 次
5. **`cocos_batch_scene_ops` 扩展 ops** — 物理 / joint / audio_source / 通用 attach_component
6. **`cocos_wire_button_to_script`** — 端到端 `(scene, button_node, target_component_name, handler)` → 建 click_event + 调 add_button
7. **`cocos_save_subtree_as_prefab`** — 想把搭好的 Pipe 子树抽成 prefab，没有就只能从头重建（还踩了 Bug B）。task prompt 说这个有，但 session 里拿不到
8. **`cocos_validate_prefab`** — 知道 prefab 语义的验证器，不对 non-canvas UITransform 抱怨
9. **`cocos_list_tools`** — 自省。让 agent 知道真正可用的工具，别依赖 deferred search
10. **`cocos_patch_meta`** — 改 `uuid` / sub-metas / 其他 meta 字段，不重写 asset
11. **`cocos_get_component_info(scene, component_id)`** — "component 35 是啥类型？"的反查

---

## 6. 意外的默认值

- **`cocos_add_rigidbody2d(body_type=2)`** 默认 **Dynamic**——对玩家对，对其他 3+ 个 static/kinematic 体（ground / ceiling / pipe halves）错。Static 在 typical 场景里反而是最常见的（所有地形 + 所有墙壁），Static 默认惊讶的人会少
- **`cocos_add_sprite(size_mode=0)`** 是 CUSTOM（用 UITransform 的 contentSize）。没传 sprite_frame_uuid 但又设了 `color_*`，你默认得到一个**不可见的矩形**——没 frame 时 Sprite 啥也不画。用占位 UUID（`birdplaceholder@f9941`）绕开。建议默认 `internal://default-sprite` 1×1 白色 frame，让"debug 染色矩形"至少能看见
- **`cocos_add_box_collider2d(width=100, height=100)`** 默认不继承 UITransform 尺寸。`width=0, height=0` 能解释成"继承 contentSize" 会好
- **`cocos_create_scene(clear_color_r=135, g=206, b=235)`** 天蓝色。Flappy 合适，RPG 奇怪。`clear_color=None` → 黑或透明 + docstring 提示
- **`cocos_set_physics_2d_config(gravity_y=-320)`** 默认。Flappy 要 `-980` 才有手感。默认值适合"羽毛飘"型 platformer 但熟悉 Cocos `(0, -320)` 或 Box2D `(0, -9.8 m/s²)` 的人会惊讶。docstring 里说清楚

---

## 7. 好用的地方

- **`cocos_create_scene` 一次性返回所有 canonical id**——不用 round-trip 发现步骤。⭐⭐⭐⭐⭐
- **`cocos_batch_scene_ops` 吞吐是真的**——18 UI component ops 一次文件 I/O。工具能吸一整块 UI 面板时，agent 速度感觉不同量级
- **`cocos_compress_uuid` / `cocos_decompress_uuid`**——显式、快、好理解。不用挖 Cocos 内部就知道 23 字符形式存在
- **`cocos_make_click_event` 返回可直接粘的 dict** 插到 `cocos_add_button(click_events=[…])` 里。关注点分离漂亮
- **`cocos_list_scene_nodes`** 格式紧凑可重读——当 "source of truth" 在 edits 之间用。`components: [21,22,23,24]` 救了我
- **`cocos_get_engine_modules` + `cocos_set_engine_module` 对**——清清爽爽
- **`cocos_validate_scene`** 对 scene 完美——简洁、诊断式、能抓 ref-out-of-range
- **所有工具错误**（我踩到的）都返回可读的 non-zero response——没有神秘的 "Internal error"

---

## 8. `cocos_build` 大概会在哪里坏（没跑，推测）

1. **没真实 sprite-frame 资产**。每个 `cocos_add_sprite` 用占位 UUID（`birdplaceholder@f9941`、`btnbg@f9941`、`pipeplaceholder@f9941`）。构建时 asset-DB 查找失败，Cocos 一般 fallback 到白方块或报错。**修**：用 `cocos_add_image` 放真 PNG + `cocos_set_uuid_property` 替换 6 个占位引用；或直接用 `cocos_generate_asset`
2. **没音频 clip**。`AudioController.bgm / .sfx` 指向 AudioSource 组件，但组件 `clip_uuid=None`。`playOneShot(null)` 是 no-op——不炸，只是静音
3. **Pipe prefab 子节点缺 PrefabInfo（Bug B）**。实例化时可能只渲染 root，子节点丢；或按 Cocos 版本直接崩
4. **物理碰撞组没设**。每个 rigidbody 用默认 group/mask = 1/0xFFFFFFFF。Bird + Pipe + Ground 互相碰撞正好是对的，但用户未来加更多 body 时会意外
5. **UI 根面板没 `_anchorPoint` 定制 + 没 Widget**。Menu/GameOver root 是全屏（480×720），设计分辨率一变就不重布局
6. **GameManager 没做 scene 间 `DontDestroyOnLoad` 等价物**。singleton 假设只在这一场景，目前 OK

报告里的 Bug A/B **不是 build-blocking**——scene 自己能 validate。但都是**静默损坏**：A 破坏重写脚本的活引用；B 造出格式错误的 prefab，运行时才知道坏

---

## 9. 推荐行动（优先级）

1. **`cocos_add_script` 修成幂等**（Bug A）。高频操作，当前行为静默损坏 scene。要么覆盖时保留 UUID，要么返回 existing UUID + `created: false`
2. **`cocos_create_node` / `batch_scene_ops.add_node` 支持 prefab**（Bug B）。检测 `.prefab` 后缀 → 每个子节点写对应 `cc.PrefabInfo`
3. **扩展 `cocos_batch_scene_ops` 覆盖物理 / joint / audio_source / attach_component**。能留在一个 batch 里的 agent 快得多，transcript 也清爽
4. **batch 结果可命名**：`{"op": "add_node", "name": "gm", ...}` → `results: {gm: 13, bird: 14, ...}`。10+ op batch 的 bookkeeping 成本砍掉
5. **所有 mutation 工具结构化返回值**——不再裸 `{"result": 21}`。每个 `add_*` / `attach_*` 返回 `{component_id, type, node_id}`。Agent 需要拿回它刚插进去东西的结构化形式
6. **`cocos_add_script` 直接返回 `uuid_compressed`**——避免强制 follow-up。`cocos_create_prefab` 同理
7. **发布 top 3 复合工具**：`add_and_attach_script` / `add_button_with_label` / `add_physics_body2d`。不是语法糖——**这才是 agent 思考的形状**
8. **工具注册自测**：确保 `server.py` boot 时真注册了所有 `tools.*.register()` 模块，每个注册的工具都在 MCP deferred catalog 里可达。加个集成测试 `mcp.list_tools()` 断言 N==179
9. **教会 `cocos_validate_scene` 识别 prefab**：`.prefab` 后缀跳过 "not under canvas" 检查；或加 `cocos_validate_prefab`
10. **统一 ID 返回语义文档**：每个 `add_*` / `attach_*` / batch op 说清楚返回 int 是 node_id 还是 component_id。也许带前缀：`{"kind": "component", "id": 21}`

---

## 附录：产生的文件

- `/tmp/dogfood-flappy/assets/scenes/Game.scene` — 76 对象，validates clean
- `/tmp/dogfood-flappy/assets/prefabs/Pipe.prefab` — 结构错（Bug B）但可解析
- `/tmp/dogfood-flappy/assets/scripts/{Bird,Pipe,PipeSpawner,GameLoop,GameScore,AudioController,InputManager,Boundaries}.ts`
- `/tmp/dogfood-flappy/settings/v2/packages/{project,engine}.json` — physics-2d-box2d + ui + 2d + audio 启用，重力 -980，start scene + build list 设好

大约 **45 次 cocos-mcp 调用**。没生成资源（task 约束）。没跑构建（task 约束）。

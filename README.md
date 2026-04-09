# cocos-mcp

无头 Cocos Creator 3.8 MCP 服务器 —— 让 AI 在**不打开编辑器**的情况下自主开发完整的 Cocos 游戏。

## 安装

```bash
# 1. 克隆
git clone https://gitee.com/csbcsb/cocos-mcp.git ~/.claude/mcp-servers/cocos-mcp

# 2. 装依赖
cd ~/.claude/mcp-servers/cocos-mcp
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install "mcp[cli]" Pillow

# 3. 注册到 Claude Code
claude mcp add -s user cocos-mcp -- bash ~/.claude/mcp-servers/cocos-mcp/run.sh

# 4. 重启 Claude Code
```

## 前置要求

- [Cocos Creator](https://www.cocos.com/creator-download) 3.x（测试过 3.8.6，其他 3.x 版本应该也行）
- Python 3.11+（`uv` 或 `pip` 均可安装依赖）
- 任何支持 MCP 的 AI 客户端（Claude Code / Claude Desktop / Cursor 等）

## 使用

装好后重启 Claude Code，直接说：

- "做一个贪吃蛇游戏"
- "做一个 2048"
- "做一个带物理碰撞的平台跳跃"

Claude 会自动调用 80 个 MCP 工具完成全流程：初始化项目 → 写脚本 → 构建场景 → headless 编译 → 浏览器预览。**全程不用打开 Cocos Creator 编辑器。**

## 示例

仓库自带 3 个可一键运行的示例：

```bash
# Flappy Bird
.venv/bin/python examples/flappy-bird/build_flappy.py /tmp/flappy --port 8080

# 点击计数器
.venv/bin/python examples/click-counter/build_click_counter.py /tmp/click --port 8081

# 弹球打砖块（含 Box2D 物理）
.venv/bin/python examples/breakout/build_breakout.py  # 看脚本里的端口配置
```

运行后打开 `http://localhost:8080` 即可在浏览器里玩。

## 80 个工具

| 类别 | 数量 | 包含 |
|---|---|---|
| UUID | 3 | 生成 / 压缩 / 解压 |
| 项目 | 4 | 检测安装 / 初始化 / 信息 / 资源列表 |
| 资源 | 6 | 脚本 / 图片 / 音频 / 通用文件 / meta 升级 / SpriteFrame UUID |
| 场景节点 | 10 | 创建 / 移动 / 删除 / 复制 / 位置 / 缩放 / 旋转 / 层级 / 查找 / 列表 |
| 基础组件 | 6 | UITransform / Sprite / Label / Graphics / Widget / 通用 add_component |
| 物理 | 4 | RigidBody2D / BoxCollider / CircleCollider / PolygonCollider |
| UI | 7 | Button / Layout / ProgressBar / ScrollView / Toggle / EditBox / Slider |
| 渲染 | 5 | Camera / Mask / RichText / 9-slice Sprite / Tiled Sprite |
| 媒体 | 3 | AudioSource / Animation / ParticleSystem2D |
| 骨骼动画 | 4 | Spine / Spine 资源导入 / DragonBones / DB 资源导入 |
| TiledMap | 3 | TiledMap / TiledLayer / TMX 资源导入 |
| 脚本 | 5 | 挂载 / link_property / set_property / uuid_property / 查找节点 |
| 预制体 | 1 | 创建空 prefab |
| 动画文件 | 1 | AnimationClip 关键帧生成器 |
| 按钮事件 | 1 | ClickEvent 序列化 |
| 场景工具 | 5 | 验证 / 节点列表 / 对象查看 / 对象计数 / 批量操作 |
| 构建发布 | 9 | 构建 / 预览 / 清理 / 首场景 / 场景列表 / 微信 appid / 引擎模块 / 分辨率 / 常量 |

## 项目结构

```
cocos-mcp/
├── server.py              # MCP 入口（80 个 @mcp.tool）
├── run.sh                 # 启动器
├── cocos/
│   ├── uuid_util.py       # UUID 压缩算法
│   ├── meta_util.py       # .meta 文件读写
│   ├── scene_builder.py   # 场景 JSON 构造
│   ├── project.py         # 项目初始化 + 资源导入
│   └── build.py           # CLI 构建 + 预览 + 引擎配置
├── examples/              # 3 个一键示例
├── tests/                 # 44 个 pytest 单元测试
├── Dockerfile
└── requirements.txt
```

## 协议

MIT

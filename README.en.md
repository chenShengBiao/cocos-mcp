# cocos-mcp

> Headless [Cocos Creator 3.8](https://www.cocos.com/creator-download) MCP server — ship a complete 2D or basic 3D mini-game in 30 minutes, with AI, without opening the editor GUI or writing a line of TypeScript.

[🇨🇳 中文文档](./README.md)

![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-v1.2-green)
![Platforms](https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![Cocos Creator](https://img.shields.io/badge/Cocos%20Creator-3.8%2B-orange)
![Tools](https://img.shields.io/badge/tools-184-brightgreen)
![Tests](https://img.shields.io/badge/tests-741%20passing-success)
![License](https://img.shields.io/badge/license-Proprietary-red)

> 🔐 **Commercial · Closed Source**
> Access / trial / licensing inquiries: 📧 **2282059276@qq.com**
> Pre-v1.1.0 releases were MIT-licensed; current version (`1.2-dev`) is proprietary.

---

## ✨ Why cocos-mcp

- 🎮 **Fully headless** — direct JSON I/O on `.scene` / `.prefab` / `.meta` files; no editor GUI required (unique among game-engine MCPs)
- ⚡ **One-shot game delivery** — "make a Flappy Bird" / "make 2048" / "make a platformer with 2D physics"; AI drives 184 tools end-to-end
- 🔁 **Playwright closed-loop feedback** — AI can click, press keys, read JS state, do visual diffs; it literally plays the games it builds
- 🎯 **9 game-logic scaffolds** — player / enemy / spawner / game_loop / input / score / audio / camera_follow / ui_screen (canonical TypeScript templates)
- 🎨 **5 built-in UI themes + 6 UI pattern presets** — `add_dialog_modal` / `add_main_menu` / `add_hud_bar` ship full UI blocks in one call
- 🏭 **One-command release** — iOS / Android / WeChat mini-game, Asset Bundle, 4MB main-package subpackaging, declarative post-build patches

## 📋 Requirements

- [Cocos Creator 3.8+](https://www.cocos.com/creator-download) (tested on 3.8.6)
- Python 3.11 or 3.12
- Any MCP client: [Claude Desktop](https://claude.com/download) · [Claude Code](https://claude.com/claude-code) · [Cursor](https://cursor.com) · [Windsurf](https://codeium.com/windsurf) · VS Code

## 🚀 Quick Start

> Repository is private. Contact the author for access (`2282059276@qq.com`).

```bash
# 1. Clone (requires your access credentials)
git clone https://gitee.com/csbcsb/cocos-mcp.git ~/.claude/mcp-servers/cocos-mcp

# 2. Install dependencies
cd ~/.claude/mcp-servers/cocos-mcp
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install .

# 3. Register with your MCP client (see Client Configuration below)
```

Then restart the client and say:

> "Make a snake game"
> "Make a physics-based platformer"
> "Instantiate this character prefab 10 times in the scene"
> "Build and package as a WeChat mini-game, with `levels/` as subpackages"

## ⚙️ Client Configuration

<details>
<summary><b>Claude Code (recommended)</b></summary>

One command:

```bash
claude mcp add -s user cocos-mcp -- bash ~/.claude/mcp-servers/cocos-mcp/run.sh
```

Restart Claude Code to load.

</details>

<details>
<summary><b>Claude Desktop</b></summary>

Edit (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

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

Edit `~/.cursor/mcp.json`:

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

Edit `~/.codeium/windsurf/mcp_config.json`:

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
<summary><b>VS Code (including GitHub Copilot Chat)</b></summary>

In project root or `~/.vscode/settings.json`:

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

> **Windows users**: replace `bash /path/to/run.sh` with `cmd /c /path/to/run.bat`, or invoke `python server.py` directly after activating the venv.

## 🔄 Updating

For existing installs, pull the latest and sync deps (using the default path `~/.claude/mcp-servers/cocos-mcp`):

```bash
cd ~/.claude/mcp-servers/cocos-mcp
git pull
uv pip install --python .venv/bin/python .   # syncs deps (pyproject may have new packages)
```

Then **fully restart your MCP client** (Claude Code / Desktop / Cursor / ...).
Reason: the MCP server is a long-running child process; Python code is already loaded in memory, so the old version keeps running until the client relaunches.

Smoke-test the install:

```bash
~/.claude/mcp-servers/cocos-mcp/.venv/bin/python -c "import cocos, server; print('import OK')"
```

> Windows users: use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`.

## 🧰 Tools (184 total)

> The server prints the registered count to stderr on startup: `cocos-mcp: N tools registered…`

<details>
<summary><b>UUID / Project / Assets (15 tools)</b></summary>

- UUID: `new_uuid` / `compress_uuid` (23-char short form) / `decompress_uuid`
- Project: `list_creator_installs` / `init_project` / `get_project_info` / `list_assets`
- Assets: `add_script` / `add_image` / `add_audio_file` / `add_resource_file` / `upgrade_image_meta` / `set_sprite_frame_border` (9-slice) / `get_sprite_frame_uuid` / `constants`
</details>

<details>
<summary><b>Scene Nodes + Base Components (16 tools)</b></summary>

- Nodes: `create_scene` / `create_node` / `move_node` / `delete_node` / `duplicate_node` / `set_node_position/scale/rotation/active/layer` / `find_node_by_name` / `list_scene_nodes`
- Base components: `add_uitransform` / `add_sprite` / `add_label` / `add_graphics` / `add_widget` / `add_component` (generic)
</details>

<details>
<summary><b>2D Physics (12 tools)</b></summary>

- `add_rigidbody2d` + 3 colliders (Box / Circle / Polygon)
- All **8 Joint2D types**: Distance / Fixed / Hinge / Spring / Mouse / Slider / Wheel / Relative
- `set_physics_2d_config` (gravity / sleep threshold / sub-steps)
</details>

<details>
<summary><b>3D Physics + Rendering (18 tools)</b></summary>

- 3D physics: `add_rigidbody_3d` + 8 colliders (Box / Sphere / Capsule / Cylinder / Cone / Plane / Mesh / Terrain) + 2 CharacterControllers + `set_physics_3d_config` + `create_physics_material`
- 3D rendering: `add_directional_light` / `add_sphere_light` / `add_spot_light` / `add_mesh_renderer` / `add_skinned_mesh_renderer`
- All component field defaults **aligned to cocos-engine v3.8.6 source** — e.g. `ERigidBodyType.DYNAMIC=1 / STATIC=2 / KINEMATIC=4` (bitmask, not 0/1/2) is regression-locked
</details>

<details>
<summary><b>UI Components + Pattern Presets + Responsive (29 tools)</b></summary>

- Classic components (13): Button / Layout / ProgressBar / ScrollView / Toggle / EditBox / Slider / PageView / ToggleContainer / MotionStreak / ScrollBar / PageViewIndicator / WebView
- **UI pattern presets (6)**: `add_dialog_modal` / `add_main_menu` / `add_hud_bar` / `add_card_grid` / `add_toast` / `add_loading_spinner` — AI builds full UI blocks in one call
- **Responsive helpers (5)**: `make_fullscreen` / `anchor_to_edge` / `center_in_parent` / `stack_vertically` / `stack_horizontally` — skip the Widget bitmask pain
- **Text composition (1)**: `add_styled_text_block` — title + subtitle + divider + body
- **Rendering extras**: Camera / Mask / RichText / 9-slice Sprite / Tiled Sprite / Filled Sprite
</details>

<details>
<summary><b>Animation + Theming + UI Lint (11 tools)</b></summary>

- **Entrance animations (6)**: `add_fade_in` / `add_slide_in` / `add_scale_in` / `add_bounce_in` / `add_pulse` / `add_shake`
- **UI themes (4)**: `set_ui_theme` (5 built-ins: dark_game / light_minimal / neon_arcade / pastel_cozy / corporate) / `get_ui_tokens` / `list_builtin_themes` / `hex_to_rgba`
- **UI quality lint (1)**: `cocos_lint_ui` — 8 rules (touch target / text clipping / UI layer / WCAG contrast / button overlap / font-in-frame / buttons without Layout / nested Mask)
</details>

<details>
<summary><b>🔁 Playwright Closed-Loop Feedback (8 tools)</b></summary>

Lets the AI actually **play** the games it builds:

- `cocos_click_preview` / `cocos_press_key_preview` / `cocos_drag_preview`
- `cocos_fill_preview` (text input)
- `cocos_read_state_preview` (evaluate any JS expression, e.g. `window.game.score`)
- `cocos_wait_preview` / `cocos_run_preview_sequence` (sequence batching)
- `cocos_screenshot_preview_diff` (pure Pillow visual regression, no Playwright required)

Playwright is an **optional dependency** (~200MB chromium). When missing, tools return an install hint.
</details>

<details>
<summary><b>🎯 Game-Logic Scaffolds (9 tools)</b></summary>

Generate canonical `.ts` templates and return a compressed UUID ready to attach:

- `scaffold_input_abstraction` — unify WASD + arrow keys + touch into an `InputManager` singleton
- `scaffold_score_system` — current/best score + localStorage + auto-render Label
- `scaffold_player_controller` — **4 kinds**: platformer / topdown / flappy / click_only
- `scaffold_enemy_ai` — **3 kinds**: patrol / chase / shoot
- `scaffold_spawner` — **2 kinds**: timed / proximity-triggered
- `scaffold_game_loop` — menu / play / over state machine
- `scaffold_audio_controller` / `scaffold_camera_follow` / `scaffold_ui_screen`

All template fields use `@property` so they're Inspector-editable; numeric fields have `{ tooltip }` annotations.
</details>

<details>
<summary><b>Media / Skeletal / Particles / Tiled (14 tools)</b></summary>

- Media: AudioSource / Animation / ParticleSystem2D / VideoPlayer
- Skeletal: Spine + resource import / DragonBones + resource import
- TiledMap: TiledMap / TiledLayer / TMX resource import
- AI asset generation: `generate_asset` (CogView-3-Flash / Pollinations, SHA-256 cached) / `create_sprite_atlas`
- AnimationClip keyframe generator
</details>

<details>
<summary><b>Scene Tools + Prefabs + Batch Ops (12 tools)</b></summary>

- Prefabs: `create_prefab` / `instantiate_prefab` (with fileId uniquification) / **`save_subtree_as_prefab`**
- Scene: `validate_scene` / `audit_scene_modules` (components vs. engine module consistency) / `get_object` / `get_object_count` / `list_scene_nodes`
- **`batch_scene_ops`**: run multiple ops in one read/write; 27 op types; **measured 200 tool calls: 4293ms → 33ms (130×)**
- Scene globals: `set_ambient` / `set_skybox` / `set_shadows` / `set_fog` (LINEAR / EXP / EXP² / LAYERED)
</details>

<details>
<summary><b>🏭 Build + Publish + Post-Build Patches (11 tools)</b></summary>

- `cocos_build`: headless build for web-mobile / wechatgame / ios / android, with `source_maps` / `md5_cache` / `skip_compress_texture` / `inline_enum` / `mangle_properties`
- `cocos_start_preview` / `stop_preview` / `preview_status`
- **Post-build patches (4)**: `register_post_build_patch` / `list` / `remove` / `apply` — declarative `json_set` / `regex_sub` / `copy_from`, auto-applied after `cocos_build`, version-controlled
- Project settings: `set_native_build_config` (iOS/Android package/signing/orientation/icon) / `set_bundle_config` / `set_wechat_subpackages` (4MB main-package subpackaging)
- Engine modules: `get_engine_modules` / `set_engine_module` (toggle physics-2d-box2d / spine / video / …)
</details>

## 💡 Examples

Three one-command demos ship in-repo:

```bash
.venv/bin/python examples/flappy-bird/build_flappy.py /tmp/flappy --port 8080
.venv/bin/python examples/click-counter/build_click_counter.py /tmp/click --port 8081
.venv/bin/python examples/breakout/build_breakout.py
```

Open `http://localhost:8080` to play.

<details>
<summary><b>3D Rolling-Ball Demo (Python snippet)</b></summary>

```python
# 1. Init + enable 3D physics (default gravity = -10 m/s², not -320 px)
cocos_init_project("/tmp/roll3d")
cocos_set_physics_3d_config("/tmp/roll3d", gravity_y=-9.8)

# 2. A slippery physics material
ice = cocos_create_physics_material("/tmp/roll3d", "ice", friction=0.02, restitution=0.3)

# 3. Scene: Ball + Ground + directional light
scene = cocos_create_scene("/tmp/roll3d/assets/scenes/game.scene")
canvas = scene["canvas_node_id"]

sun = cocos_create_node(scene_path, canvas, "Sun")
cocos_add_directional_light(scene_path, sun, illuminance=65000, shadow_enabled=True)

ball = cocos_create_node(scene_path, canvas, "Ball", lpos=[0, 5, 0])
cocos_add_rigidbody_3d(scene_path, ball, body_type=1)      # DYNAMIC=1 (bitmask)
col = cocos_add_sphere_collider_3d(scene_path, ball, radius=0.5)
cocos_set_uuid_property(scene_path, col, "_material", ice["uuid"])

# 4. Fog + release build
cocos_set_fog(scene_path, enabled=True, fog_type=1, density=0.05)  # EXP
cocos_build("/tmp/roll3d", debug=False, md5_cache=True)
```

</details>

## 🏭 Commercial Release

<details>
<summary><b>iOS / Android native packaging</b></summary>

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
    android_app_bundle=True,   # produces .aab
)
```

</details>

<details>
<summary><b>Asset Bundle</b></summary>

```python
# Mark assets/levels/ as a Bundle; load at runtime with cc.assetManager.loadBundle('levels')
cocos_set_bundle_config(project, "assets/levels",
    compression_type={"web-mobile": "merge_dep", "wechatgame": "subpackage"})
```

</details>

<details>
<summary><b>WeChat mini-game subpackages (4MB main-package limit)</b></summary>

```python
cocos_set_wechat_subpackages(project, [
    {"name": "level1", "root": "assets/levels/world1"},
    {"name": "audio", "root": "assets/audio"},
])
```

</details>

<details>
<summary><b>Post-build patches — solve <code>build/</code> being regenerated each time</b></summary>

Cocos regenerates `build/<platform>/` on every build, so manual edits to `style.css` / `project.config.json` are wiped. Declare patches once and they auto-apply after every successful build:

```python
cocos_register_post_build_patch(project, patches=[
    # ① Precise JSON key override (fixes WeChat appid being reset)
    {"platform": "wechatgame", "file": "project.config.json",
     "kind": "json_set", "path": "appid", "value": "wx000000000000demo"},

    # ② Regex substitution
    {"platform": "web-mobile", "file": "style.css",
     "kind": "regex_sub",
     "find": r"background:\s*#[0-9a-fA-F]{3,6}",
     "replace": "background: #1c2833"},

    # ③ Full file override
    {"platform": "web-mobile", "file": "index.html",
     "kind": "copy_from", "source": "custom/index.html"},
])
```

**Safety valves**: regex pre-compile validation + path-injection defense (rejects `..` / absolute paths) + drift protection (regex no-match = hard error, not silent skip) + `dry_run=True` preview.

</details>

## ⚡ Performance Tuning

| Knob | Default | Effect |
|---|---|---|
| `cocos_batch_scene_ops` | — | Multiple ops per read/write cycle; **200 tool calls: 4293ms → 33ms (130×)** |
| Scene-read cache | on | LRU(8) keyed on abs-path + `st_mtime_ns`; external writes invalidate automatically |
| Creator-install cache | on | `list_creator_installs` uses `functools.lru_cache` — no rescans per session |
| `COCOS_CREATOR_PATH` | — | Pin a specific Creator install (highest priority; CI / Docker) |
| `COCOS_CREATOR_EXTRA_ROOTS` | — | Extra scan paths (POSIX `:` / Windows `;` separated) |
| `COCOS_MCP_SCENE_COMPACT=1` | off | Compact JSON writes (**500-object scene: -41% size**) |
| Pillow lazy-import | — | Tools that don't touch images don't need Pillow |

## 🎯 AI Friendliness & Reliability Guardrails

- **Structured errors** — `cocos_build` failures return `{error_code, hint}` across 9 types (`BUILD_TYPESCRIPT_ERROR` / `BUILD_MISSING_MODULE` / `BUILD_ASSET_NOT_FOUND` / `BUILD_TIMEOUT` / …)
- **Structured TS errors** — `BuildResult` carries `ts_errors: [{file, line, col, code, message}]` for direct Read+Edit
- **Scene pre-check** — `audit_scene_modules` scans components vs. `engine.json`, returns copy-pasteable `cocos_set_engine_module` command chains
- **Engine module map** — built-in `COMPONENT_REQUIRES_MODULE` (30+ mappings)
- **Script UUID idempotency** — `add_script` accepts 23 / 36 char UUIDs; re-adds preserve UUID
- **Post-build patches** — drift protection + first-fail stops chain
- **TypedDict contracts** — `BuildResult` / `ValidationResult` / `BatchOpsResult` etc. (8 total); schema drift is caught at test time

## 🐛 Troubleshooting

<details>
<summary><b>Cocos Creator install not found</b></summary>

Default scan: `/Applications/Cocos/Creator` (macOS) or `%LOCALAPPDATA%\Programs\CocosDashboard\resources\.editors` (Windows). For non-standard paths:

```bash
export COCOS_CREATOR_PATH=/custom/path/to/CocosCreator.app
# or extend the scan list
export COCOS_CREATOR_EXTRA_ROOTS=/opt/cocos:/shared/editors
```

</details>

<details>
<summary><b>Build timeout</b></summary>

First build re-imports all assets; may exceed the default 5-minute timeout. Pass explicit:

```python
cocos_build(project, timeout_sec=900)
```

</details>

<details>
<summary><b>Component doesn't work at runtime (but build succeeds)</b></summary>

Usually a required engine module is disabled. Run:

```python
cocos_audit_scene_modules(scene_path)
# → { ok: false, disabled: ["physics-2d"], actions: [...] }
```

Copy-paste the `actions` back as tool calls.

</details>

<details>
<summary><b>WeChat mini-game appid gets reset on every build</b></summary>

Creator overwrites `project.config.json`. Use a post-build patch:

```python
cocos_register_post_build_patch(project, patches=[
    {"platform": "wechatgame", "file": "project.config.json",
     "kind": "json_set", "path": "appid", "value": "wx000000000000demo"},
])
```

Version-controlled; survives machine migrations.

</details>

## 📊 Quality Assurance

- **741 pytest unit tests**, < 15s locally
- **GitHub Actions CI matrix**: Ubuntu / macOS / Windows × Python 3.11 / 3.12
- **`mypy cocos/` 0 errors**
- **`ruff check` 0 errors**
- 3D component field defaults **individually aligned to cocos-engine v3.8.6 source** (regression-locked)
- Cross-platform: external process calls go through `sys.executable` / socket / `tempfile.gettempdir()`

## 🔐 Security & Privacy

- All operations are **local file I/O**; no project code is ever uploaded
- `generate_asset` defaults to the CogView-3-Flash free API; swap to Pollinations or a local model if needed
- Playwright feedback only interacts with the **local preview server**
- No telemetry, no analytics

## 📂 Project Layout (abridged)

```
cocos-mcp/
├── server.py                 # MCP entry (60 lines FastMCP + tools.register_all)
├── run.sh / run.bat
├── cocos/
│   ├── tools/                # Thin MCP tool wrappers, 10 modules
│   ├── scene_builder/        # Scene JSON construction (physics / ui / ui_patterns / prefab …)
│   ├── project/              # Asset import / UI tokens / post-build patches
│   ├── scaffolds/            # 9 game-logic .ts templates
│   ├── build.py              # CLI build + cross-platform preview
│   ├── interact.py           # Playwright closed-loop feedback
│   ├── gen_asset.py          # AI image generation (CogView / Pollinations + cache)
│   ├── errors.py / types.py / uuid_util.py / meta_util.py
├── examples/                 # 3 one-command demos
├── tests/                    # 741 pytest
└── .github/workflows/test.yml
```

## 📄 License

**Proprietary · All Rights Reserved · Copyright © heitugongzuoshi**

Not to be copied, modified, redistributed, re-released, or used for any commercial purpose without prior written authorization.
Authorized only for invited collaborators for internal evaluation, trial, and development.

Pre-v1.1.0 releases were MIT-licensed (no longer distributed). The current repository (`1.2-dev`) is proprietary.

---

### Commercial licensing / partnership / custom development

📧 **2282059276@qq.com**

Services available:
- Commercial licensing (teams / companies)
- Custom development (bespoke tools / platform-specific adaptations)
- Technical consulting (Cocos 3.8 AI workflows / headless CI integration)
- Enterprise training (AI + game development workflows)

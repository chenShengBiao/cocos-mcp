# Changelog

All notable changes to **cocos-mcp** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Total: **109 tools** (was 80) · **166 tests** (was 45) · **72% coverage** (was 0%) · **0 mypy / ruff errors**.

### Added — 29 new tools across four feature passes

#### Publish-readiness (4 tools, 105 → 109)
- **`cocos_set_native_build_config(platform, …)`** — configures iOS / Android
  fields in `settings/v2/packages/builder.json`: package name, orientation
  (portrait/landscape/auto), icon/splash paths, iOS team ID, Android API
  levels, keystore signing config, and `.aab` toggle. Partial updates: pass
  `None` to leave a field unchanged across runs.
- **`cocos_set_bundle_config(folder_rel_path, …)`** — marks a folder as an
  Asset Bundle by patching its directory `.meta` sidecar with `isBundle /
  bundleName / priority / compressionType / isRemoteBundle`. Creates the
  meta if Cocos Creator hasn't seen the folder yet. Critical for any game
  past a few MB that needs lazy / per-level loading via
  `cc.assetManager.loadBundle()`.
- **`cocos_set_wechat_subpackages([{name, root}, …])`** — writes the
  `wechatgame.subpackages` array. WeChat hard-caps the main package at
  4 MB; without subpackages, any non-trivial game gets rejected at upload.
  Coexists with `cocos_set_wechat_appid`. Replaces the list atomically.
- **`cocos_add_video_player(node, …)`** — attaches `cc.VideoPlayer`. Two
  modes: `resource_type=1` + `clip_uuid` for local cc.VideoClip assets
  (cinematic intro), or `resource_type=0` + `remote_url` for streaming
  (rewarded video ads). Plus volume/mute/loop/fullscreen flags.

#### Cocos Creator coverage gaps (14 tools, 91 → 105)
- **`cocos_instantiate_prefab(scene, parent, prefab_path, name?, pos?, scale?)`**
  — the most-requested missing piece. Reads a .prefab, deep-clones its node
  tree into the target scene, shifts every internal `__id__`, refreshes
  `_id` strings + each `cc.PrefabInfo.fileId` so multiple instances don't
  alias, and parents the new root under `parent`. Treats the prefab as
  unlinked (one-shot copy; edits to the source .prefab don't propagate
  back into already-instantiated nodes).
- **`cocos_set_sprite_frame_border(meta_path, top, bottom, left, right)`** —
  configures 9-slice border in pixels on an existing sprite-frame meta.
  Idempotent. `cocos_add_image` and `new_sprite_frame_meta()` now also
  accept a `border` keyword argument. Required for any cc.Sprite type=SLICED
  (rounded UI buttons, panels, dialog frames).
- **9 × `cocos_add_*_joint2d`** — the full Box2D joint family:
  `add_distance_joint2d / add_hinge_joint2d / add_spring_joint2d /
  add_mouse_joint2d / add_slider_joint2d / add_wheel_joint2d /
  add_weld_joint2d / add_relative_joint2d / add_motor_joint2d`. Each
  takes `connected_body_id` (the OTHER body's RigidBody2D component id;
  `None` means anchor to world). Unlocks pendulum / vehicle / chain /
  rope / suspension / weld-and-shatter games.
- **3 × scene-globals setters**: `cocos_set_ambient` (sky/ground colors,
  illuminance), `cocos_set_skybox` (envmap UUID, HDR, lighting type),
  `cocos_set_shadows` (planar shadow plane + color). Each looks up the
  cc.AmbientInfo / SkyboxInfo / ShadowsInfo by `__type__` rather than
  hard-coded array index, so they keep working after arbitrary node edits.

#### Quality-of-life
- GitHub Actions CI matrix (Ubuntu / macOS / Windows × Python 3.11 / 3.12)
  running `ruff`, `mypy`, and `pytest`.
- Startup log line reporting the number of registered MCP tools so the
  actual count is verifiable without grepping source.
- `pyproject.toml` exposes a `[dev]` extras set (`pytest`, `ruff`, `mypy`)
  and is the single source of truth for dependencies.
- `CHANGELOG.md` (this file).

### Performance

- **`cocos_batch_scene_ops` extended from 15 → 27 op types**, adding
  `add_widget / add_camera / add_layout / add_progress_bar /
  add_audio_source / add_animation / add_mask / add_richtext` plus
  `set_scale / set_rotation / set_layer / set_uuid_property`. Real
  measurement on a 50-panel UI build: 200 sequential tool calls = **4293 ms**,
  same workload as one batch call = **33 ms** → **130× speedup**.
- **`COCOS_MCP_SCENE_COMPACT=1` env var** flips `json.dump(indent=2)` to
  `separators=(",", ":")`. Scene file size −41% (355 → 209 KB on the 500-
  object benchmark); per-write IO modestly faster too. Default off so
  human-edited scenes still git-diff cleanly.
- **`gen_asset.py` on-disk cache** keyed by SHA-256 of `(provider, model,
  prompt, size, seed)`. Cache lives at `tempfile.gettempdir()/cocos-mcp-gen/cache/`.
  Same prompt re-generated → cache hit, no API call. Bypass with `--no-cache`.
  Zhipu cache key omits seed (API doesn't honor it); Pollinations cache
  key includes it.

### Changed

- **`server.py` 1222 → 60 lines.** All 91 `@mcp.tool()` definitions moved
  into `cocos/tools/{core,scene,physics_ui,media,build}.py`; each module
  exposes a `register(mcp)` and the entrypoint just calls
  `tools.register_all(mcp)`.
- **`cocos/scene_builder.py` is now a package.** Private value/factory
  helpers and the property auto-wrap pair live in `_helpers.py`; the
  `batch_ops` mega-switch lives in `batch.py`. Public API is unchanged —
  `from cocos import scene_builder as sb; sb.add_uitransform(...)` still
  works.
- **`start_preview` / `stop_preview` rewritten cross-platform.**
  `python3` → `sys.executable`, `bash -c "lsof …"` → `socket.bind` probe,
  `os.setpgrp` / `os.killpg` → `subprocess.terminate()` (POSIX SIGTERM,
  Windows TerminateProcess). The Windows CI leg can now reach
  `cocos_start_preview` without `AttributeError`.
- **`cocos_clean_project` is now strict.** Unknown `level` argument used
  to silently fall back to `"default"` (clean build+temp), masking typos
  like `"lib"` meaning `"library"`. Now raises `ValueError`.
- **`init_project` returns `skipped_files: list[str]`** so callers know
  when the destination already had files that were left in place rather
  than overwritten.
- Build & preview log paths now use `tempfile.gettempdir()` instead of
  hard-coded `/tmp`, fixing Windows compatibility.
- `Pillow` is imported lazily inside `cocos/meta_util.py`, so non-image
  meta helpers work in slim environments without Pillow installed.
- `Dockerfile` installs via `pip install .` (reads `pyproject.toml`).

### Fixed

- **`cocos/project.py::generate_and_import_image`** was calling
  `os.environ` and `sys.executable` without ever importing `os` or `sys`,
  so the `cocos_generate_asset` MCP tool would `NameError` every time.
  Caught by the new ruff F821 check.
- **`cocos/uuid_util.py::decompress_uuid`** now chains the underlying
  `KeyError` via `raise … from e` for clearer tracebacks.
- **File-handle leak in `start_preview`** — `subprocess.Popen(stdout=open(…))`
  left the Python file object dangling; long-running MCP servers would
  accumulate FDs. Now `open()` → `Popen` → `close()` (subprocess dup'd it).
- **Loop variable shadow in `cli_build`** — `for f in build_dir.glob(...)`
  was clobbering the earlier `with open(log_path) as f:` binding, confusing
  static checkers (mypy reported `attr-defined`). Renamed loop var to
  `entry`.
- **Two missing docstrings** caught by the new tool-registration tests:
  `cocos_set_node_position` and `cocos_set_node_active`. AI clients pick
  tools by description, so empty descriptions silently degraded selection.
- **`.env` parser strips surrounding quotes.** `KEY="value"` and
  `KEY='value'` no longer leak the literal quote characters into HTTP
  Authorization headers (which used to cause silent 401 against Zhipu).
  Mismatched / unterminated quotes are preserved as-is.
- **Two `bare except: pass` blocks narrowed**: `cocos/build.py:167`
  cleaned up by the cross-platform preview rewrite; `cocos/project.py:210`
  (`_read_uuid`) narrowed to `(OSError, json.JSONDecodeError)` so
  programming bugs no longer get swallowed.
- **mypy 13 errors → 0**:
  - `get_project_info` returned `dict[str, Any]` but mypy inferred
    `dict[str, str]` from the first key (`{"project_path": str(p)}`)
    and rejected subsequent bool/None/list assignments.
  - `list_assets`, `_build_anim_json`, and `create_prefab`'s `objects = []`
    now have explicit `: list[<type>] = []` annotations.
  - `create_sprite_atlas / add_spine_data / add_dragonbones_data /
    add_tiled_map_asset` widened `list[str | Path]` parameters to
    `Sequence[str | Path]` (covariant) so MCP-tool wrappers passing
    `list[str]` no longer error.

### Removed

- `requirements.txt` (superseded by `pyproject.toml`).

### Tests

Test count: **45 → 166 (+121)**. Coverage: **45% → 72% (+27)**.

| File | Tests | Covers |
|---|---|---|
| `test_uuid.py` | 5 | UUID compression round-trip, error paths |
| `test_meta.py` | 6 | script / scene / prefab / sprite-frame meta |
| `test_scene_builder.py` | 33 | scene CRUD, validate, batch, components |
| `test_project.py` | 11 | `add_script / add_image / list_assets / find_creator` |
| `test_build.py` | 13 | mocked `cli_build`, settings JSON, strict `clean_project` |
| `test_perf_optimizations.py` | 11 | compact mode, batch ops, gen_asset cache, .env quotes |
| `test_new_features.py` | 23 | 9-slice, lighting setters, 9 joints, prefab instantiation |
| `test_publish_features.py` | 15 | native build config, bundle config, wechat subpackages, video player |
| `test_tools_registration.py` | 11 | `register_all` smoke + wrapper round-trips through tool manager |
| `test_make_transparent.py` | 6 | chroma key on synthetic 3-region PNG, low/high ramp, feather |
| `test_gen_asset.py` | 12 | URL build, size snap, watermark removal, mocked HTTP for both providers |
| `test_project_assets.py` | 20 | audio / resource / animation clip / atlas / Spine / DragonBones / TiledMap / mocked `generate_and_import_image` |

CI runs the whole suite under Ubuntu / macOS / Windows × Python 3.11 / 3.12.

### Future work (not done in this PR)

- `cocos/scene_builder/__init__.py` is still ~1330 lines. The next
  refactor pass should carve out `scene.py` (create_empty_scene /
  create_prefab / validate_scene), `nodes.py`, `components.py`,
  `physics.py`, `ui.py`, and `media.py` — leaving `__init__.py` as a
  thin re-export shim. The `_helpers.py` + `batch.py` split lays the
  groundwork.
- 3D primitives: `cc.DirectionalLight / PointLight / SpotLight`,
  `cc.MeshRenderer`, 3D physics (`cc.RigidBody` + 6 colliders),
  `cc.PostProcess` (Bloom / HBAO / ColorGrading). Most are reachable
  today via the generic `cocos_add_component` but lack friendly wrappers.
- `cocos/build.py::start_preview` covered at 66% — needs a socket-mock
  test to exercise the "port already bound" branch.

## [1.1.0] — "detail pass"

### Added
- 2D physics configuration tool (`cocos_set_physics_2d_config`).
- UI components: `PageView`, `ToggleContainer`, `MotionStreak` — bumps
  tool count to ~90.
- `install.sh` one-liner installer targeting `~/.claude/mcp-servers/cocos-mcp`.

### Fixed
- `cocos_validate_scene` gained 3 extra runtime-safety checks that
  previously surfaced only after CLI build.
- `ProgressBar.barSprite` is now serialized as a proper `{__id__: N}`
  reference instead of a bare integer.
- Several interactive-component event bindings now round-trip through
  the editor correctly.
- `Label` overflow / wrap / outline parameters and complete enum
  constants table are documented in `cocos_constants`.

## [1.0.2]

### Added
- `cocos_generate_asset` — built-in AI image generation via 智谱
  CogView-3-Flash (free in CN) or Pollinations Flux.
- `cocos_create_sprite_atlas` — packs multiple PNGs into a single
  SpriteAtlas asset.

### Fixed
- `cocos_attach_script` no longer auto-wraps raw integer property values
  as `__id__` references (broke numeric `@property` fields).
- UI render components (Sprite, Label, Graphics…) now auto-attach a
  matching `UITransform` if the target node lacks one.

## [1.0.1]

### Added
- `FilledSprite` / `SlicedSprite` / `TiledSprite` component tools.
- `cocos_add_image(as_resource=True)` to drop PNGs under
  `assets/resources/` for runtime `resources.load()`.

## [1.0.0] — initial release

- Headless Cocos Creator 3.8 MCP server.
- UUID compression (standard ↔ 23-char base64 short form).
- Project init from built-in templates, asset import, scene/prefab
  JSON generation, headless CLI build, and local HTTP preview.
- ~80 MCP tools covering nodes, UI, physics, media, animation, tilemap,
  Spine / DragonBones, and build/publish.

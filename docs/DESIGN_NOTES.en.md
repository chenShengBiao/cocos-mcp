# Design Notes

[🇨🇳 中文](./DESIGN_NOTES.md)

> **This file used to be `CHANGELOG.md`.** Moved here in v1.2-dev: release
> notes live in [Gitee Releases](https://gitee.com/csbcsb/cocos-mcp/releases)
> going forward. What stays here is the **engineering rationale** — dogfood
> findings, Cocos 3.8 field-drift fixes, Bug A/B regression context,
> architecture decisions — things that don't fit in release notes or `git log`
> one-liners but are worth preserving when future-you asks "why is this field
> `1` not `0`?".
>
> **The Chinese version ([DESIGN_NOTES.md](./DESIGN_NOTES.md)) is the primary
> design reference, organized by topic.** This English file is the historical
> per-release changelog, preserved verbatim and no longer actively maintained.

---

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Total: **184 tools** (was 80) · **741 tests** (was 45) · **0 mypy / ruff errors**.

### Fixed — batch_ops param parity with direct sb.* API (dogfood v2 follow-up)

End-to-end dogfood of Flappy Bird (Cocos Creator 3.8.6 headless
build + Chromium runtime) confirmed every physics / UI / atlas /
prefab fix — but uncovered one lingering friction: ``batch_ops``'s
``add_node`` / ``set_position`` / ``set_scale`` took different
parameter names than the direct ``sb.add_node`` / ``set_node_*``
functions. Agents familiar with the direct API handed over
``lpos=(x, y, z)`` / ``lscale=(sx, sy, sz)`` tuples and silently got
(0, 0, 0) positioning + (1, 1, 1) scale regardless of op input.

Worse: the batch ``add_node`` never read ``lscale`` at all (neither
tuple nor scalars), so **every batch-created node came out at the
engine default scale** — a latent bug unrelated to the naming
mismatch. Before this fix, there was no way to set initial scale via
``batch_ops``; only ``set_scale`` as a separate op worked.

Fix: three small helpers (``_resolve_lpos`` / ``_resolve_lscale`` /
``_resolve_xyz``) accept EITHER form. Tuple wins when both present;
``lpos=[x, y]`` (2D shorthand) defaults z to 0. The legacy scalar
form still works identically — no breaking changes for callers that
were already using the batch shape. Applies to:

* ``add_node`` — ``lpos=[x,y,z]`` / ``lscale=[sx,sy,sz]`` tuples +
  new ``lscale`` scalar support (sx/sy/sz were previously dropped
  silently).
* ``set_position`` — ``lpos=[x,y,z]`` in addition to ``x/y/z``.
* ``set_scale`` — ``lscale=[sx,sy,sz]`` in addition to ``sx/sy/sz``.

**Tests — 734 → 741 (+7)**

* ``test_add_node_accepts_lpos_tuple_matching_direct_api``
* ``test_add_node_accepts_lscale_tuple`` (catches the silent-drop bug)
* ``test_add_node_legacy_scalars_still_work`` (backward-compat)
* ``test_add_node_lpos_tuple_wins_over_scalars`` (deterministic precedence)
* ``test_add_node_lpos_short_tuple_defaults_z_to_zero`` (2D shorthand)
* ``test_set_position_accepts_lpos_tuple``
* ``test_set_scale_accepts_lscale_tuple``

### Fixed — AutoAtlas .pac shape + added runtime DynamicAtlas helper (183 → 184 tools)

`cocos_create_sprite_atlas` produced files that Cocos 3.8's
auto-atlas importer silently rejected, so the build emitted a
`SpriteAtlas` marker but no packed texture. The scene still
referenced the raw PNGs individually — heavy UI screens saw
no draw-call reduction. Found during a post-fix sweep of
Cocos 3.8 asset serialization. All bugs now regression-guarded.

**Real bugs fixed:**

* `.pac` body had packing config (maxWidth / padding / algorithm / …)
  in-line; in 3.8 the body is a single-line marker
  `{"__type__": "cc.SpriteAtlas"}` and **all config lives in
  `.pac.meta` `userData`**. Extra body fields don't break parsing
  but don't take effect — they were silently discarded.
* Meta used `"ver": "1.0.7"` — 3.8 expects `"1.0.8"`, and the
  importer's version gate silently rejects anything else.
* Meta `userData` was empty (`{}`). 3.8 expects 17 keys including
  `removeTextureInBundle`, `removeImageInBundle`,
  `removeSpriteAtlasInBundle`, `compressSettings`, `textureSetting`
  (nested: `wrapModeS` / `minfilter` / etc.) — without these the
  importer falls back to "do nothing" defaults.
* Algorithm string was `"MaxRect"`; correct 3.8 name is
  `"MaxRects"` (plural). Mis-named algorithm → importer ignores.
* Defaults were wrong: `maxWidth`/`maxHeight` 2048 (3.8 default
  1024), `powerOfTwo` true (3.8 default false), `filterUnused`
  false (3.8 default true).
* `png_paths` was required, which contradicts AutoAtlas's core
  "scan-folder-on-build" mechanic. Now optional; callers can drop
  PNGs into `atlas_dir_rel` (returned in response) at any time
  and the build picks them up.

**`cocos_enable_dynamic_atlas`** (new, runtime packing):

  Cocos 3.8 ships a separate runtime batching system
  (`dynamicAtlasManager.enabled = true`) that blits small sprite
  frames into shared GPU textures at draw time. Turning it on
  typically saves 3-10× draw calls on heavy UI screens — frames
  too new or too dynamic for AutoAtlas still benefit. The flag is
  a one-liner in a boot script; this tool generates the script +
  hands back both UUIDs so the caller can immediately attach::

    r = cocos_enable_dynamic_atlas(project, max_frame_size=512)
    cocos_add_script(scene, gm_node, r["uuid_compressed"])

  Script is idempotent on re-generation (Bug A fix applies here
  too — preserves UUID on rewrite, so already-attached components
  keep resolving).

**Tests — 728 → 734 (+6)**

* `test_create_sprite_atlas_without_png_paths_still_valid` —
  creating an empty atlas folder must produce a valid importable
  `.pac` + meta pair; further PNGs dropped in later are picked up
  by build automatically.
* `test_create_sprite_atlas_meta_has_complete_userData` — lock-in
  on `ver: 1.0.8` + all 17 required userData fields + nested
  `textureSetting`. Regression guard.
* `test_create_sprite_atlas_tunables_override_defaults` — caller
  kwargs (max_width, padding, algorithm, quality, …) reach the
  `userData` block.
* `test_enable_dynamic_atlas_writes_script_with_flag` — generated
  `.ts` actually contains `dynamicAtlasManager.enabled = true`.
* `test_enable_dynamic_atlas_custom_max_frame_size` — `maxFrameSize`
  constant lands in the source.
* `test_enable_dynamic_atlas_preserves_uuid_on_rewrite` — idempotent
  UUID on regenerate (Bug A guarantee).

### Added — Batch-op extensions + 2 composites + introspection (180 → 183 tools)

Second pass on dogfood recommendations, focused on the "still 3-6 calls
per composite action" complaint agents had even post-Bug-A/B. Details:

- **`cocos_batch_scene_ops` gains 9 new op kinds**:
  - ``add_polygon_collider2d`` — vertex-list collider for non-rect shapes.
  - All eight ``cc.*Joint2D`` variants (distance / hinge / spring / mouse
    / slider / wheel / fixed / relative). Dogfood's 10-individual-call
    rigidbody-collider-joint trio now folds into one batch. Every joint
    supports the full param surface the direct tools accept.
  - ``attach_script`` inside batch auto-compresses 36-char standard UUIDs
    to match the direct ``scene_builder.add_script`` behavior — closes
    a silent-no-op trap (previously a standard UUID as ``__type__``
    produced an unresolved component).
- **Name-addressable batch results**: an op can set ``"name": "bird"``
  and later ops reference it as ``"$bird"`` instead of ``"$0"``.
  Resolution is name-first in a ``named_results: dict`` on the
  response; positional ``$N`` still works unchanged. Unknown ``$name``
  falls through as a literal so the downstream op errors clearly
  rather than silently substituting the wrong id.
- **``cocos_add_physics_body2d``** (composite): RigidBody2D + a shape
  collider (box / circle / polygon) in one call. Returns
  ``{rigidbody_id, collider_id, shape}``. Every Bird / Pipe / Ground
  / Enemy in the dogfood ran this 2-call sequence — now it's one.
  Unknown ``shape`` raises rather than silently defaulting.
- **``cocos_add_button_with_label``** (composite): creates the canonical
  ``Btn (Node + UITransform + optional Sprite + Button) → Label (Node
  + UITransform + Label)`` subtree in one call. Every menu button in
  the dogfood ran 7 separate calls for this; now it's one. Accepts
  design-token presets, optional sprite-frame background, and
  ``click_events`` forwarded to ``add_button`` verbatim.
- **``cocos_list_tools``** (introspection): returns the actual tool
  surface the server registered. Solves the "stale MCP catalog"
  issue the dogfood run hit (Bug C in the report) — subagents'
  deferred-tool search occasionally couldn't see tools added after
  their session started. Supports ``name_contains`` substring and
  ``category`` bucket filters (heuristic mapping over 16 buckets:
  ``uuid`` / ``project`` / ``asset`` / ``scene`` / ``physics2d`` /
  ``physics3d`` / ``rendering`` / ``ui`` / ``media`` / ``build`` /
  ``interact`` / ``scaffold`` / ``composite`` / ``meta``). Zero
  tools fall into ``"other"`` — that's tested as a regression guard
  so new tools without a rule get surfaced.

### Fixed — Dogfood-Flappy HIGH-ROI bugs (Bug A + Bug B)

The first full dogfood run (building a Flappy Bird, report at
``docs/dogfood-flappy-report.md``) surfaced two silent-corruption bugs
in the most-used tools. Both are now fixed with regression tests.

- **Bug A — ``cocos_add_script`` reassigned UUID on overwrite.**
  Rewriting a .ts file (a high-frequency operation — agents edit a
  field and re-save) silently minted a new UUID, which rewrote the
  ``.ts.meta`` sidecar. Every scene that already referenced that
  script by its compressed UUID immediately became a no-op component
  at runtime. The fix: when no explicit ``uuid=`` is passed and a
  ``.ts.meta`` already exists, preserve its UUID and only update the
  source. Callers that genuinely want to fork the asset still pass
  ``uuid=<new>`` explicitly. Return value gains a ``created: bool``
  field to signal whether the UUID was freshly minted or preserved.
  Corrupt-meta recovery stays automatic — unreadable JSON falls back
  to a fresh mint so a partial-write can't permanently poison the
  asset. (``cocos/project/assets.py::add_script``.)

- **Bug B — ``add_node`` on a ``.prefab`` file skipped PrefabInfo for
  children.** A prefab requires every node to have its own
  ``cc.PrefabInfo`` entry with a unique ``fileId`` — Creator uses those
  ids to reconcile per-instance overrides. The previous code left
  child nodes with ``_prefab: null`` (the default ``_make_node``
  shape, correct for scene nodes, malformed inside a prefab). Result:
  the prefab would either refuse to instantiate or silently lose
  overrides depending on engine version. Fix detects ``.prefab``
  suffix and auto-appends a fresh PrefabInfo per node. Covers
  ``add_node``, ``batch_ops.add_node``, ``duplicate_node``, and the
  post-fix path of ``save_subtree_as_prefab`` (which previously only
  emitted a single PrefabInfo for the root).

### Added — ``cocos_add_and_attach_script`` composite (179 → 180 tools)

Single-call wrapper for the 3-step dance agents ran on every script
attach (write file → compress UUID → attach to scene node):

```
r = cocos_add_and_attach_script(project, "Bird", source,
                                 scene, bird_node_id, props=...)
# r["component_id"], r["uuid_compressed"], r["uuid_standard"], r["created"]
```

The two same-named ``cocos_add_script`` tools (project-level file
writer vs scene-level component attacher) were the biggest trip-
hazard in the dogfood — agents occasionally passed the standard UUID
to the scene attacher and got a silently-broken component. This
composite names the intent and returns both forms of the UUID so the
caller never has to re-derive the compressed one. (``cocos/composites.py``,
exposed as MCP tool in ``cocos/tools/composites.py``.)

### Added — Gameplay scaffolds (171 → 175 tools)

Before this pass, cocos-mcp did nothing to help with the *behavioural*
layer — every game AI built from scratch re-wrote the same input
singleton, score tracker, player controller, etc. in raw .ts. Six
scaffold tools now generate canonical starter scripts + hand back
both UUID forms so the next call is a plain ``cocos_add_script``
attach:

- ``cocos_scaffold_input_abstraction`` — InputManager.ts singleton
  (WASD + arrows, diagonal-normalized moveDir, SPACE jumpPressed,
  J / any-touch firePressed; one-frame triggers reset in lateUpdate).
- ``cocos_scaffold_score_system`` — GameScore.ts singleton
  (add/reset/current/high + localStorage persistence under
  'cocos-mcp-high-score', with swallowed write failures for private
  browsing / WeChat mini-game; optional @property scoreLabel +
  highLabel auto-render).
- ``cocos_scaffold_player_controller(kind)`` — 4 variants:
  *platformer* (RigidBody2D + gravity, moveSpeed/jumpForce/
  doubleJumpEnabled, ground-detection via velocity threshold);
  *topdown* (no gravity, full moveDir);
  *flappy* (single jump impulse on jumpPressed);
  *click_only* (no physics body — tweens _lpos toward click; the
  only variant that doesn't depend on InputManager).
- ``cocos_scaffold_enemy_ai(kind)`` — 3 variants:
  *patrol* (oscillate between @property patrolA↔patrolB, flip
  optional mirrorSprite); *chase* (Vec3.distance with
  chaseRadius/loseAggroRadius hysteresis, kinematic setPosition);
  *shoot* (stationary turret, fireInterval cooldown, instantiate
  bulletPrefab toward target).
- ``cocos_scaffold_spawner(kind)`` — 2 variants: *time*
  (interval + spawnBoxSize jitter + despawn-oldest queue at
  maxActive); *proximity* (triggerRadius on @property player +
  cooldown). Both parent spawned nodes under ``this.node.parent``
  (explicitly not the spawner itself) + invoke optional @property
  onSpawn(spawned) post-addChild.
- ``cocos_scaffold_game_loop(states)`` — singleton state machine,
  default states=[menu, play, over]. Each state generates paired
  @property onEnter<PascalCase> + onExit<PascalCase> callbacks
  (so ``"game_over"`` becomes onEnterGameOver). Validates state
  names are identifier-safe + unique at scaffold time so a broken
  .ts never lands.

All scaffolds: 15 kind combinations × ~50-100 LOC TS each,
embedded inline as Python triple-strings. Each template is
hand-tuned for production quality (null-checks singletons, guards
optional refs, uses hysteresis for ranges). Every @property is
inspector-visible so designers tune numbers without code changes.

### Added — Closed feedback loop (161 → 171 tools)

``cocos_screenshot_preview`` lets the AI *see* its game; this
batch adds the other half — *interact* + *read state*. The AI can
now play-test what it built instead of building blind.

- ``cocos_click_preview(url, x, y, button)`` — Playwright mouse
  click at page coords.
- ``cocos_press_key_preview(url, key)`` — Cocos KeyCode event
  fires normally (``"Space"`` / ``"ArrowUp"`` / ``"a"`` / etc).
- ``cocos_type_preview(url, text)`` — keyboard.type for text
  fields.
- ``cocos_drag_preview(url, from_xy, to_xy, steps)`` — mouse
  move+down + ``steps`` interpolated moves + up, so Cocos drag-
  detection fires (a raw A→B jump wouldn't).
- ``cocos_read_preview_state(url, expression)`` — page.evaluate,
  returns ``{ok, value, error}``; guarded so arbitrary user JS
  can't crash the tool. Designed for games that expose
  ``window.game`` in their GameManager.onLoad.
- ``cocos_wait_for_preview(url, ms)`` — let async loads settle.
- ``cocos_run_preview_sequence(url, actions)`` — ordered list of
  click/key/type/drag/wait/read_state/screenshot actions in ONE
  browser session (game state doesn't survive a reload). Per-
  action failure doesn't short-circuit so earlier reads survive
  a later bad click. Screenshot bytes come back hex-encoded for
  JSON-safe MCP transport.
- ``cocos_screenshot_preview_diff(before_png, after_png, threshold)``
  — pure Pillow (no Playwright needed). Per-channel absolute-delta
  threshold avoids flagging JPEG-like compression noise as
  change. Returns
  ``{width, height, total_pixels, different_pixels, diff_ratio}``.

Same install-hint pattern as ``cocos_screenshot_preview``: missing
playwright → ImportError with ``uv pip install playwright`` +
``playwright install chromium``; missing chromium binary →
RuntimeError with the install-step hint.

### Added — Prefab subtree extraction (160 → 161 tools)

Biggest existing prefab gap: the AI could create an empty prefab
or instantiate one, but had no way to take an already-configured
scene subtree (Enemy with Sprite + RigidBody + Collider +
Animation + script all wired) and *export* it as a reusable
prefab. Without this, "spawn ten enemies" was re-running the
whole add_* stack ten times.

- ``cocos_save_subtree_as_prefab(scene_path, root_node_id,
  prefab_path, prefab_uuid?)`` — walks the subtree, transitively
  collects every descendant cc.Node + component + inline helper
  (cc.ClickEvent under Button, cc.EventHandler under Toggle).
  Builds an old→new index map, deep-copies, rewrites ``__id__``
  refs, mints fresh ``_id`` strings, wires cc.Prefab + cc.PrefabInfo
  + writes the .prefab + meta.
- Self-contained enforcement: any ``__id__`` pointing at a cc.Node
  OUTSIDE the subtree raises ValueError naming the offender and
  the component context. Cocos's prefab format can't represent
  late-bound cross-scene refs; silent clipping would produce a
  .prefab that crashes at instantiation. Atomic on failure (no
  partial file written).
- Asset ``__uuid__`` refs (SpriteFrame, clip, mesh, nested prefab)
  survive unchanged — they travel via the asset DB.
- Source scene is NEVER mutated. If the caller wants to replace
  the raw subtree with a prefab instance, do an explicit
  ``cocos_delete_node`` + ``cocos_instantiate_prefab`` — the
  two-step is deliberate so a misfired call can't lose the source.

Hidden-capability documentation: prefab files share the JSON-
array shape of scenes, so every ``scene_builder`` mutation tool
(add_sprite / add_button / batch_scene_ops / etc) works directly
on a .prefab path. A regression-guard test pins this behaviour.

### Added — UI/UX pass: design tokens + lint + presets + animations (135 → 160 tools)

Six commits landed an entire design-system layer so AI-built UI
stops looking "AI-random". Summary of what shipped:

**Design tokens + theme swap** (``cocos_set_ui_theme`` +
``cocos_get_ui_tokens`` + ``cocos_list_builtin_themes`` +
``cocos_hex_to_rgba``):

- 5 built-in themes: dark_game / light_minimal / neon_arcade /
  pastel_cozy / corporate. Each ships the full preset vocabulary
  (10 colors × 4 font sizes × 5 spacings × 4 radii).
- ``cocos_add_label`` / ``add_button`` / ``add_sprite`` /
  ``add_richtext`` gained ``color_preset`` / ``size_preset`` /
  ``outline_color_preset`` kwargs. ``color_preset="primary"`` on
  a button AUTO-DERIVES matching hover / pressed / disabled via
  luminance-aware shading — one preset replaces four hand-picked
  RGBA quadruples.
- Fallback: un-themed projects resolve presets against dark_game
  default so no lookup ever 404s.
- Custom themes via ``custom={...}`` merge atop dark_game so
  partial overrides still resolve every preset name.

**UI composites**:

- ``cocos_add_dialog_modal`` / ``add_main_menu`` / ``add_hud_bar``
  (first batch) — full-screen dialog with buttons, vertical menu
  with title + buttons, horizontal HUD row.
- ``cocos_add_toast`` / ``add_loading_spinner`` / ``derive_theme``
  — ephemeral notification, centered spinner with Animation
  component driving rotation, helper to generate a custom theme
  from a seed color.
- ``cocos_add_card_grid`` — level select / shop / character
  picker grid. variant="primary" cards auto-flip text color for
  contrast.
- ``cocos_add_styled_text_block`` — title + subtitle + divider +
  body paragraph stacked; resolves sizes + colors from tokens;
  body uses wrap + overflow=RESIZE_HEIGHT so long paragraphs
  grow the block instead of clipping.

**Responsive helpers** (``cocos_make_fullscreen`` /
``cocos_anchor_to_edge`` / ``cocos_center_in_parent`` /
``cocos_stack_vertically`` / ``cocos_stack_horizontally``):

Collapse the Widget ``align_flags`` bitmask + Layout
``layoutType`` + ``resizeMode`` + ``h_direction`` trio into five
verbs. ``stack_*`` accept a token name (``"md"``) OR raw int for
spacing/padding.

**Animation presets** (``cocos_add_fade_in`` / ``add_slide_in`` /
``add_scale_in`` / ``add_bounce_in`` / ``add_pulse`` /
``add_shake``):

Six entrance / feedback animations. ``add_shake`` oscillates
around the node's CURRENT ``_lpos``, not around origin (the
common bug that flings the node across the screen). Fixed a
latent wrap_mode bug in ``create_animation_clip``: was
hardcoded to 2 (WrapMode.Reverse — plays the clip once
backwards!); now parameterized with default 1 (Normal, play
once forward). Regression test locks all five enum values.

**UI lint** (``cocos_lint_ui``) — 8 rules:

- button_touch_target (<44×44 — iOS HIG / Material 48dp)
- label_overflow_risk (overflow=NONE + no-wrap + long text in
  narrow box)
- ui_layer_mismatch (UI component on a non-UI_2D layer —
  UICamera won't render it)
- contrast_too_low (WCAG AA threshold per text-size tier — 3:1
  for large, 4.5:1 for body. Nearest background resolves via
  cc.Button._N$normalColor preferred, otherwise ancestor
  cc.Sprite. 12-level ancestor walk.)
- overlapping_buttons (same-parent, >25% of smaller's area —
  skips cc.Layout-managed parents since Layout repositions at
  runtime)
- huge_font_small_box (UITransform.height < font_size × 1.2)
- many_buttons_no_layout (≥6 button siblings without cc.Layout
  — manual positioning at this scale drifts across resolutions.
  cc.Layout type=NONE counts as "I manage my own layout" so
  card_grid's self-positioned cards don't trip.)
- nested_mask_perf (cc.Mask inside another Mask — each stencil
  pass doubles).

Lint caught two real bugs in our own composites during
development (main_menu title box ratio, card_grid's hand-
positioned cells); both fixed in the same commits.

### Added — Post-build patch registry (131 → 135 tools)

Cocos regenerates ``build/<platform>/`` from scratch every build, so
manual edits to files with no Cocos source-config switch (style.css
body bg, ``project.config.json`` fields beyond builder.json's surface,
custom index.html) get wiped on every rebuild. This commit introduces
a declarative patch registry at
``settings/v2/packages/post-build-patches.json`` + auto-apply inside
``cli_build``.

**Three patch kinds** (in ``cocos/project/post_build_patches.py``):

- ``json_set`` — dotted-path navigation, creates missing intermediate
  dicts, refuses to descend into a non-dict (which would silently
  corrupt user data).
- ``regex_sub`` — ``re.sub`` with ``count=1``. Must match at least once
  at apply time; a drifted pattern after a Cocos bump becomes an
  explicit ``errors[0]`` entry rather than a silent regression.
- ``copy_from`` — whole-file copy from a project-root-relative source
  over the build target.

**Four new MCP tools**:

- ``cocos_register_post_build_patch(patches, mode='append'|'replace')``
  — batched registration is atomic: one invalid patch in the list
  fails the whole call and the registry file stays untouched.
- ``cocos_list_post_build_patches`` — returns patches with indices for
  later selective removal.
- ``cocos_remove_post_build_patches(indices|platform|file)`` —
  precedence: indices > platform+file AND filter. Calling with all
  None is a no-op (explicit wipe requires ``register([], mode='replace')``
  — forces the user to think twice about clearing the whole list).
- ``cocos_apply_post_build_patches(platform, dry_run=False)`` —
  normally ``cli_build`` runs this automatically on success; exposed
  for dry-run preview and re-apply-without-rebuild.

**Validation hardening** (at register time, not apply time — the right
moment is when the author writes the patch):

- ``kind`` in the supported set
- ``file`` relative path, no ``..`` segments (path-injection guard)
- ``copy_from`` source similarly constrained
- ``regex_sub.find`` must compile
- ``json_set.path`` non-empty; ``value`` must be present

**cli_build integration**:

- New ``apply_patches: bool = True`` param.
- After ``success==True``, walks the registry for matching-platform
  patches and applies them in order, **stopping on first error** so
  patch failures can't cascade across files.
- Result carries ``post_build_patches: {platform, dry_run, build_dir,
  applied, skipped, errors, ok}``.
- When the build itself passed but patches broke, ``success`` flips to
  False and ``error_code`` is **``POST_BUILD_PATCH_FAILED``** with a
  hint that points at ``cocos_list_post_build_patches`` — the caller
  isn't sent to grep the Cocos log for a nonexistent problem.

**Tests (+24, tests/test_post_build_patches.py)**:

- Register: append vs replace, atomic-fail-on-bad-batch, rejects
  absolute paths / ``..`` / unknown kinds
- Remove: platform filter, index list, no-op-when-no-filter (safety)
- json_set: simple, creates intermediates, refuses non-dict traversal
- regex_sub: replaces, errors when pattern doesn't match
- copy_from: overwrites target, errors if source missing
- Apply: filters by platform, skips missing files (no raise), dry_run
  doesn't touch fs, stops on first error (no cascade)
- cli_build: auto-apply on success, ``apply_patches=False`` skips,
  patch failure surfaces ``POST_BUILD_PATCH_FAILED``, no-patches-
  registered still emits a consistent (empty) report shape

### Added — Friction-reducer pass (130 → 131 tools)

Four targeted fixes for the top "AI client gets stuck" failure modes.
None add components; all reduce the number of round-trips between the
orchestrating LLM and the tools when something doesn't work first try.

**Creator path discovery** (``cocos/project/installs.py``):

The hardcoded ``INSTALL_ROOTS`` misses common setups (symlinked
locations, ``~/Applications`` on macOS, ``D:\`` drives). Added three
precedence-ordered escape hatches:

1. ``COCOS_CREATOR_PATH`` env var — pins a single install.
2. ``COCOS_CREATOR_EXTRA_ROOTS`` env var — ``:``/``;`` separated
   additional scan roots.
3. ``$PATH`` probe — ``shutil.which("CocosCreator")`` then back-walk
   to the install root.

``find_creator``'s "no install" error now lists all four escape hatches
(download + three env/PATH options). A bad ``COCOS_CREATOR_PATH`` falls
through to auto-discovery rather than silently swallowing the error.

**TS error structured parsing** (``cocos/errors.py``, ``cocos/build.py``):

``classify_build_log`` already routes TS compile failures to
``BUILD_TYPESCRIPT_ERROR``. Added ``parse_ts_errors()`` that extracts
per-diagnostic ``{file, line, col, code, message}`` tuples from the
``tsc``-format output in the log tail. When ``cli_build`` classifies
the failure as TS, it attaches ``ts_errors: list[dict]`` to
``BuildResult`` so the AI can Read+Edit each offending file directly
instead of re-parsing the log.

**Script UUID auto-compress** (``cocos/scene_builder/__init__.py``):

``add_script`` previously required the 23-char compressed UUID form
(what the engine resolves at runtime). Callers often copy-pasted the
36-char standard form from ``cocos_list_assets`` / ``.ts.meta`` —
scene saved fine, build succeeded, component became a silent no-op
because the engine couldn't resolve the class. Now auto-compresses
any 36-char dashed UUID before writing. Zero-risk change since the
36-char path was already a silent bug.

**Engine-module audit** (``cocos/scene_builder/modules.py`` +
``cocos_audit_scene_modules``):

Single biggest runtime-failure mode: attaching a component whose
engine module is off in ``settings/v2/packages/engine.json``. Build
artifacts are structurally fine, the scene loads, but the component
class doesn't register and the feature silently does nothing.

New tool cross-checks scene ``__type__``s against a 30+ entry
``COMPONENT_REQUIRES_MODULE`` map vs. the project's ``engine.json``.
Returns ``{ok, required, enabled, disabled, actions}`` where
``actions`` is copy-pasteable ``cocos_set_engine_module`` + library
clean commands. ``physics-2d-box2d`` / ``physics-2d-builtin``
satisfies the ``physics-2d`` requirement (matches Cocos inspector
semantics). Walks up from ``scene_path`` to find ``package.json`` when
``project_path`` is None; raises explicitly if unfindable.

``cc.Camera`` intentionally NOT in the map — every UI scene created
via ``create_empty_scene`` attaches one and 2D builds work fine
without base-3d. Only the genuinely 3D-exclusive renderers
(MeshRenderer, DirectionalLight/SphereLight/SpotLight) require base-3d.

**Tests (+16, tests/test_friction_reducers.py)**:

- Creator path: ``COCOS_CREATOR_PATH`` pin / bad-pin fallback /
  ``COCOS_CREATOR_EXTRA_ROOTS`` / PATH probe / error lists 4 hatches
- TS errors: regex extraction / empty inputs / cli_build integration
- UUID compress: 36→23 round-trip + 23-char no-op
- Module audit: RigidBody2D flagged when physics-2d off /
  ``physics-2d-box2d`` satisfies physics-2d / plain UI scene ok /
  multiple missing flagged / walks up to find project / raises on
  unfindable project

### Added — 3D parity pass (108 → 130 tools)

Grew the scene-building surface from "2D only" to "2D + baseline 3D
mini-games end-to-end". Every new component's default value is lifted
verbatim from cocos-engine v3.8.6 sources (`cocos/physics/framework/...`,
`cocos/3d/lights/...`, `cocos/scene-graph/scene-globals.ts`,
`cocos/ui/...`) and pinned by regression tests.

**3D physics (+13 tools)** —
`cocos_add_rigidbody_3d` plus all eight colliders (`add_{box,sphere,
capsule,cylinder,cone,plane,mesh,terrain}_collider_3d`), two character
controllers (`add_{box,capsule}_character_controller`),
`cocos_create_physics_material` (writes a `.pmat` asset + meta; bind
via `cocos_set_uuid_property(col_id, "_material", uuid)`), and
`cocos_set_physics_3d_config` (gravity, timestep, sub-steps, sleep
threshold; writes `settings/v2/packages/physics.json`, default
gravity **-10 m/s² — NOT pixel units like set_physics_2d_config**).
`ERigidBodyType` is exported as `sb.RIGIDBODY_{DYNAMIC,STATIC,KINEMATIC}`
because the engine uses bitmask values (1/2/4, non-contiguous) that
are trivial to get wrong otherwise.

**3D rendering (+5 tools)** —
`cocos_add_{directional,sphere,spot}_light` with full HDR/LDR
illuminance pairs, `_staticSettings` sub-object, PCF shadow mode, and
(for DirectionalLight) the CSM block. `cocos_add_mesh_renderer`
(materials array = one per submesh, `_shadowCastingMode` / `_shadowReceivingMode`,
`_reflectionProbeId`) and `cocos_add_skinned_mesh_renderer`
(`_skinningRoot` is a **Node `__id__` reference, NOT a uuid** — a
common third-party bug, documented in the tool hint).

**Scene-global fog (+1 tool)** —
`cocos_set_fog` mirrors `set_ambient` / `set_skybox` / `set_shadows`,
lazy-creates `cc.FogInfo` + links it under `cc.SceneGlobals.fog` if
the scene predates this commit. Supports all four fog modes
(LINEAR / EXP / EXP² / LAYERED).

**UI polish (+3 tools)** —
`cocos_add_webview` (embedded browser pane for ToS / activity pages),
`cocos_add_scroll_bar` (companion to `ScrollView`, with `_handle` +
`_scrollView` as `__id__` refs), `cocos_add_page_view_indicator`
(dots row for `PageView` navigation).

**Build polish (+6 params on existing `cocos_build`)** —
`source_maps`, `md5_cache`, `skip_compress_texture`, `inline_enum`,
`mangle_properties` booleans + `build_options: dict[str, Any]` catch-all,
all joined into the Cocos CLI's `--build "k=v;k=v;..."` flag. Explicit
params win over dict conflicts; values containing `;` or `=` (which
would corrupt CLI parsing) are rejected with `ValueError` up-front.

### Fixed — 2D joint class-name mismatches (108 from 109)

Two of the nine 2D joint tools emitted `__type__` strings that Cocos
3.8 doesn't recognize. Verified against cocos-engine v3.8.6 sources
(`cocos/physics-2d/framework/components/joints/`): only **eight** joint
files exist, and neither `weld-joint-2d.ts` nor `motor-joint-2d.ts` is
among them. Scenes built with the old tools silently had no joint at
runtime.

- **Renamed** `cocos_add_weld_joint2d` → `cocos_add_fixed_joint_2d`,
  emitting `cc.FixedJoint2D` (the real class).
- **Removed** `cocos_add_motor_joint2d` — `cc.MotorJoint2D` doesn't
  exist in 3.8. The follow-target use case is covered by
  `cocos_add_relative_joint2d` via `_linearOffset` + `_angularOffset`.

Breaking change for any caller hitting the two old tool names, but
those calls were producing broken scenes anyway — "tool not found"
replaces silent runtime failure with a clear error.

### Added — Structured observability

- **`cocos/errors.py`** — central error surface with 8 `error_code`
  constants (`CREATOR_NOT_FOUND` / `BUILD_TIMEOUT` / `BUILD_FAILED` /
  `BUILD_MISSING_MODULE` / `BUILD_TYPESCRIPT_ERROR` /
  `BUILD_ASSET_NOT_FOUND` / …). `classify_build_log(log_tail)` pattern-
  matches common Cocos CLI failure signatures; `cli_build` attaches
  `{error_code, hint}` to every failure path so the LLM can recover
  without reading the log tail (e.g. "physics-2d module is off →
  `cocos_set_engine_module`"). TypeScript-error pattern is intentionally
  more specific than module-missing so `error TS2307: Cannot find module`
  classifies as TS error, not module error.
- **`cocos/types.py`** — 8 `TypedDict` return-shape contracts
  (`BuildResult` / `ValidationResult` / `BatchOpsResult` /
  `SceneCreateResult` / `PreviewStart/Stop/Status/Result`,
  `StructuredError`). `_BuildCommon` + `total=False` cleanly separates
  always-present from failure-only fields.
- **`tests/test_types.py`** — shape-drift tests reflect each tool's
  runtime dict keys against its TypedDict's `__annotations__`. Catches
  divergence that mypy can't (because `total=False` makes all keys
  optional from a static-typing perspective).
- **`find_creator`** — no-install error now names the recovery tool
  (`cocos_list_creator_installs`) and points to the Cocos Creator
  download page; version-mismatch error lists the locally-available
  versions.
- **`cocos_batch_scene_ops`** description now leads with
  "PREFERRED for ≥3 sequential mutations" so LLMs reach for it
  unprompted instead of firing ten individual `add_*` calls.

### Performance

- **Session-level scene read cache** (`cocos/scene_builder/_helpers.py`)
  — `_load_scene` keyed by resolved abspath + `st_mtime_ns`, LRU cap
  of 8 scenes. `_save_scene` refreshes the cache after a successful
  write, so the next tool call hits instead of re-parsing the file we
  just wrote. External edits (editor save, git checkout) bump mtime and
  the cache self-invalidates. Exported `invalidate_scene_cache()` for
  tests / manual sync.
- **Creator install list cached** via `functools.lru_cache(maxsize=1)`.
  `list_creator_installs()` was walking `/Applications/Cocos/Creator`
  every init / build call; cache hit makes the init path noticeably
  snappier on repeat runs. `invalidate_creator_installs_cache()` exported
  for the "I just installed a new Creator version" case.
- **Merged 3 + 4 redundant `rglob` scans** in `get_project_info` and
  `list_assets` into single `assets/**` walks with suffix dispatch.
  Noticeable on large projects; suffix dispatch preserves original
  behavior (verified by existing tests).
- **Explicit `timed_out: True`** on `cli_build` result when a build
  exceeds `timeout_sec` — previously it was indistinguishable from a
  non-timeout `exit_code = -1` crash.

### Fixed — narrower exception handling

- `scene_builder/batch.py` — replaced `except Exception` with
  `(KeyError, TypeError, ValueError, IndexError)` so our own
  implementation bugs (AttributeError, NameError, RuntimeError, ...)
  surface with a traceback instead of being silently reported as
  "op failed". Caller-mistake exceptions still get formatted into a
  per-op error dict.

### Changed — module-level refactors

- **`cocos/project.py` 1099 lines → 7-submodule package** under
  `cocos/project/`: `installs.py` (Creator detect + `init_project`),
  `assets.py` (script/image/audio/resource import + `list_assets` +
  `get_project_info`), `animation.py` (`.anim` builder), `skeletal.py`
  (Spine + DragonBones), `tiled.py`, `atlas.py` (SpriteAtlas `.pac`),
  `gen_image.py` (AI asset wrapper). Plus new `physics_material.py`
  for `.pmat` assets. `__init__.py` re-exports the full public surface
  so `from cocos import project as cp; cp.list_assets(...)` is
  unchanged, and the monkey-patch used by tests
  (`monkeypatch.setattr(cp, "list_creator_installs", ...)`) still
  takes effect — `find_creator` uses a late `from cocos.project
  import list_creator_installs` inside its body to pick up the patch.
- **`cocos/scene_builder/__init__.py` 1811 lines → 4 new submodules**:
  `physics.py` (RigidBody2D + 3 colliders + 8 Joint2D), `ui.py`
  (buttons/layout/progress/scroll/toggle/editbox/slider/masks/RichText/
  sprite variants/UIOpacity/SafeArea/PageView/ToggleContainer/
  MotionStreak/ScrollBar/PageViewIndicator/WebView + event builders),
  `media.py` (audio/anim/particle/camera/spine/DB/tiled/video +
  scene-globals setters including fog), `prefab.py` (create +
  instantiate + `_shift_id_refs`). Core `__init__.py` down to 685
  lines (scene lifecycle + node + basic component mutators +
  validation + generic `add_component`). Submodules that call back
  into `add_component` use a late `from cocos.scene_builder import
  add_component` to stay load-order-safe.
- **`cocos/scene_builder/rendering.py` (new)** — 3D lights +
  MeshRenderer + SkinnedMeshRenderer, with engine-matched constants
  `SHADOW_CAST_{OFF,ON}`, `SHADOW_RECV_{OFF,ON}`, `PCF_{HARD,SOFT,
  SOFT_2X,SOFT_4X}`, `REFLECT_{NONE,BAKED_CUBEMAP,PLANAR,BLEND}`,
  `CAMERA_DEFAULT_MASK`.
- **`cocos/scene_builder/physics_3d.py` (new)** — 3D physics, with
  `RIGIDBODY_{DYNAMIC,STATIC,KINEMATIC}` + `AXIS_{X,Y,Z}` exported
  as module constants so callers don't have to memorize the
  non-contiguous engine enum values.
- **`cocos/tools/{physics_3d,rendering_3d}.py` (new)** — MCP
  registrations for the 3D tools, kept in separate modules from 2D
  (`physics_ui.py`) so the 2D/3D surfaces can evolve independently.

### Tests

Test count: **166 → 226 (+60)**. New files:

| File | Tests | Covers |
|---|---|---|
| `test_physics_3d.py` | 18 | RigidBody3D defaults (+ non-contiguous enum regression guard) · parametrized collider shape fields · MeshCollider UUID wiring · CharacterController defaults · PhysicsMaterial `.pmat` asset shape + engine-default parity · `set_physics_3d_config` round-trip · scene validates with full 3D physics stack |
| `test_rendering_3d.py` | 10 | Per-light-type defaults · regression guard that all three lights carry the base `cc.Light` fields · MeshRenderer material array + shadow flag mapping + ModelBakeSettings nested shape · SkinnedMeshRenderer skeleton UUID + skinning_root `__id__` ref · scene validates with lit 3D render stack |
| `test_step3_polish.py` | 12 | FogInfo lazy-create + engine-default regression + idempotency · WebView URL round-trip · ScrollBar refs + null-omission · PageViewIndicator `cc.Size` + `__expectedType__` shape · `cli_build` dict + convenience-param merge semantics + unsafe-char guard |
| `test_errors.py` | 7 | `make_error` shape · `classify_build_log` pattern dispatch (TS / module / asset) · find_creator enrichment (lists available + names recovery tool) |
| `test_types.py` | 7 | Reflects `BuildResult` / `ValidationResult` / `BatchOpsResult` / `SceneCreateResult` / `PreviewStatusResult` `__annotations__` against runtime dict keys; all success + failure + timeout paths |
| `test_perf_optimizations.py` extension | +3 | Scene read cache hit (shared-ref return) · mtime invalidation on external write · LRU eviction past size cap |

All previous 166 tests continue to pass; 2D joint parametrize drops 1
(motor) and renames 1 (weld → fixed). CI still runs Ubuntu / macOS /
Windows × Python 3.11 / 3.12.

---

### Earlier work in this Unreleased cycle (45 → 108 tools, 45 → 166 tests)

What follows is the prior draft of `[Unreleased]` covering the publish-
readiness + 9-joint + lighting + AI-asset passes that shipped before
the 3D parity work above. It's kept here for continuity until the next
release tag; minor adjustments (joint-name supersession) applied in
place so the two halves reconcile.

#### Added — 29 new tools across four feature passes

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
- **9 × `cocos_add_*_joint2d`** — intended to ship the full Box2D joint
  family: `add_distance_joint2d / add_hinge_joint2d / add_spring_joint2d /
  add_mouse_joint2d / add_slider_joint2d / add_wheel_joint2d /
  add_weld_joint2d / add_relative_joint2d / add_motor_joint2d`. Each
  takes `connected_body_id` (the OTHER body's RigidBody2D component id;
  `None` means anchor to world). Unlocks pendulum / vehicle / chain /
  rope / suspension / weld-and-shatter games. **(Superseded:** weld
  was later renamed to `add_fixed_joint_2d` and motor was removed — see
  the 2D joint fix note above. Effective shipped set is 8 joints.**)**
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

#### Performance

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

#### Changed

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

#### Fixed

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

#### Removed

- `requirements.txt` (superseded by `pyproject.toml`).

#### Tests

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

### Future work

All three items called out in the previous Unreleased draft have been
addressed in the 3D-parity pass above:

- ✅ `scene_builder/__init__.py` refactor — now 685 lines; logic split
  across `physics.py` / `physics_3d.py` / `ui.py` / `media.py` /
  `prefab.py` / `rendering.py` + `_helpers.py` / `batch.py`.
- ✅ 3D primitives — DirectionalLight / SphereLight / SpotLight +
  MeshRenderer + SkinnedMeshRenderer + full 3D physics (RigidBody +
  8 colliders + 2 CharacterControllers + PhysicsMaterial) shipped.
- ✅ `cli_build` observability — timeout is now distinguishable and
  failure paths carry `error_code` + `hint`.

Remaining gaps deferred for a later release:

- **Marionette AnimationController** — 3.8's state-machine animation
  system. Required for humanoid 3D skeletal animation; MeshRenderer
  + SkinnedMeshRenderer alone can't drive it.
- **3D constraints** — `cc.HingeConstraint` / `cc.PointToPointConstraint`
  / `cc.ConfigurableConstraint` (3D equivalent of the 2D joint family).
- **`cc.PostProcess`** — Bloom / HBAO / ColorGrading / FXAA, reachable
  today via generic `cocos_add_component` but no friendly wrappers.
- **Terrain asset creation** — `cc.Terrain` + heightmap generation;
  `cocos_add_terrain_collider_3d` accepts a UUID but we can't yet
  create the backing asset. Lower priority because most mini-games
  use flat geometry.
- **`cc.ReflectionProbe` / `cc.LightProbeGroup`** — needed for PBR
  materials to look right. Rare in mini-games.
- **`cc.PostProcessStack`** — requires pipeline-specific serialization
  that varies between built-in and custom render pipelines.

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

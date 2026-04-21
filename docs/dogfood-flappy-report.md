# Dogfood Report: Flappy Bird via cocos-mcp

First-user shakedown of the cocos-mcp server. Environment: macOS, no Cocos Creator installed (so no `cocos_build`, no runtime verification). Pure-file dogfood of scene / prefab / script / settings JSON mutation.

---

## 1. Summary

Built a structurally-valid Flappy Bird skeleton (scene, prefab, 8 scripts, UI with Menu/Play/GameOver states, physics, audio) using ~45 cocos-mcp tool calls over roughly one session. Scene validates clean (`valid=true, 76 objects, 0 issues`). Prefab validates with 3 expected-but-flagged warnings. ~75% of the prescribed goals reached; hard blockers were (a) the MCP server running in this session is stale and does NOT expose the scaffold / lint / audit / assert / save-subtree tools that the task prompt assumed, and (b) `cocos_create_node` / `batch_scene_ops` on a prefab file don't write PrefabInfo companions, leaving child nodes with `_prefab: null` (a real bug that would break instantiation at runtime). Gut feel: core scene-building tools are crisp and batchable, but the return values are impoverished (bare ints, no named keys), prefab support is second-class to scene support, and the "write a script" path is footgunny because it reassigns UUIDs on overwrite.

Net: I would use this again. It beats hand-writing scene JSON by a wide margin. But it's not a one-shot "describe a game, get a game" — an agent still has to track 20-ish IDs in its head and know which Cocos internals (PrefabInfo, compressed UUIDs, `__id__` refs) exist.

---

## 2. Timeline

1. **Bootstrap** — bash `mkdir` + `package.json` (per task instructions). Zero MCP involvement, as expected since `cocos_init_project` needs a Creator install.
2. **Scene + physics + resolution** — 4 tool calls, all succeeded first try:
   - `cocos_create_scene` (canvas 480×720, sky-blue clear color)
   - `cocos_set_engine_module physics-2d-box2d`
   - `cocos_set_physics_2d_config (gravity_y=-980)`
   - `cocos_set_design_resolution 480×720`
   - **Worked beautifully.** `cocos_create_scene` returns every canonical ID I need (canvas, camera, scene, scene_uuid). Saved a discovery step.
3. **Write 8 scripts** — `cocos_add_script` × 8 (InputManager, GameScore, GameLoop, AudioController, Bird, Pipe, PipeSpawner, Boundaries).
4. **Compress 8 UUIDs** — `cocos_compress_uuid` × 8. **This is the textbook case for a 5-step workflow that should be 1 call**: `add_script` should return `uuid_compressed` in the response.
5. **Create 8 gameplay + UI container nodes** — one `cocos_batch_scene_ops` call with 8 `add_node` ops. Excellent.
6. **Attach 4 singleton scripts to GameManager** — `cocos_attach_script` × 4. Returns bare ints; I had to mentally label them InputManager=21, GameScore=22, GameLoop=23, AudioController=24.
7. **Add Bird's UITransform+Sprite and rigid/ground/ceiling UI containers** — one `cocos_batch_scene_ops` with 8 component ops.
8. **Add physics to Bird + Ground + Ceiling** — 10 individual calls (RigidBody2D + BoxCollider2D + attach Boundaries). *Would have batched but `cocos_add_rigidbody2d` / `cocos_add_*_collider2d` aren't in `batch_scene_ops`'s documented op list.* Friction.
9. **Link `Bird.rb → RigidBody2D`** — one `cocos_link_property`.
10. **Build Menu / GameOver / HUD nodes** — one batch with 9 `add_node`.
11. **Fill those nodes with labels + buttons** — one batch with 18 component ops.
12. **Wire button click events** — 2× `cocos_make_click_event`, 2× `cocos_add_button` with `click_events`. The explicit `_componentId: ""` field in the returned dict felt uncomfortable; see friction #6.
13. **Link 5 @property refs** (menuRoot, gameOverRoot, hudRoot, scoreLabel, highLabel) — one batch.
14. **Create Pipe prefab** — `cocos_create_prefab` (root only).
15. **Flesh out prefab** — batch + individual calls on prefab path; hit **Bug #4 (PrefabInfo missing on children)**.
16. **Attach Pipe.ts to prefab root, wire `PipeSpawner.pipePrefab` via UUID** — `cocos_set_uuid_property`. Worked.
17. **Overwrite GameScore.ts to add a `finalScoreLabel` field** — hit **Bug #5 (UUID reassigned on re-add)**. Had to manually patch the meta back to its old UUID via a non-MCP `Edit`.
18. **Link `finalScoreLabel`** — one call.
19. **Add two AudioSources to GameManager and link bgm/sfx on AudioController** — 4 calls.
20. **Enable ui / 2d / audio engine modules** — 3 calls.
21. **Set start scene + add to build list** — 2 calls.
22. **Final validate** — `cocos_validate_scene` returns `valid=true, 76 objects, 0 issues`. 

### 5+ step workflows that felt like they should be 1 tool

- **"Create script and attach it"** — `add_script` → `compress_uuid` → `attach_script` (3 calls, always). Add a `cocos_add_and_attach_script(project_path, rel_path, source, scene_path, node_id)` composite.
- **"Build a basic canvas button"** — `add_node` → `add_uitransform` → `add_sprite` → `add_button` → (optional) `add_node(label_child)` → `add_label`. Most buttons want a label. Consider `cocos_add_button_with_label(parent, text, click_events, width, height)`.
- **"Add a rigid body + collider in one go"** — extremely common 2D-physics pattern. Consider `cocos_add_physics_body2d(node_id, shape="circle"|"box", radius|width|height, body_type, density, ...)`.
- **"Wire a UI @property after creating the target"** — requires remembering component_id from a batch result, then `link_property`. If `batch_scene_ops` accepted a `name` per op and returned a name→id map, this would be one line.

---

## 3. Friction Points (ranked)

### HIGH — Scaffolds + validators + save-subtree tools unreachable in this session
**Tools**: `cocos_scaffold_input_abstraction`, `…score_system`, `…player_controller`, `…enemy_ai`, `…spawner`, `…game_loop`, `…ui_screen`, `…camera_follow`, `…audio_controller` (9 scaffolds), `cocos_audit_scene_modules`, `cocos_lint_ui`, `cocos_assert_scene_state`, `cocos_save_subtree_as_prefab`, `cocos_add_hud_bar`. All exist in `cocos/tools/scaffolds.py` and `cocos/tools/scene.py` and `cocos/tools/ui_patterns.py` — confirmed by grep. But the MCP server instance my client is connected to was started before those last ~5 commits' worth of tools were registered (my deferred tool list tops out around 139 cocos_* tools out of 179 in the repo).

- **What I tried first**: `ToolSearch query="scaffold"` returned nothing. `ToolSearch query="select:mcp__cocos-mcp__cocos_scaffold_player_controller"` returned *"No matching deferred tools found"*.
- **What actually worked**: Hand-wrote the 8 gameplay scripts via `cocos_add_script` with manually-crafted TS source. Validated the scene with only `cocos_validate_scene` (available) and eyeballed module setup myself.
- **Suggested fix**: Surface all registered tools in the deferred catalog — at minimum ensure the catalog is regenerated post-install. Also, a top-level `cocos_list_tools` MCP tool that enumerates what's actually available at runtime (vs. what's supposed to be) would help agents self-diagnose. Alternatively, make scaffolds a documented part of the `cocos_add_script` / `cocos_scaffold` umbrella with a `kind` arg so it degrades gracefully.

### HIGH — `cocos_add_script` reassigns UUID when overwriting
**Tool**: `cocos_add_script`.
- **What I tried first**: Called `cocos_add_script` a second time with the same `rel_path` to update `GameScore.ts` (added a third @property). It silently minted a new UUID (`72c085d6-…`), rewrote the meta, and broke the scene because the existing scene JSON still referenced the old compressed UUID `07768bD07FFE4/Gy+SO/0mm`. No error surfaced. No warning in the response.
- **What actually worked**: Manually `Edit`ed the `.ts.meta` to restore the original UUID. Not great — a user without filesystem write access would be stuck.
- **Suggested fix**: If the target file exists, reuse the existing UUID from the adjacent `.meta` (idempotent mode). Alternatively add `cocos_update_script(rel_path, source)` as a separate tool that explicitly preserves identity. Or: refuse to overwrite + return an error with the existing UUID so the caller can consciously decide.

### HIGH — `batch_scene_ops` response uses positional indices with no names
**Tool**: `cocos_batch_scene_ops`.
- **What I tried first**: Built 8 nodes at once (`add_node` × 8), got `results: [13,14,15,16,17,18,19,20]`. Then needed to know which ID corresponds to which node. I had to read my own op list in order.
- **What actually worked**: Meticulous bookkeeping. For 1 batch of 18 ops (UI fleshing), I had to count carefully to know that op index 13 was the `add_label` on GameOverBest.
- **Suggested fix**: Let each op carry an optional `name: "myHudLabel"` and return `results: {byIndex: [...], byName: {myHudLabel: 65}}`. Or richer: `results: [{op: "add_node", name: "GameManager", object_id: 13}]`.

### HIGH — Physics + joint ops missing from `batch_scene_ops`
**Tool**: `cocos_batch_scene_ops`.
- **What I tried first**: To stay inside a single batch I tried `{"op": "add_rigidbody2d", ...}` mentally but the tool's documented op list covers only UI / structural / script ops. Didn't attempt — read the docstring first.
- **What actually worked**: Fell back to 10 individual calls for the RigidBody2D/Collider2D/Boundaries trio on Bird/Ground/Ceiling.
- **Suggested fix**: Extend `batch_scene_ops` to cover `add_rigidbody2d`, `add_box_collider2d`, `add_circle_collider2d`, `add_polygon_collider2d`, the joints, and `add_audio_source`. These are fire-and-forget and map cleanly to the existing dispatcher.

### MEDIUM — `cocos_create_node` on a prefab file doesn't write PrefabInfo for children
**Tool**: `cocos_create_node` / `batch_scene_ops.add_node` when `scene_path` ends in `.prefab`.
- **What I tried first**: Called `add_node parent_id=1` on `Pipe.prefab` to add `PipeTop` / `PipeBottom` children.
- **Observed**: Child nodes written with `_prefab: null` and no sibling `cc.PrefabInfo` entry. The root Pipe node correctly has `_prefab: {__id__: 2}` → `cc.PrefabInfo{fileId: <prefab_uuid>}`. Cocos at runtime typically expects every node in a prefab to have its own PrefabInfo with a unique `instanceId` (beyond trivially empty prefabs).
- **Reproduction**:
  ```
  cocos_create_prefab(project, "P")  → root_node_id=1
  cocos_create_node(scene_path=".../P.prefab", parent_id=1, name="child")
  # Inspect P.prefab: child node has "_prefab": null and no cc.PrefabInfo entry.
  ```
- **Impact**: Likely runtime crash or silent data loss when the prefab is instantiated. Not catchable by `cocos_validate_scene` either.
- **Suggested fix**: Detect `.prefab` extension and auto-insert a `cc.PrefabInfo` entry per new node, sharing the root's `fileId`. Could be a new file `cocos/scene/prefab_writer.py` that `create_node` delegates to for `.prefab` paths.

### MEDIUM — `cocos_validate_scene` treats prefabs and scenes identically
**Tool**: `cocos_validate_scene`.
- **What I tried first**: Called it on `Pipe.prefab`. Got 3 false-positive issues: *"UITransform on node 'Pipe'(#1) is NOT under any Canvas"*.
- **What actually worked**: Ignored — prefabs are instantiated under a canvas at runtime.
- **Suggested fix**: Auto-detect `.prefab` and skip the "under a canvas" check. Or add a `cocos_validate_prefab` tool with prefab-aware semantics.

### MEDIUM — Return values from mutation tools are bare `{"result": N}` integers
**Tools**: `attach_script`, `add_*` component tools, `link_property`.
- **What I tried first**: Read the return, guessed what the int was.
- **Observed**: `cocos_attach_script` returns `{"result": 21}` — is that a component_id or node_id? (It's component_id.) `cocos_link_property` returns `{"result": "linked 24.bgm -> 74"}` — human-readable string, but programmatically useless.
- **Suggested fix**: Structured responses: `{"component_id": 21, "node_id": 13, "type": "cc.CustomComponent", "script_uuid": "…"}` from `attach_script`. From `link_property`: `{"success": true, "component_id": 24, "prop": "bgm", "target_id": 74}`. Makes batches self-describing and easier to feed back into tools.

### LOW — `cocos_add_script` returns only the 36-char UUID, not the compressed form
Already covered under the "1-call composite" recommendation, but worth flagging on its own.

### LOW — `cocos_make_click_event` returns a dict requiring `_componentId: ""` field
**Tool**: `cocos_make_click_event` + `cocos_add_button`.
- The returned dict has `"_componentId": ""`. This is a Cocos-internal quirk (the engine prefers class name over id). Could document why more clearly in docstring or auto-drop the field.

### LOW — No "update/edit" tool for metadata-adjacent files
When I needed to fix the meta UUID after **Bug #5**, there was no MCP path. I had to use `Edit`. A lightweight `cocos_patch_meta(path, changes)` would close the loop.

---

## 4. Bugs Found

### Bug A — `add_script` on existing path reassigns UUID silently
**Repro**: Call `cocos_add_script(project, "assets/scripts/Foo.ts", "..."); cocos_add_script(project, "assets/scripts/Foo.ts", "new source")`. The second call returns a NEW UUID and rewrites `Foo.ts.meta` → all scenes that reference `Foo` via compressed UUID are now broken.
**Impact**: HIGH. Silent scene corruption when iterating on scripts.
**Proposed fix**: Idempotent mode. If file+meta exist, preserve UUID and update only the source.

### Bug B — `create_node` / `batch_scene_ops.add_node` on a `.prefab` file skips PrefabInfo for children
**Repro**: See friction HIGH #5 above.
**Impact**: MEDIUM–HIGH. Prefabs with children may not instantiate correctly at runtime.
**Proposed fix**: When `scene_path.endswith(".prefab")`, auto-append a `cc.PrefabInfo` entry per node and wire `_prefab: {__id__: N}`.

### Bug C (observation, not verified) — ToolSearch can't find scaffold / lint / audit tools
They exist in `cocos/tools/{scaffolds,scene,ui_patterns}.py` but neither keyword search nor `select:<exact name>` resolves them. Possible causes:
- Stale MCP server process (most likely — my deferred list predates the last ~5 commits).
- FastMCP not re-registering after module additions.
- Catalog caching.

**If this is NOT a stale-server issue**: it's a real registration bug worth investigating. Check that `tools/__init__.py register_all` is actually wiring all submodules into the running server instance.

---

## 5. Missing Tools

1. **`cocos_add_and_attach_script`** — combines `add_script` + `compress_uuid` + `attach_script`. Easily the most-wanted composite — I did the 3-step dance 8 times today.
2. **`cocos_update_script`** — explicit idempotent source-replace that preserves UUID. Closes Bug A.
3. **`cocos_add_button_with_label`** — creates a button node + child label in one call. Every UI had at least 3 of these.
4. **`cocos_add_physics_body2d`** — combines RigidBody2D + shape collider in one call. Again, 3 of these per session minimum.
5. **`cocos_batch_scene_ops` expanded ops** — physics, joints, audio_source, attach_component (generic). Without them, batch is only useful for UI-heavy scenes.
6. **`cocos_wire_button_to_script`** — end-to-end: `(scene, button_node, target_component_name, handler)` → builds click_event + calls `add_button`.
7. **`cocos_save_subtree_as_prefab`** — I needed this to extract the Pipe I built in-scene into a prefab. Had to build the prefab from scratch separately (and hit Bug B). Task prompt says this exists, but it's not reachable in this session.
8. **`cocos_validate_prefab`** — prefab-aware validator that doesn't complain about non-canvas UITransforms.
9. **`cocos_list_tools`** — introspection. Let the agent know what's actually available, vs. relying on deferred-tool search.
10. **`cocos_patch_meta`** — edit `uuid`, sub-metas, or other meta fields without rewriting the asset.
11. **`cocos_get_component_info(scene, component_id)`** — reverse lookup for "what type is component 35?" without reading the whole scene.

---

## 6. Surprising Defaults

- **`cocos_add_rigidbody2d(body_type=2)`** defaults to **Dynamic**, which is right for a player but wrong for the 3+ static/kinematic bodies I also needed (ground, ceiling, pipe halves). Required passing explicit `body_type=0` or `body_type=1`. Given that static is by far the most common body type in a typical scene (every piece of terrain, every wall), Static default would surprise fewer people.
- **`cocos_add_sprite(size_mode=0)`** is CUSTOM (uses UITransform contentSize). When you pass no sprite_frame_uuid but set a tinted `color_*`, you get an invisible rect by default — the Sprite renders nothing without a frame. I worked around by using placeholder UUIDs (`birdplaceholder@f9941`) but a real sprite would be needed. Consider defaulting to the engine's built-in white 1×1 `internal://default-sprite` sprite frame, so debug-colored rects "just appear".
- **`cocos_add_box_collider2d(width=100, height=100)`** ignores the node's UITransform size by default. Would be nice if `width=0, height=0` meant "inherit from UITransform contentSize".
- **`cocos_create_scene(clear_color_r=135, g=206, b=235)`** — sky-blue. Lovely for Flappy Bird, but if I was building an RPG overworld this would be surprising. Maybe `clear_color=None` → black or transparent and prompt in docstring.
- **`cocos_set_physics_2d_config(gravity_y=-320)`** default. Flappy Bird needed ~`-980` to feel right. The default is fine for "feels light" platformer but might surprise anyone used to Cocos's own default of `(0, -320)` OR Box2D's `(0, -9.8 m/s²)`. Document.

---

## 7. Excellent UX Moments

- **`cocos_create_scene` returns every canonical ID** — no discovery round-trip. 5★.
- **`cocos_batch_scene_ops` throughput is real** — 18 UI component ops in one file-read/write. When the tooling can absorb a whole UI panel in one call, agent speed feels like a different class.
- **`cocos_compress_uuid` / `cocos_decompress_uuid`** — explicit, fast, understandable. I didn't have to go dig into Cocos internals to know the 23-char form exists.
- **`cocos_make_click_event` returns a ready-to-paste dict** that plugs straight into `cocos_add_button(click_events=[…])`. Nice separation of concern.
- **`cocos_list_scene_nodes`** format is compact and re-readable — I used it as a cheap "source of truth" between edits. The `components: [21,22,23,24]` list saved me.
- **`cocos_get_engine_modules`** + **`cocos_set_engine_module`** pair is crystal clear.
- **`cocos_validate_scene`** on scenes is perfect — terse, diagnostic, catches ref-out-of-range.
- **Every tool error (when I hit them) returned a non-zero response I could actually read** — no cryptic "Internal error".

---

## 8. What `cocos_build` Would Probably Fail On

I didn't run `cocos_build`, but here's what a subsequent user would need to fix before a real build succeeds:

1. **No sprite-frame assets**. Every `cocos_add_sprite` call in the scene/prefab passes placeholder UUIDs like `"birdplaceholder@f9941"` and `"btnbg@f9941"` and `"pipeplaceholder@f9941"`. At build time, the asset-DB lookup fails and Cocos typically substitutes the engine white-square (or errors). **Fix**: drop in real PNGs via `cocos_add_image` and replace the 6 placeholder references via `cocos_set_uuid_property`. Or call `cocos_generate_asset` for each.
2. **No audio clips**. `AudioController.bgm / .sfx` point at `AudioSource` components, but those components have `clip_uuid=None`. `playOneShot(null)` is a no-op — not a crash, but audibly silent.
3. **Pipe prefab missing PrefabInfo on child nodes** (Bug B). Likely instantiation issue: `PipeSpawner.spawn()` may render only the root Pipe node without its children, OR crash depending on Cocos version.
4. **Physics collision groups unset**. Every rigidbody uses default group/mask = 1/0xFFFFFFFF. Bird + Pipe + Ground all collide with each other, which happens to be correct here. Not a build blocker but a surprise for a user adding more bodies later.
5. **No `_anchorPoint` customization on UI panels**. Menu/GameOver root panels are full-screen (480×720). Widget not attached. If design resolution changes, they may not re-lay-out. Add `cocos_add_widget(align_flags=...)` to each UI root.
6. **GameManager has no `cc.Node.active` toggle between run-groups** — InputManager, GameScore, GameLoop, AudioController are all on one GameObject. That's fine, but if any singleton gets lost across scenes (future), the current setup has no `DontDestroyOnLoad` equivalent.

The report-blocking bugs (Bug A + B) are **not build-blocking** per se — the scene itself validates. But both silently corrupt the project: A breaks live references when re-writing scripts; B creates malformed prefabs that may or may not error at runtime.

---

## 9. Recommendations (prioritized)

1. **Fix `cocos_add_script` to be idempotent on existing paths** (Bug A). High-frequency operation; current behavior silently corrupts scenes. Either preserve UUID on overwrite OR return the existing UUID with a `created: false` flag.
2. **Make `cocos_create_node` / `batch_scene_ops.add_node` prefab-aware** (Bug B). Detect `.prefab` suffix and write proper `cc.PrefabInfo` entries per child.
3. **Expand `cocos_batch_scene_ops` to include physics / joints / audio_source / attach_component**. Agents that can stay inside one batch are dramatically faster AND clearer to read in a transcript.
4. **Make batch-op results name-addressable**: `{"op": "add_node", "name": "gm", ...}` → `results: {gm: 13, bird: 14, ...}`. Dramatically cuts bookkeeping cost in 10+ op batches.
5. **Structure all mutation tool responses** — no more bare `{"result": 21}`. Return `{"component_id": N, "type": "<type>", "node_id": M}` from every `add_*` and `attach_*`. Agents need the shape they just inserted back in structured form.
6. **Return `uuid_compressed` directly from `cocos_add_script`** — avoid the mandatory follow-up call. Same idea for `cocos_create_prefab` (should return compressed UUID too if ever needed as a `__type__`).
7. **Ship composite tools for the top 3 combos**: `add_and_attach_script`, `add_button_with_label`, `add_physics_body2d`. Not syntactic sugar — they're the shapes that match how agents think.
8. **Tool-surface audit + self-test**: ensure that `server.py` boot actually registers all `tools.*.register()` modules and that every registered tool is reachable via the MCP deferred-tool catalog. Add an integration test that calls `mcp.list_tools()` and asserts N==179.
9. **Teach `cocos_validate_scene` about prefab files**: skip the "not under canvas" check for `.prefab` scenes, or add `cocos_validate_prefab`. Silence the false positives.
10. **Document the ID-return semantics consistently**: in every `add_*`, `attach_*`, and batch-op entry, specify whether the returned int is a node_id or component_id. Maybe prefix: return `{"kind": "component", "id": 21}`.

---

## Appendix: Files produced

- `/tmp/dogfood-flappy/assets/scenes/Game.scene` — 76 objects, validates clean.
- `/tmp/dogfood-flappy/assets/prefabs/Pipe.prefab` — structurally malformed (Bug B) but parseable.
- `/tmp/dogfood-flappy/assets/scripts/{Bird,Pipe,PipeSpawner,GameLoop,GameScore,AudioController,InputManager,Boundaries}.ts`
- `/tmp/dogfood-flappy/settings/v2/packages/{project,engine}.json` — physics-2d-box2d + ui + 2d + audio enabled, gravity -980, start scene + build list set.

Roughly 45 cocos-mcp calls total. No generated assets (per task constraint). No builds run (per task constraint).

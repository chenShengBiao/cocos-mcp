"""Scaffold for a singleton game-loop state machine.

Every small game reinvents "menu -> play -> game over -> menu" as a
tangled web of booleans on the root scene. This scaffold emits a single
``GameLoop`` singleton where each state gets a pair of inspector-visible
callback hooks (``onEnter<State>`` / ``onExit<State>``) plus a tiny
runtime API (``go`` / ``reset`` / ``current``) so gameplay scripts can
poll ``GameLoop.I.current`` in their update loop. The state list is
parameterized so the LLM can ask for ``["idle", "attack", "dead"]``
instead of being forced into menu/play/over.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..project.assets import add_script
from ..uuid_util import compress_uuid

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _pascal(name: str) -> str:
    """Turn ``"game_over"`` → ``"GameOver"``, ``"menu"`` → ``"Menu"``.

    Splits on underscores so snake_case inputs round-trip cleanly into
    the TS callback field naming (``onEnterGameOver``).
    """
    return "".join(part[:1].upper() + part[1:] for part in name.split("_") if part)


def _validate_states(states: list[str]) -> None:
    if len(states) < 1:
        raise ValueError("states must contain at least one state")
    seen: set[str] = set()
    for s in states:
        if not isinstance(s, str) or not s:
            raise ValueError(f"state must be a non-empty string; got {s!r}")
        if not _IDENT_RE.match(s):
            raise ValueError(
                f"state {s!r} is not a valid identifier "
                "(must match ^[A-Za-z_][A-Za-z0-9_]*$)"
            )
        if s in seen:
            raise ValueError(f"duplicate state: {s!r}")
        seen.add(s)


def _render_template(states: list[str]) -> str:
    """Emit the GameLoop.ts source with one @property pair per state."""
    pascal_names = [_pascal(s) for s in states]
    first = states[0]

    # @property pairs for inspector wiring — one enter/exit per state.
    prop_lines: list[str] = []
    for raw, pas in zip(states, pascal_names):
        prop_lines.append(
            f"    @property({{ tooltip: 'Called when entering {raw} state' }})\n"
            f"    onEnter{pas}: (() => void) | null = null;\n"
            f"    @property({{ tooltip: 'Called when exiting {raw} state' }})\n"
            f"    onExit{pas}: (() => void) | null = null;"
        )
    props_block = "\n\n".join(prop_lines)

    # Dispatch-switch arms, one per state.
    enter_arms = "\n".join(
        f"            case '{raw}': if (this.onEnter{pas}) this.onEnter{pas}(); break;"
        for raw, pas in zip(states, pascal_names)
    )
    exit_arms = "\n".join(
        f"            case '{raw}': if (this.onExit{pas}) this.onExit{pas}(); break;"
        for raw, pas in zip(states, pascal_names)
    )

    states_literal = ", ".join(f'"{s}"' for s in states)

    return f"""\
import {{ _decorator, Component }} from 'cc';
const {{ ccclass, property }} = _decorator;

/**
 * Singleton game-loop state machine.
 *
 * Runtime API:
 *   GameLoop.I.current       current state name (string)
 *   GameLoop.I.go(state)     transition; fires onExit<old> then onEnter<new>
 *   GameLoop.I.reset()       jump straight to the first state
 *
 * Designers wire per-state callbacks via the inspector; gameplay scripts
 * can also poll ``GameLoop.I.current`` each update() if they prefer.
 */
@ccclass('GameLoop')
export class GameLoop extends Component {{
    private static _instance: GameLoop | null = null;
    static get I(): GameLoop {{ return GameLoop._instance!; }}

{props_block}

    public current: string = "{first}";
    private _states: string[] = [{states_literal}];

    onLoad() {{
        if (GameLoop._instance && GameLoop._instance !== this) {{
            this.destroy();
            return;
        }}
        GameLoop._instance = this;
        this.current = this._states[0];
    }}

    onDestroy() {{
        if (GameLoop._instance === this) GameLoop._instance = null;
    }}

    go(state: string): void {{
        if (!this._states.includes(state)) {{
            console.warn(`[GameLoop] unknown state: ${{state}}`);
            return;
        }}
        if (state === this.current) return;
        const old = this.current;
        this._dispatchExit(old);
        this.current = state;
        this._dispatchEnter(state);
    }}

    reset(): void {{
        this.go(this._states[0]);
    }}

    private _dispatchEnter(state: string): void {{
        switch (state) {{
{enter_arms}
        }}
    }}

    private _dispatchExit(state: string): void {{
        switch (state) {{
{exit_arms}
        }}
    }}
}}
"""


def scaffold_game_loop(project_path: str | Path,
                      states: list[str] | None = None,
                      rel_path: str = "GameLoop.ts") -> dict:
    """Generate GameLoop.ts — singleton state machine.

    states: ordered list, default ["menu", "play", "over"]. Used
    to generate per-state ``onEnter<Name>`` / ``onExit<Name>`` callback
    properties visible in the inspector. The generator validates
    state names: non-empty, ASCII-identifier-safe, no duplicates.

    Runtime API (generated regardless of states):
      GameLoop.I.current   // current state name (string)
      GameLoop.I.go(state) // transition; fires onExit<old> then onEnter<new>
      GameLoop.I.reset()   // jump straight to the first state

    Each state gets two inspector-visible @property callback slots the
    designer can wire visually — or scripts can just check
    ``GameLoop.I.current`` in their update loop. Callbacks are invoked
    with no args (keep it simple).

    Snake_case state names are PascalCased for the callback field:
    ``"game_over"`` becomes ``onEnterGameOver``.

    Returns {path, rel_path, uuid_standard, uuid_compressed}.
    """
    effective_states = list(states) if states is not None else ["menu", "play", "over"]
    _validate_states(effective_states)

    source = _render_template(effective_states)
    result = add_script(project_path, rel_path, source)
    return {
        "path": result["path"],
        "rel_path": result["rel_path"],
        "uuid_standard": result["uuid"],
        "uuid_compressed": compress_uuid(result["uuid"]),
    }

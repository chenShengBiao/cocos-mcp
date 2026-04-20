"""Design-token registry for UI-building tools.

Gives the orchestrating LLM a fixed vocabulary of semantic design values
(``primary``, ``body``, ``md`` spacing, ``lg`` radius …) in place of
free-form integers and RGBA quadruples. Five built-in themes supply the
actual numbers; the user picks one with ``cocos_set_ui_theme`` and every
subsequent ``add_label`` / ``add_button`` / ``add_sprite`` call that
passes ``color_preset="primary"`` or ``size_preset="title"`` resolves
through the registry.

Why fixed preset *names* but swappable themes: users should be able to
switch from ``dark_game`` to ``neon_arcade`` by changing one line
without re-editing every scene. If each theme invented its own preset
vocabulary, swap would break references. The names below form the
stable contract.

Preset vocabularies

* color: primary, secondary, bg, surface, text, text_dim,
  success, warn, danger, border          (10 names)
* font_size: title, heading, body, caption                 (4)
* spacing:   xs, sm, md, lg, xl                            (5)
* radius:    sm, md, lg, pill                              (4)

Registry location: ``settings/v2/packages/ui-tokens.json`` — same
convention as ``post-build-patches.json`` and ``engine.json``. Cocos
Creator doesn't recognize the filename so it won't touch it, and git
tracks it alongside other project settings.

Resolution fallback: callers ask for a preset on a project that hasn't
set a theme → fall back to the bundled ``dark_game`` defaults. We
deliberately don't raise here: the orchestrating LLM may add UI before
picking a theme, and a silent sensible default beats a hard stop.
``cocos_get_ui_tokens`` always reflects the ACTIVE theme (including the
dark_game fallback), so the caller can still introspect.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REGISTRY_REL = Path("settings") / "v2" / "packages" / "ui-tokens.json"

# Stable preset names every theme MUST provide. Custom themes via
# ``cocos_set_ui_theme(project, custom={...})`` are allowed to omit
# names — we fill missing ones from the dark_game defaults at load
# time, so switching themes never leaves a preset unresolved.
COLOR_NAMES = ("primary", "secondary", "bg", "surface", "text",
               "text_dim", "success", "warn", "danger", "border")
SIZE_NAMES = ("title", "heading", "body", "caption")
SPACING_NAMES = ("xs", "sm", "md", "lg", "xl")
RADIUS_NAMES = ("sm", "md", "lg", "pill")

# ----- bundled themes -----

BUILTIN_THEMES: dict[str, dict[str, dict[str, Any]]] = {
    "dark_game": {
        "color": {
            "primary":   "#6366f1",  # indigo — strong CTAs
            "secondary": "#ec4899",  # pink — accent / highlight
            "bg":        "#0f172a",  # slate-900 — deep background
            "surface":   "#1e293b",  # slate-800 — cards, panels
            "text":      "#e2e8f0",  # slate-200 — body text
            "text_dim":  "#94a3b8",  # slate-400 — captions, metadata
            "success":   "#22c55e",  # green-500
            "warn":      "#f59e0b",  # amber-500
            "danger":    "#ef4444",  # red-500
            "border":    "#334155",  # slate-700 — subtle separators
        },
        "font_size": {"title": 72, "heading": 48, "body": 32, "caption": 24},
        "spacing":   {"xs": 4, "sm": 8, "md": 16, "lg": 32, "xl": 64},
        "radius":    {"sm": 4, "md": 8, "lg": 16, "pill": 9999},
    },
    "light_minimal": {
        "color": {
            "primary":   "#2563eb",  # blue-600
            "secondary": "#64748b",  # slate-500
            "bg":        "#ffffff",
            "surface":   "#f8fafc",  # slate-50
            "text":      "#0f172a",  # slate-900
            "text_dim":  "#475569",  # slate-600
            "success":   "#16a34a",
            "warn":      "#d97706",
            "danger":    "#dc2626",
            "border":    "#e2e8f0",  # slate-200
        },
        "font_size": {"title": 64, "heading": 44, "body": 28, "caption": 22},
        "spacing":   {"xs": 4, "sm": 8, "md": 16, "lg": 32, "xl": 64},
        "radius":    {"sm": 2, "md": 6, "lg": 12, "pill": 9999},
    },
    "neon_arcade": {
        "color": {
            "primary":   "#22d3ee",  # cyan-400
            "secondary": "#f472b6",  # pink-400
            "bg":        "#030712",  # gray-950
            "surface":   "#111827",  # gray-900
            "text":      "#f0fdff",  # near-white with cyan tint
            "text_dim":  "#67e8f9",  # cyan-300
            "success":   "#4ade80",
            "warn":      "#facc15",
            "danger":    "#fb7185",  # rose-400
            "border":    "#0891b2",  # cyan-600
        },
        "font_size": {"title": 88, "heading": 56, "body": 36, "caption": 26},
        "spacing":   {"xs": 4, "sm": 8, "md": 20, "lg": 40, "xl": 80},
        "radius":    {"sm": 0, "md": 4, "lg": 8, "pill": 9999},  # sharper for arcade feel
    },
    "pastel_cozy": {
        "color": {
            "primary":   "#f472b6",  # pink-400
            "secondary": "#a78bfa",  # violet-400
            "bg":        "#fff7ed",  # orange-50
            "surface":   "#ffedd5",  # orange-100
            "text":      "#431407",  # orange-950
            "text_dim":  "#9a3412",  # orange-800
            "success":   "#86efac",  # green-300
            "warn":      "#fcd34d",
            "danger":    "#fda4af",  # rose-300
            "border":    "#fed7aa",  # orange-200
        },
        "font_size": {"title": 68, "heading": 44, "body": 30, "caption": 24},
        "spacing":   {"xs": 4, "sm": 10, "md": 20, "lg": 36, "xl": 72},
        "radius":    {"sm": 8, "md": 16, "lg": 24, "pill": 9999},  # soft, rounded
    },
    "corporate": {
        "color": {
            "primary":   "#0ea5e9",  # sky-500
            "secondary": "#10b981",  # emerald-500
            "bg":        "#f9fafb",  # gray-50
            "surface":   "#ffffff",
            "text":      "#111827",  # gray-900
            "text_dim":  "#6b7280",  # gray-500
            "success":   "#10b981",
            "warn":      "#f59e0b",
            "danger":    "#ef4444",
            "border":    "#e5e7eb",  # gray-200
        },
        "font_size": {"title": 56, "heading": 40, "body": 26, "caption": 20},
        "spacing":   {"xs": 4, "sm": 8, "md": 12, "lg": 24, "xl": 48},
        "radius":    {"sm": 2, "md": 4, "lg": 8, "pill": 9999},
    },
}

_DEFAULT_THEME = "dark_game"


# ----- registry IO -----

def _registry_path(project_path: str | Path) -> Path:
    return Path(project_path).expanduser().resolve() / _REGISTRY_REL


def _materialize_theme(theme_data: dict) -> dict:
    """Given a (possibly partial) theme dict, fill missing preset names
    from the default theme. Invariant: every preset name in every
    vocabulary resolves to something, so no ``color_preset="primary"``
    lookup ever fails mid-build.
    """
    base = BUILTIN_THEMES[_DEFAULT_THEME]
    out = {
        "color":     dict(base["color"]),
        "font_size": dict(base["font_size"]),
        "spacing":   dict(base["spacing"]),
        "radius":    dict(base["radius"]),
    }
    for group in ("color", "font_size", "spacing", "radius"):
        for k, v in (theme_data.get(group) or {}).items():
            out[group][k] = v
    return out


def _validate_custom_theme(custom: dict) -> None:
    """Light-weight sanity check on a user-supplied theme. Unknown
    keys are allowed (a user can add their own preset names beyond
    the standard vocab) but we reject structurally-broken values up
    front so ``apply_patches``-style silent corruption can't happen.
    """
    if not isinstance(custom, dict):
        raise ValueError("custom theme must be a dict")
    for group in ("color", "font_size", "spacing", "radius"):
        if group in custom and not isinstance(custom[group], dict):
            raise ValueError(f"theme.{group} must be a dict, got {type(custom[group]).__name__}")

    # Colors must be hex strings; this is the single type mismatch that
    # hides hardest (an int 0x6366f1 would silently resolve to a
    # completely different colour after RGBA conversion).
    for k, v in (custom.get("color") or {}).items():
        if not isinstance(v, str) or not v.startswith("#"):
            raise ValueError(
                f"color.{k} must be a hex string like '#6366f1', got {v!r}"
            )
    for group_name, typ in (("font_size", (int, float)),
                            ("spacing", (int, float)),
                            ("radius", (int, float))):
        for k, v in (custom.get(group_name) or {}).items():
            if not isinstance(v, typ) or isinstance(v, bool):
                raise ValueError(
                    f"{group_name}.{k} must be a number, got {v!r}"
                )


def set_ui_theme(project_path: str | Path,
                 theme: str | None = None,
                 custom: dict | None = None) -> dict:
    """Pin this project's active UI theme.

    Pass either a built-in ``theme`` name (one of ``dark_game``,
    ``light_minimal``, ``neon_arcade``, ``pastel_cozy``, ``corporate``)
    OR a ``custom`` dict with the shape ``{color, font_size, spacing,
    radius}``. When ``custom`` is partial, missing preset names fall
    through to ``dark_game`` defaults so every preset resolves.

    Giving both picks custom and stamps ``theme`` onto the registry
    as a "derived from" label (purely informational).

    Returns {registry_path, theme, resolved} where ``resolved`` is the
    fully materialized theme the registry will serve.
    """
    if theme is None and custom is None:
        # Default to dark_game — makes the first call trivial: just
        # cocos_set_ui_theme(project).
        theme = _DEFAULT_THEME

    if theme is not None and theme not in BUILTIN_THEMES:
        raise ValueError(
            f"unknown theme {theme!r}. Built-ins: {sorted(BUILTIN_THEMES)}. "
            "Pass a custom= dict instead."
        )

    base = BUILTIN_THEMES[theme] if theme else BUILTIN_THEMES[_DEFAULT_THEME]
    if custom is not None:
        _validate_custom_theme(custom)
        merged = _materialize_theme(custom)
    else:
        merged = _materialize_theme(base)

    payload = {
        "version": 1,
        "theme": theme,          # for reference; the active values are in ``resolved``
        "resolved": merged,
    }
    reg_path = _registry_path(project_path)
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(reg_path, "w") as f:
        json.dump(payload, f, indent=2)
    return {
        "registry_path": str(reg_path),
        "theme": theme,
        "resolved": merged,
    }


def get_ui_tokens(project_path: str | Path) -> dict:
    """Return the active theme — either what was set via ``set_ui_theme``
    or the dark_game default when the project never registered one.

    Always returns a fully-materialized theme so callers can rely on
    every standard preset name resolving.
    """
    reg = _registry_path(project_path)
    if reg.exists():
        try:
            with open(reg) as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and isinstance(payload.get("resolved"), dict):
            return {
                "theme": payload.get("theme"),
                "resolved": payload["resolved"],
                "source": "registry",
            }
    # Fallback: project hasn't set a theme yet
    return {
        "theme": _DEFAULT_THEME,
        "resolved": _materialize_theme(BUILTIN_THEMES[_DEFAULT_THEME]),
        "source": "fallback",
    }


def list_builtin_themes() -> dict:
    """Return all five bundled themes verbatim (no registry IO).

    Useful when the LLM wants to show the user choices without first
    picking one, or to base a custom theme off of."""
    return {
        "default": _DEFAULT_THEME,
        "themes": {name: _materialize_theme(theme) for name, theme in BUILTIN_THEMES.items()},
    }


# ----- resolvers used from scene_builder when a preset= kwarg is given -----

def _find_project_from_scene(scene_path: str | Path) -> Path | None:
    """Walk up from a scene file until we hit ``package.json``. Mirrors
    the helper in ``scene_builder/modules.py`` — duplicated to keep the
    import direction scene_builder → project rather than the reverse."""
    cur = Path(scene_path).expanduser().resolve().parent
    while True:
        if (cur / "package.json").exists():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent


def hex_to_rgba(hex_str: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Convert ``#rrggbb`` / ``#rgb`` / ``#rrggbbaa`` to an (r, g, b, a)
    int 0-255 tuple. Accepts with or without leading ``#``."""
    s = hex_str.strip().lstrip("#")
    # Validate shape + hex-digit-only up front so non-hex input like
    # "red" fails with a targeted message instead of ``int('re', 16)``.
    if len(s) not in (3, 6, 8) or any(c not in "0123456789abcdefABCDEF" for c in s):
        raise ValueError(
            f"bad hex color {hex_str!r}; expected '#rgb' or '#rrggbb' or '#rrggbbaa'"
        )
    if len(s) == 3:
        return (int(s[0] * 2, 16), int(s[1] * 2, 16), int(s[2] * 2, 16), alpha)
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), alpha)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))


def resolve_color(scene_path: str | Path | None,
                  preset: str,
                  alpha: int = 255) -> tuple[int, int, int, int]:
    """Look up a named color in the active theme and return RGBA ints.

    Raises if the preset is unknown AFTER falling back to dark_game —
    that means the name is a typo, not a missing theme."""
    tokens = _tokens_for(scene_path)
    hex_str = tokens["color"].get(preset)
    if hex_str is None:
        raise ValueError(
            f"unknown color preset {preset!r}. Available: "
            f"{sorted(tokens['color'].keys())}"
        )
    return hex_to_rgba(hex_str, alpha=alpha)


def resolve_size(scene_path: str | Path | None, preset: str) -> int:
    tokens = _tokens_for(scene_path)
    val = tokens["font_size"].get(preset)
    if val is None:
        raise ValueError(
            f"unknown font_size preset {preset!r}. Available: "
            f"{sorted(tokens['font_size'].keys())}"
        )
    return int(val)


def resolve_spacing(scene_path: str | Path | None, preset: str) -> int:
    tokens = _tokens_for(scene_path)
    val = tokens["spacing"].get(preset)
    if val is None:
        raise ValueError(
            f"unknown spacing preset {preset!r}. Available: "
            f"{sorted(tokens['spacing'].keys())}"
        )
    return int(val)


def resolve_radius(scene_path: str | Path | None, preset: str) -> int:
    tokens = _tokens_for(scene_path)
    val = tokens["radius"].get(preset)
    if val is None:
        raise ValueError(
            f"unknown radius preset {preset!r}. Available: "
            f"{sorted(tokens['radius'].keys())}"
        )
    return int(val)


# ----- seed-color theme derivation -----

def _hex_to_hsl(hex_str: str) -> tuple[float, float, float]:
    """#rrggbb → (h, s, l) with h∈[0,360), s,l∈[0,1]."""
    r, g, b, _ = hex_to_rgba(hex_str)
    rf, gf, bf = r / 255, g / 255, b / 255
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    l = (mx + mn) / 2
    if mx == mn:
        h = s = 0.0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == rf:
            h = (gf - bf) / d + (6 if gf < bf else 0)
        elif mx == gf:
            h = (bf - rf) / d + 2
        else:
            h = (rf - gf) / d + 4
        h *= 60
    return h, s, l


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Inverse of _hex_to_hsl. Clamps inputs so out-of-range values
    from intermediate math don't overflow."""
    h = h % 360
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))

    if s == 0:
        v = int(round(l * 255))
        return f"#{v:02x}{v:02x}{v:02x}"

    def _hue_to_rgb(p: float, q: float, t: float) -> float:
        t = t % 1.0
        if t < 1/6:
            return p + (q - p) * 6 * t
        if t < 1/2:
            return q
        if t < 2/3:
            return p + (q - p) * (2/3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    hh = h / 360
    r = _hue_to_rgb(p, q, hh + 1/3)
    g = _hue_to_rgb(p, q, hh)
    b = _hue_to_rgb(p, q, hh - 1/3)
    return f"#{int(round(r*255)):02x}{int(round(g*255)):02x}{int(round(b*255)):02x}"


def derive_theme_from_seed(seed_hex: str, mode: str = "dark") -> dict:
    """Derive a full theme dict from one seed color + dark/light mode.

    Uses HSL math to spin a coherent palette around the seed's hue:
    secondary is the complementary hue, bg/surface share the seed's
    hue at low saturation (so the UI tints subtly toward the brand
    color), text is high-contrast against bg, and text_dim sits between
    them. The semantic colours (success/warn/danger) are fixed
    green/amber/red because their meaning trumps brand consistency.

    Returns a dict ready to pass as ``custom=`` to ``set_ui_theme``.
    """
    if mode not in ("dark", "light"):
        raise ValueError(f"mode must be 'dark' or 'light', got {mode!r}")

    h, s, _l = _hex_to_hsl(seed_hex)
    # Clamp primary saturation so pale seed colours still give a readable
    # secondary / text; saturations below ~0.3 produce bg-indistinguishable
    # surface tints.
    tinted_s = min(s, 0.15)  # used for bg/surface — low chroma tint

    # Secondary: complementary hue, full saturation of the seed so the
    # accent pops visibly against it.
    secondary = _hsl_to_hex((h + 180) % 360, s if s > 0 else 0.7, 0.55)

    if mode == "dark":
        bg = _hsl_to_hex(h, tinted_s, 0.08)
        surface = _hsl_to_hex(h, tinted_s, 0.14)
        text = _hsl_to_hex(h, tinted_s * 0.5, 0.92)
        text_dim = _hsl_to_hex(h, tinted_s * 0.5, 0.62)
        border = _hsl_to_hex(h, tinted_s, 0.22)
    else:  # light
        bg = _hsl_to_hex(h, tinted_s * 0.5, 0.98)
        surface = _hsl_to_hex(h, tinted_s * 0.5, 0.95)
        text = _hsl_to_hex(h, tinted_s, 0.08)
        text_dim = _hsl_to_hex(h, tinted_s, 0.42)
        border = _hsl_to_hex(h, tinted_s, 0.86)

    return {
        "color": {
            "primary":   seed_hex,
            "secondary": secondary,
            "bg":        bg,
            "surface":   surface,
            "text":      text,
            "text_dim":  text_dim,
            # Fixed semantic trio — a "danger" button needs to read red
            # regardless of the game's brand. Swap out in a custom={...}
            # follow-up if you disagree.
            "success":   "#22c55e",
            "warn":      "#f59e0b",
            "danger":    "#ef4444",
            "border":    border,
        },
        # Fonts / spacing / radius come from the dark_game defaults via
        # the normal theme materialization path, so callers who want
        # per-project type scale still set those independently.
    }


def _tokens_for(scene_path: str | Path | None) -> dict:
    """Locate tokens for the project enclosing ``scene_path``, falling
    back to the dark_game default when we can't find a project root.
    A resolver never fails on "no theme set" — it fails on "typo'd
    preset name", which is the real bug.
    """
    if scene_path is not None:
        project = _find_project_from_scene(scene_path)
        if project is not None:
            return get_ui_tokens(project)["resolved"]
    return _materialize_theme(BUILTIN_THEMES[_DEFAULT_THEME])

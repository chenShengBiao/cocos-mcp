"""Entrance / motion animation presets.

Each preset:

  1. Generates a ``.anim`` AnimationClip file via
     ``cocos.project.create_animation_clip`` (UUID'd asset that the
     build pipeline picks up automatically).
  2. Attaches ``cc.Animation`` to the target node with the new clip
     as default + play_on_load=True so it runs at scene start.
  3. For fades — ensures the node has a ``cc.UIOpacity`` component
     (the engine animates the UIOpacity's ``opacity`` field, not a
     node-level property; without this the fade animation silently
     does nothing).

Auto-locates the project root by walking up from the scene file to
``package.json``. Raises if the scene lives outside any Cocos project.

All timings are in seconds. Clips are named ``<preset>_<node_id>`` and
land under ``assets/animations/`` by default — pass ``rel_dir=`` to
override.
"""
from __future__ import annotations

from pathlib import Path

from ..project.ui_tokens import _find_project_from_scene


def _require_project(scene_path: str | Path) -> Path:
    """Either return the project root containing ``scene_path`` or raise
    a FileNotFoundError with an actionable message. Presets can't create
    the ``.anim`` asset without knowing where ``assets/`` lives."""
    p = _find_project_from_scene(scene_path)
    if p is None:
        raise FileNotFoundError(
            f"couldn't locate a Cocos project above {scene_path}. "
            "Animation presets need a package.json parent to place the "
            "generated .anim asset; move the scene under a project root "
            "or generate the clip manually with cocos_create_animation_clip."
        )
    return p


# WrapMode.Normal — play once + hold last keyframe. Default for entrance
# animations. WrapMode.Loop = 4 for continuous effects like pulse.
_WRAP_NORMAL = 1
_WRAP_LOOP = 4


def add_fade_in(scene_path: str | Path,
                node_id: int,
                duration: float = 0.3,
                delay: float = 0.0,
                rel_dir: str | None = None) -> dict:
    """Fade a node from fully transparent to fully opaque over ``duration``.

    Adds a ``cc.UIOpacity`` to the node (with initial opacity=0 so the
    first pre-play frame doesn't flash at full opacity) and a cc.Animation
    pointing at the new clip.

    ``delay`` adds a flat hold at opacity=0 before the ramp starts —
    useful for staggering multiple fade-ins on sibling nodes.

    Returns ``{clip_uuid, clip_path, anim_component_id, opacity_component_id}``.
    """
    from ..project import create_animation_clip
    from . import add_animation, add_ui_opacity

    project = _require_project(scene_path)

    # Keyframes: [0 → 0] [delay → 0] [delay+duration → 255]. The
    # redundant (0,0) + (delay,0) pair gives us the "hold" before the ramp.
    keyframes: list[dict] = []
    if delay > 0:
        keyframes.append({"time": 0.0, "value": 0})
        keyframes.append({"time": delay, "value": 0})
    else:
        keyframes.append({"time": 0.0, "value": 0})
    keyframes.append({"time": delay + duration, "value": 255})

    clip = create_animation_clip(
        project,
        clip_name=f"fade_in_{node_id}",
        duration=delay + duration,
        sample=60,
        tracks=[{"path": "", "property": "opacity", "keyframes": keyframes}],
        rel_dir=rel_dir,
        wrap_mode=_WRAP_NORMAL,
    )
    opacity_cid = add_ui_opacity(scene_path, node_id, opacity=0)
    anim_cid = add_animation(scene_path, node_id,
                             default_clip_uuid=clip["uuid"],
                             play_on_load=True,
                             clip_uuids=[clip["uuid"]])
    return {
        "clip_uuid": clip["uuid"],
        "clip_path": clip["path"],
        "anim_component_id": anim_cid,
        "opacity_component_id": opacity_cid,
    }


def add_slide_in(scene_path: str | Path,
                 node_id: int,
                 from_side: str = "bottom",
                 distance: float = 200.0,
                 duration: float = 0.4,
                 delay: float = 0.0,
                 rel_dir: str | None = None) -> dict:
    """Slide a node into position from off-screen.

    ``from_side``: ``"left"`` / ``"right"`` / ``"top"`` / ``"bottom"``
    — picks the axis and sign of the start offset.

    The end position is always the node's current _lpos, so call this
    AFTER positioning the node where you want it to end up. The clip
    animates toward (0,0,0) relative offset, i.e. it tweens the node
    back to whatever you set via add_node/set_node_position.

    Returns ``{clip_uuid, clip_path, anim_component_id}``.
    """
    from ..project import create_animation_clip
    from . import add_animation, get_object

    project = _require_project(scene_path)

    if from_side not in ("left", "right", "top", "bottom"):
        raise ValueError(
            f"from_side must be left/right/top/bottom, got {from_side!r}"
        )

    # Start offset in 2D scene coords. +x right, +y up.
    dx, dy = 0.0, 0.0
    if from_side == "left":
        dx = -distance
    elif from_side == "right":
        dx = distance
    elif from_side == "bottom":
        dy = -distance
    elif from_side == "top":
        dy = distance

    # Use the node's CURRENT _lpos as the end value. Cocos animates
    # absolute position, not offset — so if we hardcode [0,0,0] the
    # node snaps to scene origin when the clip ends. Read the pose
    # the user already set.
    obj = get_object(scene_path, node_id)
    cur_pos = obj.get("_lpos", {"x": 0, "y": 0, "z": 0})
    end_x, end_y, end_z = cur_pos.get("x", 0), cur_pos.get("y", 0), cur_pos.get("z", 0)
    start_x, start_y = end_x + dx, end_y + dy

    keyframes: list[dict] = []
    if delay > 0:
        keyframes.append({"time": 0.0, "value": [start_x, start_y, end_z]})
        keyframes.append({"time": delay, "value": [start_x, start_y, end_z]})
    else:
        keyframes.append({"time": 0.0, "value": [start_x, start_y, end_z]})
    keyframes.append({"time": delay + duration, "value": [end_x, end_y, end_z]})

    clip = create_animation_clip(
        project,
        clip_name=f"slide_in_{from_side}_{node_id}",
        duration=delay + duration,
        sample=60,
        tracks=[{"path": "", "property": "position", "keyframes": keyframes}],
        rel_dir=rel_dir,
        wrap_mode=_WRAP_NORMAL,
    )
    anim_cid = add_animation(scene_path, node_id,
                             default_clip_uuid=clip["uuid"],
                             play_on_load=True,
                             clip_uuids=[clip["uuid"]])
    return {
        "clip_uuid": clip["uuid"],
        "clip_path": clip["path"],
        "anim_component_id": anim_cid,
    }


def add_scale_in(scene_path: str | Path,
                 node_id: int,
                 from_scale: float = 0.0,
                 duration: float = 0.3,
                 delay: float = 0.0,
                 rel_dir: str | None = None) -> dict:
    """Pop a node in from ``from_scale`` to 1.0 over ``duration``.

    Typical values: 0.0 (invisible → full) or 0.5 (half-size grow).
    The clip animates all three axes uniformly so UI nodes don't skew.

    Returns {clip_uuid, clip_path, anim_component_id}.
    """
    from ..project import create_animation_clip
    from . import add_animation

    project = _require_project(scene_path)

    start_vec = [from_scale, from_scale, from_scale]
    end_vec = [1.0, 1.0, 1.0]
    keyframes: list[dict] = []
    if delay > 0:
        keyframes.append({"time": 0.0, "value": start_vec})
        keyframes.append({"time": delay, "value": start_vec})
    else:
        keyframes.append({"time": 0.0, "value": start_vec})
    keyframes.append({"time": delay + duration, "value": end_vec})

    clip = create_animation_clip(
        project,
        clip_name=f"scale_in_{node_id}",
        duration=delay + duration,
        sample=60,
        tracks=[{"path": "", "property": "scale", "keyframes": keyframes}],
        rel_dir=rel_dir,
        wrap_mode=_WRAP_NORMAL,
    )
    anim_cid = add_animation(scene_path, node_id,
                             default_clip_uuid=clip["uuid"],
                             play_on_load=True,
                             clip_uuids=[clip["uuid"]])
    return {
        "clip_uuid": clip["uuid"],
        "clip_path": clip["path"],
        "anim_component_id": anim_cid,
    }


def add_bounce_in(scene_path: str | Path,
                  node_id: int,
                  overshoot: float = 1.15,
                  duration: float = 0.5,
                  delay: float = 0.0,
                  rel_dir: str | None = None) -> dict:
    """Entrance with an overshoot — scale goes 0 → overshoot → 1.0.

    The 3-keyframe curve gives a springy "pop" feel without needing a
    proper easing curve (Cocos's RealCurve defaults to linear, so the
    overshoot keyframe IS the bounce). Tune ``overshoot`` 1.05-1.3 for
    subtle to exaggerated effect.

    Returns {clip_uuid, clip_path, anim_component_id}.
    """
    from ..project import create_animation_clip
    from . import add_animation

    project = _require_project(scene_path)

    # 60% of duration to the overshoot, 40% to settle back to 1.0.
    # This ratio comes from UX observation — any more settle time and
    # the "pop" feeling fades into a slow wobble.
    overshoot_time = (delay + duration) * 0.6
    if delay > 0:
        overshoot_time = delay + (duration * 0.6)

    keyframes: list[dict] = []
    if delay > 0:
        keyframes.append({"time": 0.0, "value": [0.0, 0.0, 0.0]})
        keyframes.append({"time": delay, "value": [0.0, 0.0, 0.0]})
    else:
        keyframes.append({"time": 0.0, "value": [0.0, 0.0, 0.0]})
    keyframes.append({"time": overshoot_time,
                      "value": [overshoot, overshoot, overshoot]})
    keyframes.append({"time": delay + duration, "value": [1.0, 1.0, 1.0]})

    clip = create_animation_clip(
        project,
        clip_name=f"bounce_in_{node_id}",
        duration=delay + duration,
        sample=60,
        tracks=[{"path": "", "property": "scale", "keyframes": keyframes}],
        rel_dir=rel_dir,
        wrap_mode=_WRAP_NORMAL,
    )
    anim_cid = add_animation(scene_path, node_id,
                             default_clip_uuid=clip["uuid"],
                             play_on_load=True,
                             clip_uuids=[clip["uuid"]])
    return {
        "clip_uuid": clip["uuid"],
        "clip_path": clip["path"],
        "anim_component_id": anim_cid,
    }


def add_pulse(scene_path: str | Path,
              node_id: int,
              strength: float = 0.08,
              period: float = 1.2,
              rel_dir: str | None = None) -> dict:
    """Looping subtle scale pulse (attention-grabber for idle UI).

    ``strength``: how much bigger at peak, relative to 1.0 (0.08 = 8%
    larger on pulse). Values above ~0.15 look anxious; keep subtle
    for production.
    ``period``: one full cycle in seconds. 1.0-1.5s reads as a
    relaxed heartbeat; below 0.5 feels panicked.

    Clip wraps LOOP, so attach and forget — the animation plays
    forever once the scene starts.

    Returns {clip_uuid, clip_path, anim_component_id}.
    """
    from ..project import create_animation_clip
    from . import add_animation

    project = _require_project(scene_path)

    peak = 1.0 + strength
    # Three keyframes spaced at 0 / half / full: 1.0 → peak → 1.0
    # gives a smooth ease in and out under the default linear curve.
    keyframes = [
        {"time": 0.0, "value": [1.0, 1.0, 1.0]},
        {"time": period / 2, "value": [peak, peak, peak]},
        {"time": period, "value": [1.0, 1.0, 1.0]},
    ]

    clip = create_animation_clip(
        project,
        clip_name=f"pulse_{node_id}",
        duration=period,
        sample=60,
        tracks=[{"path": "", "property": "scale", "keyframes": keyframes}],
        rel_dir=rel_dir,
        wrap_mode=_WRAP_LOOP,
    )
    anim_cid = add_animation(scene_path, node_id,
                             default_clip_uuid=clip["uuid"],
                             play_on_load=True,
                             clip_uuids=[clip["uuid"]])
    return {
        "clip_uuid": clip["uuid"],
        "clip_path": clip["path"],
        "anim_component_id": anim_cid,
    }


def add_shake(scene_path: str | Path,
              node_id: int,
              intensity: float = 10.0,
              duration: float = 0.3,
              axis: str = "x",
              rel_dir: str | None = None) -> dict:
    """One-shot position wobble. Useful for damage / error feedback.

    Ten keyframes across ``duration`` alternating ±intensity on the
    chosen axis then decaying to 0. No easing — linear interpolation
    between keyframes is what makes the shake read as jittery rather
    than smooth.

    ``axis``: "x" (horizontal, default — hit / error), "y" (vertical —
    stomp), or "both" (diagonal — explosion / big impact).

    Returns {clip_uuid, clip_path, anim_component_id}.
    """
    from ..project import create_animation_clip
    from . import add_animation, get_object

    project = _require_project(scene_path)

    if axis not in ("x", "y", "both"):
        raise ValueError(f"axis must be 'x', 'y', or 'both', got {axis!r}")

    # Read the node's current _lpos so the shake oscillates AROUND
    # its actual position instead of around (0,0,0).
    obj = get_object(scene_path, node_id)
    cur_pos = obj.get("_lpos", {"x": 0, "y": 0, "z": 0})
    bx, by, bz = cur_pos.get("x", 0), cur_pos.get("y", 0), cur_pos.get("z", 0)

    # 10 keyframes across the duration. Amplitude decays linearly so
    # the shake tapers out rather than stopping abruptly.
    n_keys = 10
    keyframes: list[dict] = []
    for i in range(n_keys):
        t = duration * i / (n_keys - 1)
        decay = 1.0 - (i / (n_keys - 1))  # 1.0 → 0.0
        # Alternate sign each frame for max jitter effect
        sign = 1 if i % 2 == 0 else -1
        dx = intensity * sign * decay if axis in ("x", "both") else 0
        dy = intensity * sign * decay if axis in ("y", "both") else 0
        keyframes.append({
            "time": t,
            "value": [bx + dx, by + dy, bz],
        })
    # Final keyframe guaranteed back at rest
    keyframes.append({"time": duration, "value": [bx, by, bz]})

    clip = create_animation_clip(
        project,
        clip_name=f"shake_{axis}_{node_id}",
        duration=duration,
        sample=60,
        tracks=[{"path": "", "property": "position", "keyframes": keyframes}],
        rel_dir=rel_dir,
        wrap_mode=_WRAP_NORMAL,
    )
    anim_cid = add_animation(scene_path, node_id,
                             default_clip_uuid=clip["uuid"],
                             play_on_load=True,
                             clip_uuids=[clip["uuid"]])
    return {
        "clip_uuid": clip["uuid"],
        "clip_path": clip["path"],
        "anim_component_id": anim_cid,
    }

"""AnimationClip (.anim) authoring.

Cocos Creator 3.x .anim files are JSON arrays in the same shape as
.scene / .prefab (object-per-index, cross-references via ``{"__id__": N}``).
The public ``create_animation_clip`` takes a simple list-of-tracks spec
and expands it into the verbose engine-expected structure via the three
private ``_build_*_track`` helpers.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..meta_util import write_meta
from ..uuid_util import new_uuid


def create_animation_clip(project_path: str | Path, clip_name: str,
                          duration: float = 1.0,
                          sample: int = 60,
                          tracks: list[dict] | None = None,
                          rel_dir: str | None = None,
                          uuid: str | None = None) -> dict:
    """Create a .anim AnimationClip file + meta.

    Args:
        clip_name: Name of the clip (e.g. "idle", "walk")
        duration: Clip duration in seconds
        sample: Frames per second
        tracks: List of track dicts. Each track:
            {
                "path": "NodeName",          # target node path (relative)
                "property": "position",       # "position" | "scale" | "rotation" | "color" | "opacity" | "active"
                "keyframes": [
                    {"time": 0.0, "value": [0, 0, 0]},
                    {"time": 0.5, "value": [100, 0, 0]},
                    {"time": 1.0, "value": [0, 0, 0]},
                ]
            }
            Values: position=[x,y,z], scale=[sx,sy,sz], rotation=[ez] (euler z degrees),
                    color=[r,g,b,a], opacity=0-255 (number), active=true/false

    Returns {path, rel_path, uuid}.
    """
    p = Path(project_path).expanduser().resolve()
    if rel_dir:
        base = rel_dir.lstrip("/")
        if not base.startswith("assets/"):
            base = f"assets/{base}"
    else:
        base = "assets/animations"

    dst_dir = p / base
    dst_dir.mkdir(parents=True, exist_ok=True)
    clip_path = dst_dir / f"{clip_name}.anim"

    clip_uuid = uuid or new_uuid()

    # Build Cocos Creator 3.x AnimationClip JSON
    # Cocos 3.x .anim is a JSON with specific structure
    anim_data = _build_anim_json(clip_name, duration, sample, tracks or [])

    with open(clip_path, "w") as f:
        json.dump(anim_data, f, indent=2)

    # Write meta
    meta = {
        "ver": "1.0.0",
        "importer": "animation-clip",
        "imported": True,
        "uuid": clip_uuid,
        "files": [".json"],
        "subMetas": {},
        "userData": {},
    }
    write_meta(clip_path, meta)

    return {
        "path": str(clip_path),
        "rel_path": str(clip_path.relative_to(p)),
        "uuid": clip_uuid,
    }


def _build_anim_json(name: str, duration: float, sample: int, tracks: list[dict]) -> list:
    """Build a Cocos Creator 3.x AnimationClip serialized JSON.

    The .anim file is a JSON array (same format as .scene/.prefab).
    """
    objects: list[dict] = []

    def push(obj):
        idx = len(objects)
        objects.append(obj)
        return idx

    # [0] cc.AnimationClip
    clip_idx = push({
        "__type__": "cc.AnimationClip",
        "_name": name,
        "_objFlags": 0,
        "_native": "",
        "sample": sample,
        "speed": 1,
        "wrapMode": 2,  # 2=Loop, 1=Normal, 0=Default
        "enableTrsBlending": False,
        "_duration": duration,
        "_hash": hash(name) & 0xFFFFFFFF,
        "_tracks": [],
        "_exoticAnimation": None,
        "_events": [],
    })

    # Build tracks
    track_refs = []
    for track in tracks:
        prop = track.get("property", "position")
        path = track.get("path", "")
        keyframes = track.get("keyframes", [])

        if prop == "position" or prop == "scale":
            t_idx = _build_vec3_track(objects, push, path, keyframes, "cc.animation.VectorTrack", 3)
        elif prop == "rotation":
            # Euler Z only for 2D
            t_idx = _build_float_track(objects, push, path, keyframes, "cc.animation.RealTrack")
        elif prop in ("opacity", "active"):
            t_idx = _build_float_track(objects, push, path, keyframes, "cc.animation.RealTrack")
        elif prop == "color":
            t_idx = _build_color_track(objects, push, path, keyframes)
        else:
            continue
        track_refs.append({"__id__": t_idx})

    objects[clip_idx]["_tracks"] = track_refs
    return objects


def _build_vec3_track(objects, push, path, keyframes, track_type, channels):
    """Build a VectorTrack with 2-3 channel curves."""
    # Simplified: store as a generic track with keyframe data
    # Cocos 3.x track format is complex; we use a simplified version
    # that the engine can still parse
    times = [kf["time"] for kf in keyframes]
    values = [kf["value"] for kf in keyframes]

    channels_data = []
    for ch in range(min(channels, 3)):
        curve_idx = push({
            "__type__": "cc.animation.RealCurve",
            "_times": times,
            "_values": [{"__type__": "cc.animation.RealKeyframeValue",
                         "interpolationMode": 2,  # LINEAR
                         "value": v[ch] if isinstance(v, (list, tuple)) and ch < len(v) else 0
                         } for v in values],
            "preExtrapolation": 1,
            "postExtrapolation": 1,
        })
        channels_data.append({"__id__": curve_idx})

    track_idx = push({
        "__type__": track_type,
        "_binding": {
            "__type__": "cc.animation.TrackBinding",
            "path": {
                "__type__": "cc.animation.TrackPath",
                "_paths": [
                    {"__type__": "cc.animation.HierarchyPath", "path": path},
                    {"__type__": "cc.animation.ComponentPath", "component": ""},
                    path.split("/")[-1] if "/" in path else "",
                ],
            },
        },
        "_channels": channels_data,
        "_nComponents": channels,
    })
    return track_idx


def _build_float_track(objects, push, path, keyframes, track_type):
    """Build a single-channel RealTrack."""
    times = [kf["time"] for kf in keyframes]
    values = [kf["value"] for kf in keyframes]

    curve_idx = push({
        "__type__": "cc.animation.RealCurve",
        "_times": times,
        "_values": [{"__type__": "cc.animation.RealKeyframeValue",
                     "interpolationMode": 2,
                     "value": v if isinstance(v, (int, float)) else (v[0] if isinstance(v, list) else 0)
                     } for v in values],
        "preExtrapolation": 1,
        "postExtrapolation": 1,
    })

    track_idx = push({
        "__type__": track_type,
        "_binding": {
            "__type__": "cc.animation.TrackBinding",
            "path": {
                "__type__": "cc.animation.TrackPath",
                "_paths": [
                    {"__type__": "cc.animation.HierarchyPath", "path": path},
                ],
            },
        },
        "_channel": {"__id__": curve_idx},
    })
    return track_idx


def _build_color_track(objects, push, path, keyframes):
    """Build a ColorTrack with 4 channel curves (r,g,b,a)."""
    times = [kf["time"] for kf in keyframes]
    values = [kf["value"] for kf in keyframes]

    channels_data = []
    for ch in range(4):
        curve_idx = push({
            "__type__": "cc.animation.RealCurve",
            "_times": times,
            "_values": [{"__type__": "cc.animation.RealKeyframeValue",
                         "interpolationMode": 2,
                         "value": v[ch] if isinstance(v, (list, tuple)) and ch < len(v) else 255
                         } for v in values],
            "preExtrapolation": 1,
            "postExtrapolation": 1,
        })
        channels_data.append({"__id__": curve_idx})

    track_idx = push({
        "__type__": "cc.animation.ColorTrack",
        "_binding": {
            "__type__": "cc.animation.TrackBinding",
            "path": {
                "__type__": "cc.animation.TrackPath",
                "_paths": [
                    {"__type__": "cc.animation.HierarchyPath", "path": path},
                ],
            },
        },
        "_channels": channels_data,
    })
    return track_idx

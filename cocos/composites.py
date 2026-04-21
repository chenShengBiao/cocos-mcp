"""Cross-cutting composites — single-call shorthands for multi-call sequences.

Every function here is a pure wrapper over the per-layer primitives
(``cocos.project``, ``cocos.scene_builder``, ``cocos.uuid_util``). They
exist because the dogfood run showed the same 3–4-call dance repeated
for every script attached, every UI button created, every physics body
wired — enough that the bookkeeping drift (forgetting to compress a
UUID, losing track of which id belongs to which node, re-saving the
wrong scene path) became the dominant source of agent error.

Keeping these functions in one module rather than scattered across the
``tools/*.py`` files lets ``test_composites.py`` exercise them without
spinning up an MCP server, and lets callers reach them from Python
directly.
"""
from __future__ import annotations

from pathlib import Path

from . import project as cp
from . import scene_builder as sb
from . import uuid_util as uu


def add_and_attach_script(project_path: str | Path,
                          rel_path: str,
                          source: str,
                          scene_path: str | Path,
                          node_id: int,
                          props: dict | None = None,
                          uuid: str | None = None) -> dict:
    """Write a TS script + attach it to a scene node in one call.

    Replaces the 3-step dance agents ran repeatedly on the dogfood run::

        r = cocos_add_script(project, "Foo", source)
        short = cocos_compress_uuid(r["uuid"])
        cid = cocos_add_script(scene, node_id, short, props=...)

    with::

        r = cocos_add_and_attach_script(project, "Foo", source,
                                        scene, node_id, props=...)

    The two ``cocos_add_script`` overloads (the project-level script
    file writer vs the scene-level component attacher) sharing a name
    was the main trip-hazard here. This composite names the intent.

    Parameters mirror the two underlying primitives:

    * ``project_path`` / ``rel_path`` / ``source`` — where the .ts lives.
      ``rel_path`` follows the same auto-prefix rules as ``add_script``
      (bare names get ``assets/scripts/`` prepended; ``.ts`` appended if
      absent).
    * ``scene_path`` / ``node_id`` — the scene (or prefab) file and the
      target node's array index.
    * ``props`` — forwarded verbatim to the scene-level attach. Pass
      ``{"__id__": N}`` for node/component refs and ``{"__uuid__": "..."}``
      for asset refs; bare ints stay as ints.
    * ``uuid`` — optional override for the script's main UUID. When
      omitted and the .ts.meta already exists, the existing UUID is
      preserved (see Bug A fix in ``project.assets.add_script``).

    Returns a dict with both forms of the script UUID so the caller can
    immediately reference it from other places (e.g. linking a second
    component's @property at the same UUID)::

        {
          "script_path": "/abs/path/to/Foo.ts",
          "rel_path":    "assets/scripts/Foo.ts",
          "uuid_standard":   "5372d6f5-...",
          "uuid_compressed": "5372db1cH...",
          "component_id":    <int, the attached component's scene index>,
          "created":         <bool, False iff the .ts.meta was preserved>,
        }
    """
    script_info = cp.add_script(project_path, rel_path, source, uuid=uuid)
    compressed = uu.compress_uuid(script_info["uuid"])
    component_id = sb.add_script(scene_path, node_id, compressed, props=props)
    return {
        "script_path": script_info["path"],
        "rel_path": script_info["rel_path"],
        "uuid_standard": script_info["uuid"],
        "uuid_compressed": compressed,
        "component_id": component_id,
        "created": script_info["created"],
    }


_ALLOWED_SHAPES: frozenset[str] = frozenset({"box", "circle", "polygon"})


def add_physics_body2d(scene_path: str | Path,
                       node_id: int,
                       shape: str = "box",
                       body_type: int = 2,
                       # RigidBody2D tunables
                       gravity_scale: float = 1.0,
                       linear_damping: float = 0.0,
                       angular_damping: float = 0.0,
                       fixed_rotation: bool = False,
                       bullet: bool = False,
                       awake_on_load: bool = True,
                       # Shared collider tunables
                       density: float = 1.0,
                       friction: float = 0.2,
                       restitution: float = 0.0,
                       is_sensor: bool = False,
                       tag: int = 0,
                       offset_x: float = 0.0,
                       offset_y: float = 0.0,
                       # Shape-specific (only the relevant keys get read)
                       width: float = 100.0,
                       height: float = 100.0,
                       radius: float = 50.0,
                       points: list[list[float]] | None = None) -> dict:
    """Attach a RigidBody2D + shape collider in one call.

    The dogfood run had "RigidBody2D + Box/Circle/Polygon Collider" as
    one of the most-repeated sequences — every Bird, every Pipe, every
    Ground slab. This folds the 2 calls into 1 and returns both ids so
    the caller can immediately link them or set them as a joint target.

    Parameters:

    * ``shape`` — one of ``"box"`` / ``"circle"`` / ``"polygon"``.
      Picks which collider type to attach; the irrelevant *_tunables
      are ignored. Raises ``ValueError`` on unknown shape rather than
      silently attaching a default — the caller almost certainly meant
      something specific.
    * ``body_type`` — ``0=Static``, ``1=Kinematic``, ``2=Dynamic``
      (default). Matches ``cocos_constants.rigidbody2d_type``.
    * Common RigidBody2D knobs: ``gravity_scale``, ``linear_damping``,
      ``angular_damping``, ``fixed_rotation``, ``bullet``, ``awake_on_load``.
    * Common collider knobs: ``density`` / ``friction`` / ``restitution``
      / ``is_sensor`` / ``tag`` / ``offset_x`` / ``offset_y``.
    * Shape-specific:
        - box:     ``width`` × ``height`` (defaults 100×100)
        - circle:  ``radius`` (default 50)
        - polygon: ``points`` — list of ``[x, y]`` vertex pairs
                   (defaults to a 100×100 square — same as
                   ``add_polygon_collider2d``).

    Returns::

        {"rigidbody_id": <int>, "collider_id": <int>, "shape": "box"}
    """
    if shape not in _ALLOWED_SHAPES:
        raise ValueError(
            f"unknown shape {shape!r}; expected one of {sorted(_ALLOWED_SHAPES)}"
        )
    rb_id = sb.add_rigidbody2d(
        scene_path, node_id,
        body_type=body_type,
        gravity_scale=gravity_scale,
        linear_damping=linear_damping,
        angular_damping=angular_damping,
        fixed_rotation=fixed_rotation,
        bullet=bullet,
        awake_on_load=awake_on_load,
    )
    col_id: int
    if shape == "box":
        col_id = sb.add_box_collider2d(
            scene_path, node_id,
            width=width, height=height,
            offset_x=offset_x, offset_y=offset_y,
            density=density, friction=friction, restitution=restitution,
            is_sensor=is_sensor, tag=tag,
        )
    elif shape == "circle":
        col_id = sb.add_circle_collider2d(
            scene_path, node_id,
            radius=radius,
            offset_x=offset_x, offset_y=offset_y,
            density=density, friction=friction, restitution=restitution,
            is_sensor=is_sensor, tag=tag,
        )
    else:  # polygon — guarded by the frozenset above
        col_id = sb.add_polygon_collider2d(
            scene_path, node_id,
            points=points,
            density=density, friction=friction, restitution=restitution,
            is_sensor=is_sensor, tag=tag,
        )
    return {
        "rigidbody_id": rb_id,
        "collider_id": col_id,
        "shape": shape,
    }


def add_button_with_label(scene_path: str | Path,
                          parent_id: int,
                          label_text: str,
                          width: float = 200.0,
                          height: float = 60.0,
                          name: str | None = None,
                          pos_x: float = 0.0,
                          pos_y: float = 0.0,
                          font_size: int = 32,
                          # Background sprite (optional)
                          sprite_frame_uuid: str | None = None,
                          # Label styling (presets)
                          label_color_preset: str | None = None,
                          label_size_preset: str | None = None,
                          bg_color_preset: str | None = None,
                          # Button behavior knobs
                          transition: int = 2,
                          zoom_scale: float = 1.1,
                          click_events: list[dict] | None = None) -> dict:
    """Create a button node with a child Label — the single most-
    repeated UI sequence agents ran during the dogfood run.

    Structurally produces::

        Btn (Node, UITransform, Sprite?, Button)
         └── Label (Node, UITransform, Label)

    The button is clickable (``cc.Button`` with ``transition=2`` /
    scale zoom by default) and the label is a separate child so
    designers can re-skin the background (via ``sprite_frame_uuid``)
    without disturbing the label's content. This matches Cocos Creator
    wizard-generated buttons.

    Key knobs:

    * ``label_text`` — the text to show. Required positional arg
      because no other default makes sense.
    * ``width`` / ``height`` — button size. Label sizes itself to the
      same box so text is centered via UITransform anchor.
    * ``sprite_frame_uuid`` — optional background sprite. When ``None``
      the button renders without a background sprite (a transparent
      hitbox) — Graphics-only styling via a later ``add_sprite`` /
      ``add_graphics`` call works the same as before.
    * ``label_color_preset`` / ``label_size_preset`` / ``bg_color_preset``
      — design-token lookups (theme-aware). Pass ``"primary"``,
      ``"title"``, ``"bg"``, etc. Missing presets fall back through
      the theme's default.
    * ``click_events`` — forward verbatim to ``add_button``. Build via
      ``cocos_make_click_event`` before calling.

    Returns::

        {
          "button_node_id":  <int>,   # top-level node
          "label_node_id":   <int>,   # child label node
          "button_component_id": <int>,  # cc.Button
          "label_component_id":  <int>,  # cc.Label
          "sprite_component_id": <int|None>,  # cc.Sprite if sprite_frame_uuid set
        }
    """
    # Button node
    btn_node = sb.add_node(
        scene_path, parent_id,
        name=name or f"Btn_{label_text[:10] or 'text'}",
        lpos=(pos_x, pos_y, 0),
    )
    sb.add_uitransform(scene_path, btn_node, width, height)
    sprite_cid: int | None = None
    if sprite_frame_uuid is not None:
        sprite_cid = sb.add_sprite(
            scene_path, btn_node,
            sprite_frame_uuid=sprite_frame_uuid,
            color_preset=bg_color_preset,
        )
    elif bg_color_preset is not None:
        # Color-only background: attach a Sprite without a frame so the
        # preset still gets applied (cc.Sprite with no _spriteFrame
        # renders as the _color alone).
        sprite_cid = sb.add_sprite(scene_path, btn_node, color_preset=bg_color_preset)

    button_cid = sb.add_button(
        scene_path, btn_node,
        transition=transition, zoom_scale=zoom_scale,
        click_events=click_events,
    )

    # Child Label node — same box, anchored centered so the text is
    # readable even if the parent button is later widget-stretched.
    label_node = sb.add_node(scene_path, btn_node, name="Label")
    sb.add_uitransform(scene_path, label_node, width, height)
    label_cid = sb.add_label(
        scene_path, label_node, text=label_text, font_size=font_size,
        color_preset=label_color_preset, size_preset=label_size_preset,
    )

    return {
        "button_node_id": btn_node,
        "label_node_id": label_node,
        "button_component_id": button_cid,
        "label_component_id": label_cid,
        "sprite_component_id": sprite_cid,
    }

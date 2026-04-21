"""UI widget components — buttons, layouts, text, sprites variants, events.

Most of these are thin wrappers over ``add_component`` that pick sensible
defaults for the component's engine-specific field names (``_N$barSprite``,
``_fillType``, ``_layoutType``, ...). They're split out of ``__init__.py``
so the core scene-lifecycle file stays under 700 lines.

``make_event_handler`` and ``make_click_event`` build the serialized event
handler dicts that Button/ScrollView/Toggle/Slider/EditBox consume — they
don't mutate any scene file on their own.

The late import of ``add_component`` inside each function avoids a load-time
cycle with ``__init__.py`` (which re-exports from this module).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._helpers import (
    _attach_component,
    _color,
    _load_scene,
    _make_sprite,
    _nid,
    _ref,
    _save_scene,
    _vec2,
)


# ----------- event handler builders -----------

def make_event_handler(target_node_id: int, component_name: str, handler: str,
                       custom_data: str = "") -> dict:
    """Build a serialized cc.EventHandler for any component event binding.

    Works with: ScrollView.scrollEvents, Toggle.checkEvents,
    Slider.slideEvents, EditBox.editingDidBegan/editingReturn, etc.

    Same format as cc.ClickEvent but uses cc.EventHandler type.
    """
    return {
        "__type__": "cc.EventHandler",
        "target": _ref(target_node_id),
        "_componentId": "",
        "component": component_name,
        "handler": handler,
        "customEventData": custom_data,
    }


def make_click_event(target_node_id: int, component_name: str, handler: str,
                     custom_data: str = "") -> dict:
    """Build a serialized cc.ClickEvent for Button.clickEvents.

    Args:
        target_node_id: The node that holds the script component (array index)
        component_name: The @ccclass name (e.g. "GameManager")
        handler: The method name to call (e.g. "onStartClick")
        custom_data: Optional string passed to the handler

    Example::

        evt = make_click_event(gm_node_id, "GameManager", "onStartClick")
        add_button(scene, btn_node, click_events=[evt])
    """
    return {
        "__type__": "cc.ClickEvent",
        "target": _ref(target_node_id),
        "_componentId": "",
        "component": component_name,
        "handler": handler,
        "customEventData": custom_data,
    }


def _serialize_events(s: list, events: list[dict] | None) -> list:
    """Serialize event handler dicts into scene array, return list of refs."""
    if not events:
        return []
    refs = []
    for evt in events:
        s.append(evt)
        refs.append(_ref(len(s) - 1))
    return refs


# ----------- widgets -----------

def _derive_button_states(base_rgba: tuple) -> tuple[tuple, tuple, tuple]:
    """From a primary button color, derive hover (slightly lighter),
    pressed (slightly darker), and disabled (desaturated gray) colors.

    Keeps the feel consistent — three hand-picked greys would jar against
    a theme-coloured primary. Multipliers below are eyeballed against the
    bundled themes; they don't aim for strict WCAG ratios."""
    r, g, b = base_rgba[0], base_rgba[1], base_rgba[2]
    a = base_rgba[3] if len(base_rgba) > 3 else 255

    def _clamp(v: int) -> int:
        return max(0, min(255, v))

    hover = (_clamp(int(r * 1.12)), _clamp(int(g * 1.12)), _clamp(int(b * 1.12)), a)
    pressed = (_clamp(int(r * 0.78)), _clamp(int(g * 0.78)), _clamp(int(b * 0.78)), a)
    # Disabled: gray derived from the primary's luminance, so dark and
    # light themes both produce a sensible gray at the same step.
    luma = int(0.299 * r + 0.587 * g + 0.114 * b)
    gray = _clamp(int(luma * 0.55 + 60))
    disabled = (gray, gray, gray, a)
    return hover, pressed, disabled


def add_button(scene_path: str | Path, node_id: int,
               transition: int = 2, zoom_scale: float = 1.1,
               normal_color: tuple = (255, 255, 255, 255),
               hover_color: tuple = (211, 211, 211, 255),
               pressed_color: tuple = (150, 150, 150, 255),
               disabled_color: tuple = (124, 124, 124, 255),
               click_events: list[dict] | None = None,
               color_preset: str | None = None) -> int:
    """Attach cc.Button. transition: 0=NONE, 1=COLOR, 2=SCALE, 3=SPRITE.

    Use ``make_click_event()`` to build entries for ``click_events``.

    ``color_preset`` (e.g. ``"primary"``, ``"secondary"``, ``"danger"``)
    sets ``normal_color`` from the project's UI theme AND derives
    matching ``hover`` / ``pressed`` / ``disabled`` shades (explicit
    values for those still win if also passed).
    """
    if color_preset is not None:
        from ..project.ui_tokens import resolve_color
        normal_color = resolve_color(scene_path, color_preset,
                                     alpha=normal_color[3] if len(normal_color) > 3 else 255)
        # Only auto-derive states when caller didn't pin them explicitly.
        # A caller passing e.g. hover_color=... alongside color_preset means
        # "preset for normal, but I want a specific hover" — respect that.
        auto_hover, auto_pressed, auto_disabled = _derive_button_states(normal_color)
        if hover_color == (211, 211, 211, 255):
            hover_color = auto_hover
        if pressed_color == (150, 150, 150, 255):
            pressed_color = auto_pressed
        if disabled_color == (124, 124, 124, 255):
            disabled_color = auto_disabled

    s = _load_scene(scene_path)
    # Build click events — they are inline objects in the scene array
    serialized_events = []
    if click_events:
        for evt in click_events:
            s.append(evt)
            serialized_events.append(_ref(len(s) - 1))

    # Cocos 3.8 serializes Button's getter/setter fields under their
    # underscore-prefixed backing names (see button.ts). Pre-audit we
    # wrote `transition`/`zoomScale`/`duration` and Cocos 2.x `_N$` prefixed
    # colors — all silently dropped at deserialization, so every button
    # ran with engine defaults (SCALE transition, 1.2× zoom, white colors).
    obj = {
        "__type__": "cc.Button",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("btn"),
        "target": _ref(node_id),  # target = self node (required for SCALE transition)
        "clickEvents": serialized_events,  # public @serializable — bare name
        "_interactable": True,
        "_transition": transition,
        "_zoomScale": zoom_scale,
        "_duration": 0.1,
        "_normalColor": _color(*normal_color),
        "_hoverColor": _color(*hover_color),
        "_pressedColor": _color(*pressed_color),
        "_disabledColor": _color(*disabled_color),
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_layout(scene_path: str | Path, node_id: int,
               layout_type: int = 1, spacing_x: float = 0, spacing_y: float = 0,
               padding_top: float = 0, padding_bottom: float = 0,
               padding_left: float = 0, padding_right: float = 0,
               resize_mode: int = 1,
               h_direction: int = 0, v_direction: int = 1) -> int:
    """Attach cc.Layout. layout_type: 0=NONE, 1=HORIZONTAL, 2=VERTICAL, 3=GRID.

    Cocos 3.x serializes Layout's protected fields with a plain
    underscore prefix; ``_N$`` was the 2.x-mangled form and is ignored
    in 3.8. Pre-audit, this tool was emitting ``_N$`` keys and the
    Layout ran with default spacing/padding/direction regardless of
    the caller's config.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.Layout", {
        "_layoutType": layout_type,
        "_resizeMode": resize_mode,
        "_spacingX": spacing_x,
        "_spacingY": spacing_y,
        "_paddingTop": padding_top,
        "_paddingBottom": padding_bottom,
        "_paddingLeft": padding_left,
        "_paddingRight": padding_right,
        "_horizontalDirection": h_direction,
        "_verticalDirection": v_direction,
    })


def add_progress_bar(scene_path: str | Path, node_id: int,
                     bar_sprite_id: int | None = None,
                     mode: int = 0, total_length: float = 100,
                     progress: float = 1.0, reverse: bool = False) -> int:
    """Attach cc.ProgressBar. mode: 0=HORIZONTAL, 1=VERTICAL, 2=FILLED.

    All fields are protected in the 3.8 engine source — emit the
    underscore-prefixed names. The bar_sprite ref uses ``_barSprite``
    (``_N$barSprite`` was the 2.x mangled form).
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {
        "_mode": mode,
        "_totalLength": total_length,
        "_progress": progress,
        "_reverse": reverse,
    }
    if bar_sprite_id is not None:
        props["_barSprite"] = _ref(bar_sprite_id)
    return add_component(scene_path, node_id, "cc.ProgressBar", props)


def add_scroll_view(scene_path: str | Path, node_id: int,
                    content_id: int | None = None,
                    horizontal: bool = False, vertical: bool = True,
                    inertia: bool = True, brake: float = 0.75,
                    elastic: bool = True, bounce_duration: float = 0.23,
                    scroll_events: list[dict] | None = None) -> int:
    """Attach cc.ScrollView. scroll_events: list from make_event_handler().

    Public @serializable fields (``horizontal``/``vertical``/``inertia``
    /``brake``/``elastic``/``bounceDuration``/``scrollEvents``) stay
    bare. The ``content`` ref is the backing ``_content`` field —
    pre-audit we wrote ``content`` which the engine ignored, leaving
    the scroll area without any content bound.
    """
    s = _load_scene(scene_path)
    ser_events = _serialize_events(s, scroll_events)
    obj: dict[str, Any] = {
        "__type__": "cc.ScrollView",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("scv"),
        # Public @serializable — bare names.
        "horizontal": horizontal,
        "vertical": vertical,
        "inertia": inertia,
        "brake": brake,
        "elastic": elastic,
        "bounceDuration": bounce_duration,
        "scrollEvents": ser_events,
    }
    if content_id is not None:
        obj["_content"] = _ref(content_id)
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_toggle(scene_path: str | Path, node_id: int,
               is_checked: bool = False, transition: int = 2,
               check_events: list[dict] | None = None) -> int:
    """Attach cc.Toggle. check_events: list from make_event_handler().

    Toggle extends Button, so inherits ``_transition`` /
    ``_interactable`` with underscore prefixes. Its own backing field
    ``_isChecked`` is protected too. ``checkEvents`` (public) and
    ``target`` (from ComponentEventHandler) stay bare.
    """
    s = _load_scene(scene_path)
    ser_events = _serialize_events(s, check_events)
    obj = {
        "__type__": "cc.Toggle",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("tgl"),
        "target": _ref(node_id),
        "checkEvents": ser_events,
        "_interactable": True,
        "_transition": transition,
        "_isChecked": is_checked,
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_editbox(scene_path: str | Path, node_id: int,
                placeholder: str = "Enter text...",
                max_length: int = -1, input_mode: int = 6,
                return_type: int = 0,
                editing_did_began: list[dict] | None = None,
                editing_did_ended: list[dict] | None = None,
                editing_return: list[dict] | None = None,
                text_changed: list[dict] | None = None) -> int:
    """Attach cc.EditBox. All event params accept lists from make_event_handler().

    The engine's ``_placeholderLabel`` / ``_textLabel`` fields are refs
    to child Label nodes (set up at runtime if omitted). Event-handler
    arrays (editingDidBegan, editingDidEnded, editingReturn,
    textChanged) are public @serializable — kept bare. Other config
    fields (maxLength, inputMode, returnType) are protected — emit
    with underscore prefix.

    The ``placeholder=`` parameter is kept for API stability but its
    string is no longer written to the scene; Cocos 3.8 reads
    placeholder text from a child Label via ``_placeholderLabel``, not
    a direct string field. Configure placeholder content via the
    child node after attach.
    """
    s = _load_scene(scene_path)
    # Swallow the parameter for backward API compatibility without
    # emitting a field the engine ignores.
    del placeholder
    obj = {
        "__type__": "cc.EditBox",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("edb"),
        # Public @serializable — bare names.
        "editingDidBegan": _serialize_events(s, editing_did_began),
        "editingDidEnded": _serialize_events(s, editing_did_ended),
        "editingReturn": _serialize_events(s, editing_return),
        "textChanged": _serialize_events(s, text_changed),
        # Protected @serializable — underscore prefix.
        "_string": "",
        "_maxLength": max_length,
        "_inputMode": input_mode,
        "_returnType": return_type,
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_slider(scene_path: str | Path, node_id: int,
               direction: int = 0, progress: float = 0.5,
               slide_events: list[dict] | None = None) -> int:
    """Attach cc.Slider. slide_events: list from make_event_handler().

    Engine source uses private underscore-prefixed ``_direction`` /
    ``_progress`` backing fields; ``slideEvents`` is public.
    """
    s = _load_scene(scene_path)
    ser_events = _serialize_events(s, slide_events)
    obj = {
        "__type__": "cc.Slider",
        "_name": "", "_objFlags": 0,
        "node": _ref(node_id), "_enabled": True, "__prefab": None,
        "_id": _nid("sld"),
        "slideEvents": ser_events,  # public @serializable
        "_direction": direction,
        "_progress": progress,
    }
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


# ----------- mask / richtext -----------

def add_mask(scene_path: str | Path, node_id: int,
             mask_type: int = 0, inverted: bool = False,
             segments: int = 64) -> int:
    """Attach cc.Mask. mask_type: 0=RECT, 1=ELLIPSE, 2=GRAPHICS_STENCIL, 3=SPRITE_STENCIL."""
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.Mask", {
        "_type": mask_type,
        "_inverted": inverted,
        "_segments": segments,
    })


def add_richtext(scene_path: str | Path, node_id: int,
                 text: str = "<b>Hello</b>",
                 font_size: int = 40,
                 max_width: float = 0,
                 line_height: float = 40,
                 horizontal_align: int = 0,
                 size_preset: str | None = None) -> int:
    """Attach cc.RichText. Supports <b>, <i>, <color>, <size>, <img> tags.

    ``size_preset`` (``"title"``/``"heading"``/``"body"``/``"caption"``)
    overrides ``font_size`` and sets ``line_height`` to ~1.25× of it for
    a readable default. Explicit ``font_size`` / ``line_height`` args
    take precedence when also given.
    """
    if size_preset is not None:
        from ..project.ui_tokens import resolve_size
        resolved = resolve_size(scene_path, size_preset)
        # Only override when caller didn't hand-pick — mirrors add_button.
        if font_size == 40:
            font_size = resolved
        if line_height == 40:
            line_height = int(resolved * 1.25)
    # RichText field names (from cocos/2d/components/rich-text.ts):
    # every @serializable is protected with underscore prefix — so
    # ``_string`` / ``_fontSize`` / ``_maxWidth`` / ``_horizontalAlign``
    # / ``_handleTouchEvent`` all need the underscore. Pre-audit we
    # wrote the bare names and the RichText silently rendered its
    # default '<color=#00ff00>Rich</color>...' placeholder.
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.RichText", {
        "_lineHeight": line_height,
        "_string": text,
        "_fontSize": font_size,
        "_maxWidth": max_width,
        "_horizontalAlign": horizontal_align,
        "_handleTouchEvent": True,
    })


# ----------- sprite variants -----------

def add_sliced_sprite(scene_path: str | Path, node_id: int,
                      sprite_frame_uuid: str | None = None,
                      color: tuple = (255, 255, 255, 255)) -> int:
    """Attach cc.Sprite with type=SLICED (9-slice).

    The sprite stretches the center while keeping corners fixed.
    Set border sizes in the spriteFrame meta's borderTop/Bottom/Left/Right.
    """
    s = _load_scene(scene_path)
    obj = _make_sprite(node_id, sprite_frame_uuid, size_mode=0, color=color)
    obj["_type"] = 1  # SLICED
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_tiled_sprite(scene_path: str | Path, node_id: int,
                     sprite_frame_uuid: str | None = None,
                     color: tuple = (255, 255, 255, 255)) -> int:
    """Attach cc.Sprite with type=TILED (repeating pattern)."""
    s = _load_scene(scene_path)
    obj = _make_sprite(node_id, sprite_frame_uuid, size_mode=0, color=color)
    obj["_type"] = 2  # TILED
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


def add_filled_sprite(scene_path: str | Path, node_id: int,
                      sprite_frame_uuid: str | None = None,
                      fill_type: int = 0, fill_center: tuple = (0.5, 0.5),
                      fill_start: float = 0, fill_range: float = 1.0,
                      color: tuple = (255, 255, 255, 255)) -> int:
    """Attach cc.Sprite with type=FILLED (radial/horizontal/vertical fill).

    fill_type: 0=HORIZONTAL, 1=VERTICAL, 2=RADIAL
    fill_start: 0~1 fill starting position
    fill_range: 0~1 fill amount (useful for cooldown timers)
    fill_center: center point for RADIAL fill
    """
    s = _load_scene(scene_path)
    obj = _make_sprite(node_id, sprite_frame_uuid, size_mode=0, color=color)
    obj["_type"] = 3  # FILLED
    obj["_fillType"] = fill_type
    obj["_fillCenter"] = _vec2(*fill_center)
    obj["_fillStart"] = fill_start
    obj["_fillRange"] = fill_range
    cid = _attach_component(s, node_id, obj)
    _save_scene(scene_path, s)
    return cid


# ----------- compact utility widgets -----------

def add_ui_opacity(scene_path: str | Path, node_id: int, opacity: int = 255) -> int:
    """Attach cc.UIOpacity. Controls node transparency (0=invisible, 255=opaque).

    Essential for fade-in/out animations via tween:
      tween(node.getComponent(UIOpacity)).to(0.5, {opacity: 0}).start()

    Engine source backs ``opacity`` with protected ``_opacity`` — JSON
    key has the underscore.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.UIOpacity", {
        "_opacity": opacity,
    })


def add_block_input_events(scene_path: str | Path, node_id: int) -> int:
    """Attach cc.BlockInputEvents. Prevents touch/mouse events from passing through.

    Put this on a fullscreen overlay node to block clicks on nodes behind it.
    Typical use: modal dialog backdrop, loading screen.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.BlockInputEvents", {})


def add_safe_area(scene_path: str | Path, node_id: int) -> int:
    """Attach cc.SafeArea. Auto-adjusts node to fit within the device safe area.

    Essential for mobile games on iPhone (notch) / Android (cutout).
    Usually placed on the root UI node.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.SafeArea", {})


def add_page_view(scene_path: str | Path, node_id: int,
                  content_id: int | None = None,
                  direction: int = 0,
                  scroll_threshold: float = 0.5,
                  page_turning_speed: float = 0.3,
                  indicator_id: int | None = None,
                  auto_page_turning_threshold: float = 100) -> int:
    """Attach cc.PageView (swipeable page container).

    direction: 0=Horizontal, 1=Vertical.
    Used for: tutorials, card galleries, level select screens.
    """
    from cocos.scene_builder import add_component
    # PageView extends ScrollView — inherits public @serializable
    # horizontal/vertical/inertia/elastic/bounceDuration. Its own
    # tunables (_direction, _scrollThreshold, _pageTurningEventTiming,
    # _indicator, _sizeMode) are protected with underscore prefix.
    # Public @serializable additions: pageTurningSpeed,
    # autoPageTurningThreshold.
    props: dict = {
        "inertia": True,
        "elastic": True,
        "bounceDuration": 0.23,
        "pageTurningSpeed": page_turning_speed,
        "autoPageTurningThreshold": auto_page_turning_threshold,
        "_direction": direction,
        "_scrollThreshold": scroll_threshold,
    }
    if content_id is not None:
        props["_content"] = {"__id__": content_id}  # inherited from ScrollView
    if indicator_id is not None:
        props["_indicator"] = {"__id__": indicator_id}
    return add_component(scene_path, node_id, "cc.PageView", props)


def add_toggle_container(scene_path: str | Path, node_id: int,
                         allow_switch_off: bool = False) -> int:
    """Attach cc.ToggleContainer (radio button group).

    Child Toggle nodes are mutually exclusive — only one can be checked at a time.
    Set allow_switch_off=True to allow all unchecked.

    Backing field is protected ``_allowSwitchOff``.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.ToggleContainer", {
        "_allowSwitchOff": allow_switch_off,
    })


def add_motion_streak(scene_path: str | Path, node_id: int,
                      fade_time: float = 1.0,
                      min_seg: float = 1,
                      stroke: float = 64,
                      color: tuple = (255, 255, 255, 255),
                      fast_mode: bool = False) -> int:
    """Attach cc.MotionStreak (trail/streak effect behind moving objects).

    Used for: sword trails, shooting stars, finger swipe effects.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.MotionStreak", {
        "_fadeTime": fade_time,
        "_minSeg": min_seg,
        "_stroke": stroke,
        "_color": _color(*color),
        "_fastMode": fast_mode,
    })


# ----------- WebView -----------

def add_webview(scene_path: str | Path, node_id: int,
                url: str = "https://cocos.com") -> int:
    """Attach cc.WebView — embedded browser pane.

    Useful for in-game ToS pages, activity pages, and web-based ad networks.
    Default URL matches the engine's own default. The engine's serialized
    shape is intentionally sparse — field count will grow as more platforms
    gain WebView features; for now only _url + empty events list.
    """
    from cocos.scene_builder import add_component
    return add_component(scene_path, node_id, "cc.WebView", {
        "_url": url,
        "webviewEvents": [],
    })


# ----------- ScrollBar -----------

SCROLLBAR_HORIZONTAL = 0
SCROLLBAR_VERTICAL = 1


def add_scroll_bar(scene_path: str | Path, node_id: int,
                   handle_sprite_id: int | None = None,
                   scroll_view_id: int | None = None,
                   direction: int = SCROLLBAR_HORIZONTAL,
                   enable_auto_hide: bool = False,
                   auto_hide_time: float = 1.0) -> int:
    """Attach cc.ScrollBar — companion to cc.ScrollView (scroll indicator).

    ``handle_sprite_id``: node/component id of the cc.Sprite that renders
    the bar's draggable handle.
    ``scroll_view_id``: id of the cc.ScrollView this bar controls (needed
    so the bar stays in sync with scroll position).
    ``direction``: 0=HORIZONTAL (default), 1=VERTICAL.
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {
        "_direction": direction,
        "_enableAutoHide": enable_auto_hide,
        "_autoHideTime": auto_hide_time,
    }
    if handle_sprite_id is not None:
        props["_handle"] = _ref(handle_sprite_id)
    if scroll_view_id is not None:
        props["_scrollView"] = _ref(scroll_view_id)
    return add_component(scene_path, node_id, "cc.ScrollBar", props)


# ----------- PageViewIndicator -----------

PAGE_INDICATOR_HORIZONTAL = 0
PAGE_INDICATOR_VERTICAL = 1


def add_page_view_indicator(scene_path: str | Path, node_id: int,
                            sprite_frame_uuid: str | None = None,
                            direction: int = PAGE_INDICATOR_HORIZONTAL,
                            cell_width: float = 20,
                            cell_height: float = 20,
                            spacing: float = 5) -> int:
    """Attach cc.PageViewIndicator — dots row showing current PageView page.

    Attach to a child node of the PageView. The engine auto-generates one
    indicator sprite per page using ``sprite_frame_uuid`` as the template.
    ``cell_width``/``cell_height`` define each indicator's size;
    ``spacing`` is the gap between them.
    """
    from cocos.scene_builder import add_component
    props: dict[str, Any] = {
        "_direction": direction,
        "_cellSize": {"__type__": "cc.Size", "width": cell_width, "height": cell_height},
        "spacing": spacing,
    }
    if sprite_frame_uuid:
        props["_spriteFrame"] = {"__uuid__": sprite_frame_uuid, "__expectedType__": "cc.SpriteFrame"}
    return add_component(scene_path, node_id, "cc.PageViewIndicator", props)

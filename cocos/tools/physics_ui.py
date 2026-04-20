"""Physics2D + UI components (button/layout/progress/scroll/toggle/editbox/slider/page/group)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from cocos import scene_builder as sb

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # ---------------- Physics 2D ----------------

    @mcp.tool()
    def cocos_add_rigidbody2d(scene_path: str, node_id: int,
                              body_type: int = 2, gravity_scale: float = 1.0,
                              linear_damping: float = 0.0, angular_damping: float = 0.0,
                              fixed_rotation: bool = False, bullet: bool = False,
                              awake_on_load: bool = True) -> int:
        """Attach cc.RigidBody2D. body_type: 0=Static, 1=Kinematic, 2=Dynamic."""
        return sb.add_rigidbody2d(scene_path, node_id, body_type, gravity_scale,
                                  linear_damping, angular_damping, fixed_rotation,
                                  bullet, awake_on_load)

    @mcp.tool()
    def cocos_add_box_collider2d(scene_path: str, node_id: int,
                                 width: float = 100, height: float = 100,
                                 offset_x: float = 0, offset_y: float = 0,
                                 density: float = 1.0, friction: float = 0.2,
                                 restitution: float = 0.0, is_sensor: bool = False,
                                 tag: int = 0) -> int:
        """Attach cc.BoxCollider2D with given size, offset, and physics material."""
        return sb.add_box_collider2d(scene_path, node_id, width, height,
                                     offset_x, offset_y, density, friction,
                                     restitution, is_sensor, tag)

    @mcp.tool()
    def cocos_add_circle_collider2d(scene_path: str, node_id: int,
                                    radius: float = 50,
                                    offset_x: float = 0, offset_y: float = 0,
                                    density: float = 1.0, friction: float = 0.2,
                                    restitution: float = 0.0, is_sensor: bool = False,
                                    tag: int = 0) -> int:
        """Attach cc.CircleCollider2D with given radius and physics material."""
        return sb.add_circle_collider2d(scene_path, node_id, radius,
                                        offset_x, offset_y, density, friction,
                                        restitution, is_sensor, tag)

    @mcp.tool()
    def cocos_add_polygon_collider2d(scene_path: str, node_id: int,
                                     points: list[list[float]] | None = None,
                                     density: float = 1.0, friction: float = 0.2,
                                     restitution: float = 0.0, is_sensor: bool = False,
                                     tag: int = 0) -> int:
        """Attach cc.PolygonCollider2D. `points` is [[x,y],...] vertex list."""
        return sb.add_polygon_collider2d(scene_path, node_id, points,
                                         density, friction, restitution,
                                         is_sensor, tag)

    # ---------------- 2D physics joints ----------------
    # All joint nodes need a cc.RigidBody2D; the connected_body_id is the
    # __id__ of the OTHER body's RigidBody2D component (None = anchor to world).

    @mcp.tool()
    def cocos_add_distance_joint2d(scene_path: str, node_id: int,
                                   connected_body_id: int | None = None,
                                   anchor_x: float = 0, anchor_y: float = 0,
                                   connected_anchor_x: float = 0, connected_anchor_y: float = 0,
                                   distance: float = 1.0, auto_calc_distance: bool = True,
                                   frequency: float = 0.0, damping_ratio: float = 0.0,
                                   collide_connected: bool = False) -> int:
        """Attach cc.DistanceJoint2D — keeps two bodies a fixed distance apart."""
        return sb.add_distance_joint2d(scene_path, node_id, connected_body_id,
                                       (anchor_x, anchor_y),
                                       (connected_anchor_x, connected_anchor_y),
                                       distance, auto_calc_distance,
                                       frequency, damping_ratio, collide_connected)

    @mcp.tool()
    def cocos_add_hinge_joint2d(scene_path: str, node_id: int,
                                connected_body_id: int | None = None,
                                anchor_x: float = 0, anchor_y: float = 0,
                                connected_anchor_x: float = 0, connected_anchor_y: float = 0,
                                enable_motor: bool = False, motor_speed: float = 0.0,
                                max_motor_torque: float = 1000.0,
                                enable_limit: bool = False,
                                lower_angle: float = 0.0, upper_angle: float = 0.0,
                                collide_connected: bool = False) -> int:
        """Attach cc.HingeJoint2D — pivots around a shared anchor (door, wheel, pendulum)."""
        return sb.add_hinge_joint2d(scene_path, node_id, connected_body_id,
                                    (anchor_x, anchor_y),
                                    (connected_anchor_x, connected_anchor_y),
                                    enable_motor, motor_speed, max_motor_torque,
                                    enable_limit, lower_angle, upper_angle,
                                    collide_connected)

    @mcp.tool()
    def cocos_add_spring_joint2d(scene_path: str, node_id: int,
                                 connected_body_id: int | None = None,
                                 anchor_x: float = 0, anchor_y: float = 0,
                                 connected_anchor_x: float = 0, connected_anchor_y: float = 0,
                                 distance: float = 1.0, auto_calc_distance: bool = True,
                                 frequency: float = 5.0, damping_ratio: float = 0.7,
                                 collide_connected: bool = False) -> int:
        """Attach cc.SpringJoint2D — soft springy distance (suspensions, ropes)."""
        return sb.add_spring_joint2d(scene_path, node_id, connected_body_id,
                                     (anchor_x, anchor_y),
                                     (connected_anchor_x, connected_anchor_y),
                                     distance, auto_calc_distance,
                                     frequency, damping_ratio, collide_connected)

    @mcp.tool()
    def cocos_add_mouse_joint2d(scene_path: str, node_id: int,
                                max_force: float = 1000.0,
                                frequency: float = 5.0, damping_ratio: float = 0.7,
                                target_x: float = 0, target_y: float = 0) -> int:
        """Attach cc.MouseJoint2D — drag-to-target constraint, used to pick up bodies with the mouse."""
        return sb.add_mouse_joint2d(scene_path, node_id, max_force,
                                    frequency, damping_ratio, (target_x, target_y))

    @mcp.tool()
    def cocos_add_slider_joint2d(scene_path: str, node_id: int,
                                 connected_body_id: int | None = None,
                                 anchor_x: float = 0, anchor_y: float = 0,
                                 connected_anchor_x: float = 0, connected_anchor_y: float = 0,
                                 angle: float = 0.0,
                                 enable_motor: bool = False, motor_speed: float = 0.0,
                                 max_motor_force: float = 1000.0,
                                 enable_limit: bool = False,
                                 lower_limit: float = 0.0, upper_limit: float = 0.0,
                                 collide_connected: bool = False) -> int:
        """Attach cc.SliderJoint2D — translates along an axis (elevators, pistons)."""
        return sb.add_slider_joint2d(scene_path, node_id, connected_body_id,
                                     (anchor_x, anchor_y),
                                     (connected_anchor_x, connected_anchor_y),
                                     angle, enable_motor, motor_speed, max_motor_force,
                                     enable_limit, lower_limit, upper_limit,
                                     collide_connected)

    @mcp.tool()
    def cocos_add_wheel_joint2d(scene_path: str, node_id: int,
                                connected_body_id: int | None = None,
                                anchor_x: float = 0, anchor_y: float = 0,
                                connected_anchor_x: float = 0, connected_anchor_y: float = 0,
                                angle: float = 90.0,
                                enable_motor: bool = False, motor_speed: float = 0.0,
                                max_motor_torque: float = 1000.0,
                                frequency: float = 5.0, damping_ratio: float = 0.7,
                                collide_connected: bool = False) -> int:
        """Attach cc.WheelJoint2D — wheel + axle (slide along axis + spring + motor combined; vehicles)."""
        return sb.add_wheel_joint2d(scene_path, node_id, connected_body_id,
                                    (anchor_x, anchor_y),
                                    (connected_anchor_x, connected_anchor_y),
                                    angle, enable_motor, motor_speed, max_motor_torque,
                                    frequency, damping_ratio, collide_connected)

    @mcp.tool()
    def cocos_add_fixed_joint_2d(scene_path: str, node_id: int,
                                 connected_body_id: int | None = None,
                                 anchor_x: float = 0, anchor_y: float = 0,
                                 connected_anchor_x: float = 0, connected_anchor_y: float = 0,
                                 angle: float = 0.0,
                                 frequency: float = 5.0, damping_ratio: float = 0.7,
                                 collide_connected: bool = False) -> int:
        """Attach cc.FixedJoint2D — rigidly fuses two bodies (breakable structures).

        Named "weld" in Box2D; replaces the prior ``cocos_add_weld_joint2d``
        which emitted ``cc.WeldJoint2D`` (not a real 3.8 class).
        """
        return sb.add_fixed_joint_2d(scene_path, node_id, connected_body_id,
                                     (anchor_x, anchor_y),
                                     (connected_anchor_x, connected_anchor_y),
                                     angle, frequency, damping_ratio, collide_connected)

    @mcp.tool()
    def cocos_add_relative_joint2d(scene_path: str, node_id: int,
                                   connected_body_id: int | None = None,
                                   max_force: float = 1000.0, max_torque: float = 1000.0,
                                   correction_factor: float = 0.3,
                                   auto_calc_offset: bool = True,
                                   linear_offset_x: float = 0, linear_offset_y: float = 0,
                                   angular_offset: float = 0.0,
                                   collide_connected: bool = False) -> int:
        """Attach cc.RelativeJoint2D — keeps relative position+angle ('attach to' effect).

        Also covers the follow-target use case that the old ``cocos_add_motor_joint2d``
        tried to solve; ``cc.MotorJoint2D`` does not exist in Cocos 3.8.
        """
        return sb.add_relative_joint2d(scene_path, node_id, connected_body_id,
                                       max_force, max_torque, correction_factor,
                                       auto_calc_offset,
                                       (linear_offset_x, linear_offset_y),
                                       angular_offset, collide_connected)

    # ---------------- UI components ----------------

    @mcp.tool()
    def cocos_add_button(scene_path: str, node_id: int,
                         transition: int = 2, zoom_scale: float = 1.1,
                         click_events: list[dict] | None = None,
                         normal_color_r: int = 255, normal_color_g: int = 255,
                         normal_color_b: int = 255, normal_color_a: int = 255,
                         hover_color_r: int = 211, hover_color_g: int = 211,
                         hover_color_b: int = 211, hover_color_a: int = 255,
                         pressed_color_r: int = 150, pressed_color_g: int = 150,
                         pressed_color_b: int = 150, pressed_color_a: int = 255,
                         disabled_color_r: int = 124, disabled_color_g: int = 124,
                         disabled_color_b: int = 124, disabled_color_a: int = 255) -> int:
        """Attach cc.Button. transition: 0=NONE, 1=COLOR, 2=SCALE, 3=SPRITE.

        click_events: list of dicts from cocos_make_click_event(). Each binds a
        button press to a script method. Example:
          evt = cocos_make_click_event(scene, gm_node, 'GameManager', 'onRestart')
          cocos_add_button(scene, btn_node, click_events=[evt])
        """
        return sb.add_button(scene_path, node_id, transition, zoom_scale,
                             (normal_color_r, normal_color_g, normal_color_b, normal_color_a),
                             (hover_color_r, hover_color_g, hover_color_b, hover_color_a),
                             (pressed_color_r, pressed_color_g, pressed_color_b, pressed_color_a),
                             (disabled_color_r, disabled_color_g, disabled_color_b, disabled_color_a),
                             click_events)

    @mcp.tool()
    def cocos_add_layout(scene_path: str, node_id: int,
                         layout_type: int = 1, spacing_x: float = 0, spacing_y: float = 0,
                         padding_top: float = 0, padding_bottom: float = 0,
                         padding_left: float = 0, padding_right: float = 0,
                         resize_mode: int = 1,
                         h_direction: int = 0, v_direction: int = 1) -> int:
        """Attach cc.Layout. layout_type: 0=NONE, 1=HORIZONTAL, 2=VERTICAL, 3=GRID."""
        return sb.add_layout(scene_path, node_id, layout_type, spacing_x, spacing_y,
                             padding_top, padding_bottom, padding_left, padding_right,
                             resize_mode, h_direction, v_direction)

    @mcp.tool()
    def cocos_add_progress_bar(scene_path: str, node_id: int,
                               bar_sprite_id: int | None = None,
                               mode: int = 0, total_length: float = 100,
                               progress: float = 1.0, reverse: bool = False) -> int:
        """Attach cc.ProgressBar. mode: 0=HORIZONTAL, 1=VERTICAL, 2=FILLED."""
        return sb.add_progress_bar(scene_path, node_id, bar_sprite_id,
                                   mode, total_length, progress, reverse)

    @mcp.tool()
    def cocos_add_scroll_view(scene_path: str, node_id: int,
                              content_id: int | None = None,
                              horizontal: bool = False, vertical: bool = True,
                              inertia: bool = True, brake: float = 0.75,
                              elastic: bool = True, bounce_duration: float = 0.23) -> int:
        """Attach cc.ScrollView. content_id points to the scrollable content node."""
        return sb.add_scroll_view(scene_path, node_id, content_id,
                                  horizontal, vertical, inertia, brake,
                                  elastic, bounce_duration)

    @mcp.tool()
    def cocos_add_toggle(scene_path: str, node_id: int,
                         is_checked: bool = False, transition: int = 2,
                         check_events: list[dict] | None = None) -> int:
        """Attach cc.Toggle. check_events: list from cocos_make_event_handler()."""
        return sb.add_toggle(scene_path, node_id, is_checked, transition, check_events)

    @mcp.tool()
    def cocos_add_editbox(scene_path: str, node_id: int,
                          placeholder: str = "Enter text...",
                          max_length: int = -1, input_mode: int = 6,
                          return_type: int = 0) -> int:
        """Attach cc.EditBox. input_mode: 0=ANY, 6=SINGLE_LINE. -1=unlimited length."""
        return sb.add_editbox(scene_path, node_id, placeholder, max_length,
                              input_mode, return_type)

    @mcp.tool()
    def cocos_add_slider(scene_path: str, node_id: int,
                         direction: int = 0, progress: float = 0.5,
                         slide_events: list[dict] | None = None) -> int:
        """Attach cc.Slider. slide_events: list from cocos_make_event_handler()."""
        return sb.add_slider(scene_path, node_id, direction, progress, slide_events)

    @mcp.tool()
    def cocos_add_page_view(scene_path: str, node_id: int,
                            content_id: int | None = None,
                            direction: int = 0, scroll_threshold: float = 0.5,
                            page_turning_speed: float = 0.3) -> int:
        """Attach cc.PageView (swipeable pages). direction: 0=H, 1=V."""
        return sb.add_page_view(scene_path, node_id, content_id, direction,
                                scroll_threshold, page_turning_speed)

    @mcp.tool()
    def cocos_add_toggle_container(scene_path: str, node_id: int,
                                   allow_switch_off: bool = False) -> int:
        """Attach cc.ToggleContainer (radio group). Children are mutually exclusive."""
        return sb.add_toggle_container(scene_path, node_id, allow_switch_off)

    @mcp.tool()
    def cocos_add_scroll_bar(scene_path: str, node_id: int,
                             handle_sprite_id: int | None = None,
                             scroll_view_id: int | None = None,
                             direction: int = 0,
                             enable_auto_hide: bool = False,
                             auto_hide_time: float = 1.0) -> int:
        """Attach cc.ScrollBar — companion scroll indicator for a ScrollView.

        direction: 0=HORIZONTAL (default), 1=VERTICAL.
        Pass ``scroll_view_id`` + ``handle_sprite_id`` to wire both
        references at attach time; otherwise set later via link_property.
        """
        return sb.add_scroll_bar(scene_path, node_id, handle_sprite_id,
                                 scroll_view_id, direction, enable_auto_hide,
                                 auto_hide_time)

    @mcp.tool()
    def cocos_add_page_view_indicator(scene_path: str, node_id: int,
                                      sprite_frame_uuid: str | None = None,
                                      direction: int = 0,
                                      cell_width: float = 20,
                                      cell_height: float = 20,
                                      spacing: float = 5) -> int:
        """Attach cc.PageViewIndicator — dots row that tracks PageView position.

        Attach to a child of the PageView node. Engine auto-spawns one
        indicator sprite per page using ``sprite_frame_uuid`` as template.
        direction: 0=HORIZONTAL (default), 1=VERTICAL.
        """
        return sb.add_page_view_indicator(scene_path, node_id, sprite_frame_uuid,
                                          direction, cell_width, cell_height,
                                          spacing)

    @mcp.tool()
    def cocos_add_webview(scene_path: str, node_id: int,
                          url: str = "https://cocos.com") -> int:
        """Attach cc.WebView — embedded browser pane for ToS / activity pages."""
        return sb.add_webview(scene_path, node_id, url)

    # ---------------- Event handler builders ----------------

    @mcp.tool()
    def cocos_make_event_handler(scene_path: str, target_node_id: int,
                                 component_name: str, handler: str,
                                 custom_data: str = "") -> dict:
        """Build a cc.EventHandler dict for component event bindings.

        Use with: cocos_add_scroll_view(scroll_events=[...]),
        cocos_add_toggle(check_events=[...]), cocos_add_slider(slide_events=[...]),
        cocos_add_editbox(editing_return=[...]).

        Same pattern as cocos_make_click_event but for non-Button components.
        """
        return sb.make_event_handler(target_node_id, component_name, handler, custom_data)

    @mcp.tool()
    def cocos_make_click_event(scene_path: str, target_node_id: int,
                               component_name: str, handler: str,
                               custom_data: str = "") -> dict:
        """Build a cc.ClickEvent dict for use with cocos_add_button's click_events.

        Args:
            target_node_id: Node that holds the script (array index)
            component_name: @ccclass name (e.g. 'GameManager')
            handler: Method name to call (e.g. 'onStartClick')

        Returns a dict to pass in click_events list of cocos_add_button.

        Example workflow:
          evt = cocos_make_click_event(scene, gm_node, 'GameManager', 'onStart')
          cocos_add_button(scene, btn_node, click_events=[evt])
        """
        return sb.make_click_event(target_node_id, component_name, handler, custom_data)

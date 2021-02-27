import bpy
import traceback

from ..utility.draw import draw_quad, draw_text, get_blf_text_dims
from ..utility.addon import get_prefs
from ..utility.ray import mouse_raycast_to_scene
from .geopath_datastructure import GeoPath


class MEASURES_GEODESIC_OT(bpy.types.Operator):
    bl_label = "Create Geodesic Measure"
    bl_idname = 'measures.create_geodesic'
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    @classmethod
    def poll(cls, context):
        # If you want to verify the conditions of your operator
        # before it launches, put your code here
        if context.mode != 'OBJECT':
            return False

        if context.object.type != 'MESH':
            return False

        return True

    # Called after poll
    def invoke(self, context, event):
        # Initialize some props
        self.hit_point = None
        self.geopath = GeoPath(context, context.object)
        self.state = 'main'

        # Do some setup
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_custom_controls, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    # Running in loop until we leave the modal
    def modal(self, context, event):

        if event.type == 'MOUSEMOVE':
            self.detect_collision(context, event)

        if self.state == 'main':
            return self.handle_main(context, event)
        elif self.state == 'grab':
            return self.handle_grab(context, event)

        return {"RUNNING_MODAL"}  # Should not get here but you never know

    # Handles events in main mode
    def handle_main(self, context, event):

        # Free navigation
        if event.type in {
            'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
            'WHEELINMOUSE', 'WHEELOUTMOUSE'
        }:
            return {'PASS_THROUGH'}

        # Grab initiating
        elif event.type == 'G' and event.value == 'PRESS':
            if self.geopath.grab_initiate():
                self.state = 'grab'  # Do grab mode

        # Adding points
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            x, y = (event.mouse_region_x, event.mouse_region_y)
            if self.geopath.seed is not None:
                self.geopath.click_add_target(context, x, y)
            else:
                self.geopath.click_add_seed(context, x, y)

        # Confirm path an exit gracefully
        elif event.type == 'RET' and event.value == 'PRESS':
            self.remove_shaders(context)
            return {'FINISHED'}

        # Cancel
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self.remove_shaders(context)
            return {'CANCELLED'}

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def handle_grab(self, context, event):

        # Free navigation
        if event.type in {
            'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
            'WHEELINMOUSE', 'WHEELOUTMOUSE'
        }:
            return {'PASS_THROUGH'}

        # confirm location
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.geopath.grab_confirm()
            self.state = 'main'

        # put it back!
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self.geopath.grab_cancel()
            self.state = 'main'

        # update the b_pt location
        if event.type == 'MOUSEMOVE':
            x, y = (event.mouse_region_x, event.mouse_region_y)
            self.geopath.grab_mouse_move(context, x, y)
            self.state = 'grab'

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def detect_collision(self, context, event):
        if event.type == 'MOUSEMOVE':
            self.hit_point = None
            hit, location, normal, index, object, matrix = \
                mouse_raycast_to_scene(context, event)
            if hit:
                self.hit_point = location

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        # layout.prop(self, 'height')
        # layout.prop(self, 'plane_rotation')

    def execute(self, context):
        # scene = context.scene
        # ob = scene.objects.get("Avatar")
        return {'FINISHED'}

    def remove_shaders(self, context):
        '''Remove shader handle.'''

        if self.draw_handle is not None:
            self.draw_handle = bpy.types.SpaceView3D.draw_handler_remove(
                self.draw_handle, "WINDOW"
            )
            context.area.tag_redraw()

    def draw_custom_controls(self, context):
        try:
            self.geopath.draw(context)
            self.draw_debug_panel(context)
        except Exception:
            print("Failed to draw geopath")
            traceback.print_exc()
            self.remove_shaders(context)

    def draw_debug_panel(self, context):

        if (self.hit_point is None):
            return

        prefs = get_prefs()

        # Props
        text = "X : {:.3f}, Y : {:.3f}, Z : {:.3f}".format(
            self.hit_point.x, self.hit_point.y, self.hit_point.z
        )

        font_size = prefs.settings.font_size
        dims = get_blf_text_dims(text, font_size)
        area_width = context.area.width
        padding = 8

        over_all_width = dims[0] + padding * 2
        over_all_height = dims[1] + padding * 2

        left_offset = abs((area_width - over_all_width) * .5)
        bottom_offset = 20

        top_left = (left_offset, bottom_offset + over_all_height)
        bot_left = (left_offset, bottom_offset)
        top_right = (left_offset + over_all_width,
                     bottom_offset + over_all_height)
        bot_right = (left_offset + over_all_width, bottom_offset)

        # Draw Quad
        verts = [top_left, bot_left, top_right, bot_right]
        draw_quad(vertices=verts, color=prefs.color.bg_color)

        # Draw Text
        x = left_offset + padding
        y = bottom_offset + padding
        draw_text(
            text=text, x=x, y=y, size=font_size,
            color=prefs.color.font_color
        )

        # Draw path
        text = ""

        if self.geopath.seed_loc is not None:
            text += "START: ({:.3f}, {:.3f}, {:.3f}) ".format(
                    self.geopath.seed_loc.x,
                    self.geopath.seed_loc.y,
                    self.geopath.seed_loc.z)

        if self.geopath.target_loc is not None:
            text += "END: ({:.3f}, {:.3f}, {:.3f})".format(
                    self.geopath.target_loc.x,
                    self.geopath.target_loc.y,
                    self.geopath.target_loc.z)

        if len(text) != 0:
            draw_text(
                text=text, x=x, y=y + over_all_height + padding,
                size=font_size,
                color=prefs.color.font_color
            )

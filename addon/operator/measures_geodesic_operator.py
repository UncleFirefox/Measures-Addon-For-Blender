from functools import reduce
import bpy
import bmesh
import traceback

from ..utility.draw import draw_messages
from ..utility.ray import mouse_raycast_to_scene
# from .geopath_datastructure import GeoPath, Geodesic_State
from .geopath_datastructure_vertices import GeoPath, Geodesic_State


class MEASURES_GEODESIC_OT(bpy.types.Operator):
    bl_label = "Create Geodesic Measure"
    bl_idname = 'measures.create_geodesic'
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    @classmethod
    def poll(cls, context):
        # If you want to verify the conditions of your operator
        # before it launches, put your code here
        # if context.mode != 'OBJECT':
        #     return False

        if context.object is None or context.object.type != 'MESH':
            return False

        return True

    # Called after poll
    def invoke(self, context, event):
        # Initialize some props
        self.hit_point = None
        self.geopath = GeoPath(context, context.object)
        self.state = Geodesic_State.POINTS

        # Do some setup
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_custom_controls, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    # Running in loop until we leave the modal
    def modal(self, context, event):

        # Confirm path an exit gracefully
        if event.type == 'RET' and event.value == 'PRESS':
            self.execute(context)
            self.remove_shaders(context)
            return {'FINISHED'}

        # Cancel
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            context.window.cursor_set("DEFAULT")
            self.remove_shaders(context)
            self.geopath.finish()
            return {'CANCELLED'}

        # Free navigation
        pass_through_events = {
            'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
            'WHEELINMOUSE', 'WHEELOUTMOUSE'
        }
        if event.type in pass_through_events:
            return {'PASS_THROUGH'}

        # Movement capture for debugging
        if event.type == 'MOUSEMOVE':
            self.detect_collision(context, event)

        # Enable visual debugging
        if event.type == 'SPACE' and event.value == 'PRESS':
            self.geopath.toggle_debugging()

        # State handling
        if self.state == Geodesic_State.POINTS:
            return self.handle_points(context, event)
        elif self.state == Geodesic_State.GRAB:
            return self.handle_grab(context, event)
        elif self.state == Geodesic_State.ERASE:
            return self.handle_erase(context, event)
        elif self.state == Geodesic_State.INSERT:
            return self.handle_insert(context, event)

        return {"RUNNING_MODAL"}  # Should not get here but you never know

    def handle_points(self, context, event):

        # Adding points
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            x, y = (event.mouse_region_x, event.mouse_region_y)
            self.geopath.click_add_point(context, x, y)

        elif event.type == 'G' and event.value == 'PRESS':
            self.state = Geodesic_State.GRAB

        elif event.type == 'E' and event.value == 'PRESS':
            self.state = Geodesic_State.ERASE

        elif event.type == 'I' and event.value == 'PRESS':
            self.state = Geodesic_State.INSERT

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def handle_grab(self, context, event):

        if event.type == 'MOUSEMOVE':
            x, y = (event.mouse_region_x, event.mouse_region_y)
            self.geopath.grab_mouse_move(context, x, y)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.geopath.grab_start()

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self.geopath.grab_finish()

        elif event.type == 'P' and event.value == 'PRESS':
            self.geopath.grab_cancel()
            self.state = Geodesic_State.POINTS

        elif event.type == 'E' and event.value == 'PRESS':
            self.geopath.grab_cancel()
            self.state = Geodesic_State.ERASE

        elif event.type == 'I' and event.value == 'PRESS':
            self.geopath.grab_cancel()
            self.state = Geodesic_State.INSERT

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def handle_erase(self, context, event):

        if event.type == 'MOUSEMOVE':
            x, y = (event.mouse_region_x, event.mouse_region_y)
            self.geopath.erase_mouse_move(context, x, y)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.geopath.erase_point()

        elif event.type == 'P' and event.value == 'PRESS':
            self.geopath.erase_cancel(context)
            self.state = Geodesic_State.POINTS

        elif event.type == 'G' and event.value == 'PRESS':
            self.geopath.erase_cancel(context)
            self.state = Geodesic_State.GRAB

        elif event.type == 'I' and event.value == 'PRESS':
            self.geopath.erase_cancel(context)
            self.state = Geodesic_State.INSERT

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def handle_insert(self, context, event):

        if event.type == 'MOUSEMOVE':
            x, y = (event.mouse_region_x, event.mouse_region_y)
            self.geopath.insert_mouse_move(context, x, y)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.geopath.insert_start()

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self.geopath.insert_finish()

        elif event.type == 'P' and event.value == 'PRESS':
            self.geopath.insert_cancel(context)
            self.state = Geodesic_State.POINTS

        elif event.type == 'G' and event.value == 'PRESS':
            self.geopath.insert_cancel(context)
            self.state = Geodesic_State.GRAB

        elif event.type == 'E' and event.value == 'PRESS':
            self.geopath.insert_cancel(context)
            self.state = Geodesic_State.ERASE

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

    def execute(self, context):

        path = self.geopath.get_whole_path()

        if len(path) == 0:
            return {'FINISHED'}

        bm = bmesh.new()
        vertices = []
        edges = []
        for vert in path:
            vertices.append(bm.verts.new(vert))

        for i in range(1, len(path)):
            edges.append(bm.edges.new((vertices[i-1], vertices[i])))

        me = bpy.data.meshes.new("GeodesicPath")
        bm.to_mesh(me)
        obj = bpy.data.objects.new("GeodesicPath", me)
        context.collection.objects.link(obj)
        obj.select_set(True)

        bm.free()

        self.geopath.finish()

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
            self.geopath.draw(context, self.state)
            self.draw_debug_panel(context)
        except Exception:
            print("Failed to draw geopath")
            traceback.print_exc()
            self.remove_shaders(context)

    def draw_debug_panel(self, context):

        messages = []

        mode = "Plugin mode: {}".format(self.state.name)

        if self.geopath.is_debugging:
            mode += " | Visual Debug: ON"

        messages.append(mode)

        # Path information
        num_segments = 0
        total_length = 0

        if len(self.geopath.path_segments) > 0:
            total_length = reduce(lambda a, b:
                                  a + self.get_segment_length(b),
                                  self.geopath.path_segments, 0)

            num_segments = len(self.geopath.path_segments)

        messages.append(
            "#SEGMENTS: {}, LENGTH: {:.3f}".format(
                num_segments,
                total_length)
        )

        # Hit point information
        if (self.hit_point):
            messages.append(
                "X : {:.3f}, Y : {:.3f}, Z : {:.3f}".format(
                 self.hit_point.x, self.hit_point.y, self.hit_point.z)
            )

        draw_messages(context, messages)

    def get_segment_length(self, segment):
        result = 0

        for i in range(1, len(segment)-1):
            result += (segment[i-1] - segment[i]).length

        return result

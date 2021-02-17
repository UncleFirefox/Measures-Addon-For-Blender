from .geopath_datastructure import GeoPath
import bpy
import traceback


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
        self.geopath = GeoPath(context, context.object)
        self.state = 'main'

        # Do some setup
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self.safe_draw_shader_2d, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    # Running in loop until we leave the modal
    def modal(self, context, event):
        if self.state == 'main':
            return self.handle_main(context, event)
        elif self.state == 'grab':
            return self.handle_grab(context, event)

        return {"RUNNING_MODAL"}  # Should not get here but you never know

    # Handles events in main mode
    def handle_main(self, context, event):
        # Free navigation
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE'}:
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
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # confirm location
            self.geopath.grab_confirm()
            self.state = 'main'
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            # put it back!
            self.geopath.grab_cancel()
            self.state = 'main'
        if event.type == 'LEFTMOUSE':
            # update the b_pt location
            x, y = event['mouse']
            self.geopath.grab_mouse_move(context, x, y)
            self.state = 'grab'

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

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

    def safe_draw_shader_2d(self, context):
        try:
            self.geopath.draw(context)
        except Exception:
            print("Failed to draw geopath")
            traceback.print_exc()
            self.remove_shaders(context)

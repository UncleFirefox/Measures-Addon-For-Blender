from bmesh.types import BMesh
import bpy
import bmesh
import traceback
import math

from mathutils import Euler, Matrix, Vector
from ..utility.draw import draw_quad, draw_text, get_blf_text_dims
from ..utility.addon import get_prefs
from ..utility.ray import mouse_raycast_to_scene
from functools import reduce


class MEASURES_CIRCULAR_OT(bpy.types.Operator):
    bl_label = "Create Circular Measure"
    bl_idname = 'measures.create_circular'
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    height: bpy.props.FloatProperty(
        name="Height",
        default=0,
        min=-3,
        max=3,
        step=0.1,
        precision=3
    )
    normal_rotation: bpy.props.FloatVectorProperty(
        name="Normal Rotation",
        subtype='EULER',
        min=-2*math.pi, max=2*math.pi
    )

    @classmethod
    def poll(cls, context):
        # If you want to verify the conditions of your operator
        # before it launches, put your code here
        return True

    # Called after poll
    def invoke(self, context, event):
        # Initialize some props
        self.height = 0
        self.hit_point = None
        self.total_length = 0
        # Do some setup
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self.safe_draw_shader_2d, (context,), 'WINDOW', 'POST_PIXEL')
        self.normal_rotation = (0, 0, 0)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    # Running in loop until we leave the modal
    def modal(self, context, event):
        # Free navigation
        if event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        # Confirm
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.remove_shaders(context)
            return {'FINISHED'}

        # Cancel
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self.remove_shaders(context)
            return {'CANCELLED'}

        # Adjust
        elif event.type == 'MOUSEMOVE':

            hit, location, normal, index, object, matrix = \
                mouse_raycast_to_scene(context, event)

            if hit:
                self.height = location.z
                self.hit_point = location
                self.execute(context)

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'height')
        layout.prop(self, 'normal_rotation')

    def execute(self, context):
        dg = context.evaluated_depsgraph_get()
        ob = context.object  # default to selected object

        if ob:
            rotation = Matrix()

            if self.normal_rotation != Euler():
                rotation = self.normal_rotation.to_matrix().to_4x4()

            plane_co = self.hit_point
            if self.height != 0:
                plane_co.z = self.height

            plane_no = rotation @ Vector((0, 0, 1))
            bm = bmesh.new()
            bm.from_object(ob, dg)
            bmesh.ops.transform(
                bm,
                verts=bm.verts,
                matrix=ob.matrix_world
            )

            # Perform bisection
            bmesh.ops.bisect_plane(
                bm,
                geom=bm.faces[:] + bm.edges[:] + bm.verts[:],
                clear_inner=True,
                clear_outer=True,
                plane_co=plane_co,
                plane_no=plane_no
            )

            # Bisection cleanup
            closest_edge = self.find_closest_edge(bm)

            # Could be that the angle of plane finds
            # no vertices after bisection
            if closest_edge is not None:
                vertex_list = self.get_reachable_vertices(closest_edge)
                for v in [v for v in bm.verts if v not in vertex_list]:
                    bm.verts.remove(v)

                # Object creation and addition to scene
                bisect_obj = bpy.data.objects.get("Bisect")
                if bisect_obj is not None:
                    bpy.data.objects.remove(bisect_obj, do_unlink=True)

                me = bpy.data.meshes.new("Bisect")
                bm.to_mesh(me)
                ob = bpy.data.objects.new("Bisect", me)
                context.collection.objects.link(ob)
                ob.select_set(True)

            bm.free()

        return {'FINISHED'}

    def get_reachable_vertices(self, closest_edge):
        edge_list = [closest_edge]
        vertex_list = [v for v in closest_edge.verts]
        for v in vertex_list:
            for e in [edge for edge in v.link_edges if edge not in edge_list]:
                edge_list.append(e)
                if (e.other_vert(v) not in vertex_list):
                    vertex_list.append(e.other_vert(v))

        self.total_length = reduce(
            lambda a, b: a + b.calc_length(), edge_list, 0)

        return vertex_list

    def find_closest_edge(self, bm: BMesh):
        result = None
        min_dist = 9999.99
        for e in bm.edges:
            for v in e.verts:
                dist = (v.co - self.hit_point).magnitude
                if dist < min_dist:
                    result = e
                    min_dist = dist
                    if min_dist < 0.01:
                        return e  # If its close enough dont continue iterating

        return result

    def remove_shaders(self, context):
        '''Remove shader handle.'''

        if self.draw_handle is not None:
            self.draw_handle = bpy.types.SpaceView3D.draw_handler_remove(
                self.draw_handle, "WINDOW"
            )
            context.area.tag_redraw()

    def safe_draw_shader_2d(self, context):

        try:
            self.draw_shaders_2d(context)
        except Exception:
            print("2D Shader Failed in Ray Caster")
            traceback.print_exc()
            self.remove_shaders(context)

    def draw_shaders_2d(self, context):

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

        # Draw measurement length
        if self.total_length != 0:
            text = "LENGTH: {:.3f}".format(self.total_length)
            draw_text(
                text=text, x=x, y=y + over_all_height + padding,
                size=font_size,
                color=prefs.color.font_color
            )

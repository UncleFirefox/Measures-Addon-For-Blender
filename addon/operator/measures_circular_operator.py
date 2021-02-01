from bmesh.types import BMesh
import bpy
import bmesh
from ..utility.ray import mouse_raycast_to_scene


class MEASURES_CIRCULAR_OT(bpy.types.Operator):
    bl_label = "Create Circular Measure"
    bl_idname = 'measures.create_circular'
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    height: bpy.props.FloatProperty(name="Height", default=0, min=0)
    plane_scale: bpy.props.FloatProperty(name="Plane Scale", default=1, min=1)

    @classmethod
    def poll(cls, context):
        # If you want to verify the conditions of your operator
        # before it launches, put your code here
        return True

    # Called after poll
    def invoke(self, context, event):
        # Initialize some props

        # Do some setup

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    # Running in loop until we leave the modal
    def modal(self, context, event):
        # Free navigation
        if event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        # Confirm
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            return {'FINISHED'}

        # Cancel
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return {'CANCELLED'}

        # Adjust
        elif event.type == 'MOUSEMOVE':

            hit, location, normal, index, object, matrix = \
                mouse_raycast_to_scene(context, event)

            if hit:
                self.height = location.z
                self.hit_point = location
                self.execute(context)

        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'height')
        layout.prop(self, 'plane_scale')

    def execute(self, context):
        dg = context.evaluated_depsgraph_get()
        scene = context.scene
        ob = scene.objects.get("Avatar")
        plane = self.create_plane()

        if plane and ob:

            # Get plane data
            pmw = plane.matrix_world
            face = plane.data.polygons[0]
            plane_co = pmw @ face.center
            plane_no = pmw @ (face.center + face.normal) - plane_co
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

        return {'FINISHED'}

    def get_reachable_vertices(self, closest_edge):
        edge_list = [closest_edge]
        vertex_list = [v for v in closest_edge.verts]
        for v in vertex_list:
            for e in [edge for edge in v.link_edges if edge not in edge_list]:
                edge_list.append(e)
                if (e.other_vert(v) not in vertex_list):
                    vertex_list.append(e.other_vert(v))

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

    def create_plane(self):
        mesh = bpy.data.meshes.new("Plane")
        obj = bpy.data.objects.new("Plane", mesh)

        # bpy.context.collection.objects.link(obj)

        bm = bmesh.new()
        bm.from_object(obj, bpy.context.view_layer.depsgraph)

        s = self.plane_scale
        bm.verts.new((s, s, self.height))
        bm.verts.new((s, -s, self.height))
        bm.verts.new((-s, s, self.height))
        bm.verts.new((-s, -s, self.height))

        bmesh.ops.contextual_create(bm, geom=bm.verts)

        bm.to_mesh(mesh)
        return obj

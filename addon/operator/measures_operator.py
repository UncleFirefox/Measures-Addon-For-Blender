import bpy
import bmesh


class MEASURES_OT(bpy.types.Operator):
    bl_label = "Create Measure"
    bl_idname = 'measures.create'
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
            delta = event.mouse_y - event.mouse_prev_y
            delta /= 100
            self.height += delta

            bisect_obj = bpy.data.objects.get("Bisect")
            if bisect_obj is not None:
                bpy.data.objects.remove(bisect_obj, do_unlink=True)
            self.execute(context)

        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'height')
        layout.prop(self, 'plane_scale')

    def execute(self, context):
        #print('Measures Operator executed')

        dg = context.evaluated_depsgraph_get()
        scene = context.scene
        ob = scene.objects.get("Avatar")
        # plane = scene.objects.get("Plane")
        plane = self.create_plane()

        if plane and ob:
            pmw = plane.matrix_world
            face = plane.data.polygons[0]
            plane_co = pmw @ face.center
            plane_no = pmw @ (face.center + face.normal) - plane_co
            bm = bmesh.new()
            bm.from_object(ob, dg)
            bmesh.ops.transform(bm,
                verts=bm.verts,
                matrix=ob.matrix_world)

            x = bmesh.ops.bisect_plane(bm,
                geom=bm.faces[:] + bm.edges[:] + bm.verts[:],
                clear_inner=True,
                clear_outer=True,
                plane_co=plane_co,
                plane_no=plane_no
                )

        # new object
        me = bpy.data.meshes.new("Bisect")
        bm.to_mesh(me)
        ob = bpy.data.objects.new("Bisect", me)
        context.collection.objects.link(ob)

        #bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)

        return {'FINISHED'}

    def create_plane(self):
        mesh = bpy.data.meshes.new("Plane")
        obj = bpy.data.objects.new("Plane", mesh)

        # bpy.context.collection.objects.link(obj)

        bm = bmesh.new()
        bm.from_object(obj, bpy.context.view_layer.depsgraph)

        s = self.plane_scale
        bm.verts.new((s, s, self.height))
        bm.verts.new((s, -s, self. height))
        bm.verts.new((-s, s, self.height))
        bm.verts.new((-s, -s, self.height))

        bmesh.ops.contextual_create(bm, geom=bm.verts)

        bm.to_mesh(mesh)
        return obj

import bpy
import bmesh


class MEASURES_OT(bpy.types.Operator):
    bl_label = "Create Measure"
    bl_idname = 'measures.create'

    def execute(self, context):
        print('Measures Operator executed')

        dg = context.evaluated_depsgraph_get()
        scene = context.scene
        ob = scene.objects.get("Avatar")
        plane = scene.objects.get("Plane")

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

        return {'FINISHED'}

import bpy


class MeasuresMainPanel(bpy.types.Panel):
    """Creates a Panel in the 3D view for Measures"""
    bl_label = "Measures Library"
    bl_idname = "MEASURES_PT_MAINPANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Measures Library'
    # bl_options = {'DEFAULT_CLOSED'}
    # bl_parent_id = 'PT_PARENTPANEL' -> you need to give id aka bl_idname

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2

        row = layout.row()
        row.label(text="Adjust the plane to the Avatar", icon="MOD_TINT")

        plane = bpy.context.scene.objects.get("Plane")
        row = layout.row()
        col = layout.column()
        col.prop(plane, "location")

        # TODO:
        # https://blender.stackexchange.com/questions/123044/how-to-scale-an-object-via-a-slider-in-python
        row = layout.row()
        col = layout.column()
        col.prop(plane, "scale")

        row = layout.row()
        col = layout.column()
        col.prop(plane, "rotation_euler")

        row = layout.row()
        row.operator('measures.create')

        # row = layout.row()
        # row.label(text="Active object is: " + obj.name)
        # row = layout.row()
        # row.prop(obj, "name")

        # row = layout.row()
        # row.operator("mesh.primitive_cube_add")

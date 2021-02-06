import bpy


class MEASURES_PT_CIRCULAR_PANEL(bpy.types.Panel):
    """Creates a Panel in the 3D view for Measures"""
    bl_label = "Circular Measure"
    bl_idname = "MEASURES_PT_CIRCULAR_PANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Measures Library'
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'MEASURES_PT_MAINPANEL'

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2

        row = layout.row()
        row.label(text="Adjust the plane to the Avatar", icon="MOD_TINT")
        row = layout.row()
        row.operator('measures.create_circular')

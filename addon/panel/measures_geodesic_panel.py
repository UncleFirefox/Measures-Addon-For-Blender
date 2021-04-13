from ..register.dependency_handling import \
    are_dependencies_installed, show_no_dependencies_warning

import bpy


class MEASURES_PT_GEODESIC_PANEL(bpy.types.Panel):
    """Creates a a subpanel for geodesic in the 3D view for Measures"""
    bl_label = "Geodesic Measure"
    bl_idname = "MEASURES_PT_GEODESIC_PANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Measures Library'
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'MEASURES_PT_MAINPANEL'

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2

        if are_dependencies_installed():
            self.show_operator(layout)
        else:
            show_no_dependencies_warning(layout)

    def show_operator(self, layout):
        row = layout.row()
        row.label(
            text="Select a origin and destiny to generate a path",
            icon="MOD_TINT"
        )
        row = layout.row()
        row.operator('measures.create_geodesic')

from addon.register.dependency_handling import are_dependencies_installed
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
            self.show_no_dependencies_warning(layout)

    def show_operator(self, layout):
        row = layout.row()
        row.label(
            text="Select a origin and destiny to generate a path",
            icon="MOD_TINT"
        )
        row = layout.row()
        row.operator('measures.create_geodesic')

    def show_no_dependencies_warning(self, layout):

        lines = [f"Please install the missing dependencies for the Measures add-on.",
            f"1. Open the preferences (Edit > Preferences > Add-ons).",
            f"2. Search for the Measures Library add-on.",
            f"3. Open the details section of the add-on.",
            f"4. Click on the Install Dependencies button.",
            f"   This will download and install the missing Python packages, if Blender has the required",
            f"   permissions.",
            f"If you're attempting to run the add-on from the text editor, you won't see the options described",
            f"above. Please install the add-on properly through the preferences.",
            f"1. Open the add-on preferences (Edit > Preferences > Add-ons).",
            f"2. Press the \"Install\" button.",
            f"3. Search for the add-on file.",
            f"4. Confirm the selection by pressing the \"Install Add-on\" button in the file browser."]

        for line in lines:
            layout.label(text=line)

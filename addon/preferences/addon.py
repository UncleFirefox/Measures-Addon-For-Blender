import bpy

from .install_dependencies_operator import \
    MEASURES_OT_Install_Dependencies

from ..utility.addon import addon_name, get_prefs
from bpy.props import PointerProperty

from .color import MEASURES_Color, draw_color
from .settings import MEASURES_Settings, draw_settings


class MEASURES_Props(bpy.types.AddonPreferences):
    bl_idname = addon_name

    # Property Groups
    color: PointerProperty(type=MEASURES_Color)
    settings: PointerProperty(type=MEASURES_Settings)

    def draw(self, context):

        prefs = get_prefs()
        layout = self.layout

        # General Settings
        box = layout.box()
        draw_color(prefs, box)

        # Drawing settings
        box = layout.box()
        draw_settings(prefs, box)

        # Dependencies
        layout.operator(MEASURES_OT_Install_Dependencies.bl_idname, icon="CONSOLE")

import bpy
from bpy.props import IntProperty


class MEASURES_Settings(bpy.types.PropertyGroup):

    font_size: IntProperty(
        name='Font Size', description='Font Size',
        min=10, max=32, default=24)


def draw_settings(prefs, layout):

    layout.label(text='General Settings',  icon='TOOL_SETTINGS')

    # Tools
    box = layout.box()

    row = box.row()
    row.label(text='Font Size')
    row.prop(prefs.settings, 'font_size', text='Font Size')
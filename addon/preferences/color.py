import bpy
from bpy.props import FloatVectorProperty


class MEASURES_Color(bpy.types.PropertyGroup):

    font_color: FloatVectorProperty(
        name='Font Color', description='Color of the modal font',
        size=4, min=0, max=1,
        subtype='COLOR', default=(1, 1, 1, 1))

    bg_color: FloatVectorProperty(
        name='BG Color', description='Color of the background',
        size=4, min=0, max=1,
        subtype='COLOR', default=(0, 0, 0, .75))


def draw_color(prefs, layout):

    layout.label(text='Colors',  icon='RESTRICT_COLOR_ON')

    # Tools
    box = layout.box()

    row = box.row()
    row.prop(prefs.color, 'font_color', text='Font Color')
    row = box.row()
    row.prop(prefs.color, 'bg_color', text='Background Color')
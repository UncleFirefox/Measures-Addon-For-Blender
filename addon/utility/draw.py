import bpy
import blf
import gpu
import bgl

from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import location_3d_to_region_2d


def draw_quad(vertices=[], color=(1, 1, 1, 1)):
    '''Vertices = Top Left, Bottom Left, Top Right, Bottom Right'''

    indices = [(0, 1, 2), (1, 2, 3)]
    shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    batch = batch_for_shader(
        shader, 'TRIS', {"pos": vertices}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    bgl.glEnable(bgl.GL_BLEND)
    batch.draw(shader)
    bgl.glDisable(bgl.GL_BLEND)

    del shader
    del batch


def draw_text(text, x, y, size=12, color=(1, 1, 1, 1)):

    dpi = bpy.context.preferences.system.dpi
    font = 0
    blf.size(font, size, int(dpi))
    blf.color(font, *color)
    blf.position(font, x, y, 0)
    blf.draw(font, text)


def get_blf_text_dims(text, size):
    '''Return the total width of the string'''

    dpi = bpy.context.preferences.system.dpi
    blf.size(0, size, dpi)
    return blf.dimensions(0, str(text))


def draw_polyline_from_3dpoints(context, points_3d, color, thickness,
                                LINE_TYPE):
    '''
    a simple way to draw a line
    slow...becuase it must convert to screen every time
    but allows you to pan and zoom around

    args:
        points_3d: a list of tuples representing x,y SCREEN coordinate
        eg [(10,30),(11,31),...]
        color: tuple (r,g,b,a)
        thickness: integer? maybe a float
        LINE_TYPE:  eg...bgl.GL_LINE_STIPPLE or
    '''

    points = [
        location_3d_to_region_2d(context.region,
                                 context.space_data.region_3d, loc)
        for loc in points_3d
    ]

    if LINE_TYPE == "GL_LINE_STIPPLE":
        bgl.glLineStipple(4, 0x5555)  # play with this later
        bgl.glEnable(bgl.GL_LINE_STIPPLE)
    bgl.glEnable(bgl.GL_BLEND)

    bgl.glColor4f(*color)
    bgl.glLineWidth(thickness)
    bgl.glBegin(bgl.GL_LINE_STRIP)
    for coord in points:
        if coord:
            bgl.glVertex2f(*coord)

    bgl.glEnd()

    if LINE_TYPE == "GL_LINE_STIPPLE":
        bgl.glDisable(bgl.GL_LINE_STIPPLE)
        bgl.glEnable(bgl.GL_BLEND)  # back to uninterupted lines
        bgl.glLineWidth(1)
    return


def draw3d_points(context, points, color, size):
    bgl.glColor4f(*color)
    bgl.glPointSize(size)
    bgl.glDepthRange(0.0, 0.997)
    bgl.glBegin(bgl.GL_POINTS)
    for coord in points:
        bgl.glVertex3f(*coord)
    bgl.glEnd()
    bgl.glPointSize(1.0)

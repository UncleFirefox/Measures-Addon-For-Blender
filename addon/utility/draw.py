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
                                 context.space_data.region_3d, loc).to_3d()
        for loc in points_3d
    ]

    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": points})

    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glLineWidth(thickness)

    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    bgl.glDisable(bgl.GL_BLEND)

    del shader
    del batch

    # if LINE_TYPE == "GL_LINE_STIPPLE":
    #     bgl.glLineStipple(4, 0x5555)  # play with this later
    #     bgl.glEnable(bgl.GL_LINE_STIPPLE)
    # bgl.glEnable(bgl.GL_BLEND)

    # bgl.glColor4f(*color)
    # bgl.glLineWidth(thickness)
    # bgl.glBegin(bgl.GL_LINE_STRIP)
    # for coord in points:
    #     if coord:
    #         bgl.glVertex2f(*coord)

    # bgl.glEnd()

    # if LINE_TYPE == "GL_LINE_STIPPLE":
    #     bgl.glDisable(bgl.GL_LINE_STIPPLE)
    #     bgl.glEnable(bgl.GL_BLEND)  # back to uninterupted lines
    #     bgl.glLineWidth(1)

    return


def draw_3d_points(context, points, size, color=(1, 0, 0, 1)):
    region = context.region
    rv3d = context.space_data.region_3d

    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    vertices = []
    for coord in points:
        vector3d = (coord.x, coord.y, coord.z)
        vector2d = location_3d_to_region_2d(region, rv3d, vector3d)
        if vector2d and vector3d:
            vertices.append((vector2d.x, vector2d.y, 0))

    # Drawing using new api
    # https://www.youtube.com/watch?v=EgrgEoNFNsA
    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'POINTS', {"pos": vertices})

    bgl.glPointSize(size)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    del shader
    del batch

    return

import bmesh
from bpy_extras import view3d_utils

from ..algorithms.geodesic import \
    geodesic_walk, continue_geodesic_walk, gradient_descent

from ..utility import draw


class GeoPath(object):
    '''
    A class which manages user placed points on an object to create a
    piecewise path of geodesics, adapted to the objects surface.
    '''
    def __init__(self, context, selected_obj):

        self.selected_obj = selected_obj
        self.bme = bmesh.new()
        self.bme.from_mesh(selected_obj.data)
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()

        non_tris = [f for f in self.bme.faces if len(f.verts) > 3]
        bmesh.ops.triangulate(self.bme, faces=non_tris)

        self.key_points = []
        self.path_segments = []

        # geos, fixed, close, far
        self.geo_data = [dict(), set(), set(), set()]

    def click_add_point(self, context, x, y):
        '''
        x,y = event.mouse_region_x, event.mouse_region_y

        this will add a point into the bezier curve or
        close the curve into a cyclic curve
        '''
        hit, hit_location, face_ind = self.raycast(context, x, y)

        if not hit:
            self.selected = -1
            return

        hit_face = self.bme.faces[face_ind]
        self.key_points.append((hit_location, hit_face))

        if len(self.key_points) == 1:
            self.bme.faces.ensure_lookup_table()  # how does this get outdated?
            self.geo_data = [dict(), set(), set(), set()]
        elif len(self.key_points) > 1:
            #  The elements just before the ones we just pushed
            start_loc, start_face = self.key_points[-2]

            geos, fixed, close, far = geodesic_walk(
                self.bme.verts, start_face, start_loc,
                hit_face, max_iters=100000)

            path_elements, path = gradient_descent(geos,
                                                   hit_face, hit_location,
                                                   epsilon=.0000001)

            self.cleanup_path(start_loc, hit_location, path)

            self.path_segments.append(path)

            self.geo_data = [geos, fixed, close, far]

    def cleanup_path(self, start_location, target_location, path):
        # It goes backwards for some reason
        path.reverse()
        path.pop(0)
        path.pop(0)
        path.insert(0, start_location)
        path.append(target_location)

    def grab_mouse_move(self, context, x, y):
        hit, hit_loc, face_ind = self.raycast(context, x, y)

        if not hit:
            self.grab_cancel()
            return

        # check if first or end point and it's a non man edge!
        geos, fixed, close, far = self.geo_data

        hit_face = self.bme.faces[face_ind]
        self.key_points[-1] = (hit_loc, hit_face)

        if not all([v in fixed for v in hit_face.verts]):
            print('continue geo walk until we find it, then get it')
            continue_geodesic_walk(geos, fixed, close, far,
                                   target_location=hit_face,
                                   max_iters=100000)
        else:
            print('great we have already waked the geodesic this far')

        path_elements, path = gradient_descent(geos,
                                               hit_face, hit_loc,
                                               epsilon=.0000001)

        previous_loc, previous_face = self.key_points[-2]
        self.cleanup_path(previous_loc, hit_loc, path)

        self.path_segments[-1] = path

    def grab_initiate(self):
        if len(self.key_points) >= 2:
            self.grab_undo_loc, self.grab_undo_face = self.key_points[-1]
            self.grab_undo_segment = self.path_segments[-1]
            return True
        else:
            return False

    def grab_cancel(self):
        self.key_points[-1] = (self.grab_undo_loc, self.grab_undo_face)
        self.path_segments[-1] = self.grab_undo_segment
        return

    def grab_confirm(self):
        self.grab_undo_loc = None
        self.grab_undo_face = None
        self.grab_undo_segment = []
        return

    def draw(self, context):
        # Draw Keypoints
        mx = self.selected_obj.matrix_world
        for (location, face) in self.key_points:
            draw.draw_3d_points(
                context, [mx @ location], 8, color=(1, 0, 0, 1))

        # Draw segments
        if len(self.path_segments):
            for segment in self.path_segments:
                pts = [mx @ v for v in segment]
                draw.draw_polyline_from_3dpoints(
                    context, pts, (.2, .1, .8, 1), 3)

    def get_whole_path(self):
        pts = []

        for segment in self.path_segments:
            pts.extend(segment)

        return pts

    def raycast(self, context, x, y):
        region = context.region
        rv3d = context.region_data
        coord = x, y
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * 1000)
        mx = self.selected_obj.matrix_world
        imx = mx.inverted()

        res, loc, no, face_ind = self.selected_obj.ray_cast(
            imx @ ray_origin, imx @ ray_target - imx @ ray_origin)

        return res, loc, face_ind

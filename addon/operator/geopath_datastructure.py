import bmesh

from bpy_extras import view3d_utils
from functools import reduce
from enum import Enum
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
        self.grab_undo_segment = []

        self.point_size = 8
        self.circle_radius = 8
        self.point_color = (1, 0, 0, 1)
        self.line_color = (.2, .1, .8, 1)
        self.line_thickness = 3

        self.epsilon = .0000001
        self.max_iters = 100000

        # geos, fixed, close, far
        self.geo_data = []
        self.hover_point_index = None
        self.selected_point_index = None

    def click_add_point(self, context, x, y):

        hit, hit_location, face_ind = self.raycast(context, x, y)

        if not hit:
            return

        hit_face = self.bme.faces[face_ind]
        self.key_points.append((hit_location, hit_face))

        if len(self.key_points) < 2:
            return

        #  The elements just before the ones we just pushed
        start_loc, start_face = self.key_points[-2]

        geos, fixed, close, far = geodesic_walk(
            self.bme.verts, start_face, start_loc,
            hit_face, self.max_iters)

        path_elements, path = gradient_descent(
            geos, hit_face, hit_location, self.epsilon)

        self.cleanup_path(start_loc, hit_location, path)

        self.path_segments.append(path)

        self.geo_data.append((geos, fixed, close, far))

    def grab_mouse_move(self, context, x, y):

        hit, hit_loc, face_ind = self.raycast(context, x, y)

        if not hit:
            self.grab_cancel()
            return

        # look for keypoints to hover
        if self.selected_point_index is None:
            self.find_keypoint_hover(hit_loc)
            return

        # At least one segment
        if len(self.path_segments) == 0:
            return

        # otherwise move the selected point
        point_pos = self.selected_point_index
        hit_face = self.bme.faces[face_ind]

        # Starting point: affect only the segment before me
        if point_pos == 0:
            start_loc, start_face = self.key_points[point_pos]
            end_loc, end_face = self.key_points[point_pos+1]
            self.redo_geodesic_segment(
                point_pos, start_loc, start_face, end_loc, end_face)

        # Ending point: affect only the segment before me
        elif point_pos == len(self.key_points)-1:
            start_loc, start_face = self.key_points[point_pos-1]  # Prev point
            self.redo_geodesic_segment(
                point_pos-1, start_loc, start_face, hit_loc, hit_face)

        # In between segments, perform geodesic on both of them
        else:
            # Segment before keypoint
            start_loc, start_face = self.key_points[point_pos-1]
            end_loc, end_face = self.key_points[point_pos]
            self.redo_geodesic_segment(
                point_pos-1, start_loc, start_face, end_loc, end_face)

            # Segment after keypoint
            start_loc, start_face = self.key_points[point_pos]
            end_loc, end_face = self.key_points[point_pos+1]
            self.redo_geodesic_segment(
                point_pos, start_loc, start_face, end_loc, end_face)

        # Finally move the key_point
        self.key_points[point_pos] = (hit_loc, hit_face)

    def redo_geodesic_segment(self, segment_pos, start_loc,
                              start_face, end_loc, end_face):

        geos, fixed, close, far = geodesic_walk(
                self.bme.verts, start_face, start_loc,
                end_face, self.max_iters)

        path_elements, path = gradient_descent(
                geos, end_face, end_loc, self.epsilon)

        self.cleanup_path(start_loc, end_loc, path)
        self.path_segments[segment_pos] = path

    def geodesic_on_segment(self, segment_pos, hit_loc, hit_face):

        geos, fixed, close, far = self.geo_data[segment_pos]

        if not all([v in fixed for v in hit_face.verts]):
            continue_geodesic_walk(
                geos, fixed, close, far,
                hit_face, self.max_iters)

        path_elements, path = gradient_descent(
            geos, hit_face, hit_loc, self.epsilon)

        return path

    def grab_start(self):

        if (self.hover_point_index is None):
            return

        self.selected_point_index = self.hover_point_index
        print("Selected point index is {}".format(self.selected_point_index))
        self.hover_point_index = None

        self.grab_undo_loc, self.grab_undo_face = \
            self.key_points[self.selected_point_index]

        # start, only add the segment with its same index
        if self.selected_point_index == 0:
            self.grab_undo_segment.append(
                self.path_segments[self.selected_point_index]
            )
        # end, only the previous one
        elif self.selected_point_index == len(self.key_points)-1:
            self.grab_undo_segment.append(
                self.path_segments[self.selected_point_index-1]
            )
        # in the middle of two segments
        else:
            self.grab_undo_segment.append(
                self.path_segments[self.selected_point_index]
            )
            self.grab_undo_segment.append(
                self.path_segments[self.selected_point_index-1]
            )

        return True

    def grab_cancel(self):

        if self.selected_point_index is None:
            return

        self.key_points[self.selected_point_index] = \
            (self.grab_undo_loc, self.grab_undo_face)

        # start, only add the segment with its same index
        if self.selected_point_index == 0:
            self.path_segments[self.selected_point_index] = \
                self.grab_undo_segment[0]
        # end, only the previous one
        elif self.selected_point_index == len(self.key_points)-1:
            self.path_segments[self.selected_point_index-1] = \
                self.grab_undo_segment[0]
        # in the middle of two segments
        else:
            self.path_segments[self.selected_point_index] = \
                self.grab_undo_segment[0]
            self.path_segments[self.selected_point_index-1] = \
                self.grab_undo_segment[1]

        return

    def grab_finish(self):
        self.grab_undo_loc = None
        self.grab_undo_face = None
        self.grab_undo_segment = []
        self.selected_point_index = None
        print("Selected point index finished")
        return

    def draw(self, context, plugin_state):

        mx = self.selected_obj.matrix_world

        points = [mx @ location for (location, face) in self.key_points]

        # Draw Keypoints
        draw.draw_3d_points(context, points,
                            self.point_size, self.point_color)

        if plugin_state == Geodesic_State.GRAB:
            draw.draw_3d_circles(context, points,
                                 self.circle_radius, self.point_color)

        # Draw segments
        if len(self.path_segments):
            draw.draw_polyline_from_3dpoints(context, self.get_whole_path(),
                                             self.line_color,
                                             self.line_thickness)

    def cleanup_path(self, start_location, target_location, path):
        # It goes backwards for some reason
        path.reverse()
        path.pop(0)
        path.pop(0)
        path.insert(0, start_location)
        path.append(target_location)

    def get_whole_path(self):
        mx = self.selected_obj.matrix_world
        return reduce(lambda a, b: a + [mx @ point for point in b],
                      self.path_segments, [])

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

    def find_keypoint_hover(self, point):

        if point is None:
            self.hover_point_index = None
            return

        key_points = [key_point for (key_point, key_face) in self.key_points]

        selected_keypoints = list(
            filter(lambda x: (x-point).length <= 0.006, key_points)
        )

        if selected_keypoints:
            self.hover_point_index = key_points.index(selected_keypoints[0])
            # print("Point found {}".format(self.hover_point_index))


class Geodesic_State(Enum):
    MAIN = 1
    GRAB = 2

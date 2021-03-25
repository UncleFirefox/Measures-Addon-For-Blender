import bmesh
from bmesh.types import BMFace, BMesh

from bpy_extras import view3d_utils
from functools import reduce
from enum import Enum

from mathutils import Vector
from ..algorithms.geodesic_vertices import \
    geodesic_walk, continue_geodesic_walk, gradient_descent
from mathutils.geometry import intersect_point_line
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

        self.key_verts = []
        self.path_segments = []

        self.grab_undo_vert = None
        self.grab_undo_segment = []

        self.point_size = 8
        self.circle_radius = 8
        self.point_color = (1, 0, 0, 1)
        self.point_select_color = (0, 1, 0, 1)
        self.line_color = (.2, .1, .8, 1)
        self.line_thickness = 3
        self.debug_color = (1, 1, 0, 1)

        self.epsilon = .0000001
        self.max_iters = 100000
        self.distance_threshold = 0.006

        # geos, fixed, close, far
        self.geo_data = [None, None]
        self.hover_point_index = None
        self.selected_point_index = None

        self.insert_key_point = None
        self.insert_segment_index = None
        self.is_inserting = False

        self.is_debugging = False

    def click_add_point(self, context, x, y):

        hit, hit_location, face_ind = self.raycast(context, x, y)

        if not hit:
            return

        # print("Calling add point")

        hit_face = self.bme.faces[face_ind]

        vert = self.decide_vert_from_face(self.bme, hit_location, hit_face,
                                          self.distance_threshold*0.5)

        self.key_verts.append(vert)

        if len(self.key_verts) < 2:
            return

        #  The elements just before the ones we just pushed
        start_vert = self.key_verts[-2]

        geos, fixed, close, far = geodesic_walk(
            self.bme.verts, start_vert, vert,
            self.max_iters
        )

        path_elements, path = gradient_descent(
            geos, vert, self.epsilon)

        # Gradient goes from vert to start_vert
        path.reverse()

        self.path_segments.append(path)

        print("Added segment with index {:} which goes from {} to {}"
              .format(len(self.path_segments)-1, path[0], path[-1])
              )

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

        new_vert = self.decide_vert_from_face(
            self.bme, hit_loc, self.bme.faces[face_ind],
            self.distance_threshold)

        # I have a segment before point
        if point_pos > 0:
            start_vert = self.key_verts[point_pos-1]
            self.redo_geodesic_segment(
                point_pos-1, start_vert, new_vert)

        # I have a segment after point
        if point_pos < len(self.key_verts)-1:
            end_vert = self.key_verts[point_pos+1]
            self.redo_geodesic_segment(
                point_pos, new_vert, end_vert)

        # Finally move the key_point
        self.key_verts[point_pos] = new_vert

    def grab_start(self):

        if (self.hover_point_index is None):
            return

        self.selected_point_index = self.hover_point_index
        self.hover_point_index = None

        self.grab_undo_vert = \
            self.key_verts[self.selected_point_index]

        # start, only add the segment with its same index
        if self.selected_point_index == 0:
            self.grab_undo_segment.append(
                self.path_segments[self.selected_point_index]
            )
        # end, only the previous one
        elif self.selected_point_index == len(self.key_verts)-1:
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

        self.hover_point_index = None

        if self.selected_point_index is None:
            return

        self.key_verts[self.selected_point_index] = \
            self.grab_undo_vert

        # start, only add the segment with its same index
        if self.selected_point_index == 0:
            self.path_segments[self.selected_point_index] = \
                self.grab_undo_segment[0]
        # end, only the previous one
        elif self.selected_point_index == len(self.key_verts)-1:
            self.path_segments[self.selected_point_index-1] = \
                self.grab_undo_segment[0]
        # in the middle of two segments
        else:
            self.path_segments[self.selected_point_index] = \
                self.grab_undo_segment[0]
            self.path_segments[self.selected_point_index-1] = \
                self.grab_undo_segment[1]

        self.selected_point_index = None

        return

    def grab_finish(self):
        self.grab_undo_vert = None
        self.grab_undo_segment = []

        # Small trick to keep hovering on the point after releasing mouse
        self.hover_point_index = self.selected_point_index

        self.selected_point_index = None
        self.geo_data = [None, None]

        return

    def erase_mouse_move(self, context, x, y):

        hit, hit_loc, face_ind = self.raycast(context, x, y)

        if not hit:
            context.window.cursor_set("DEFAULT")
            return

        context.window.cursor_set("ERASER")

        # look for keypoints to hover
        self.find_keypoint_hover(hit_loc)

    def erase_point(self):

        if (self.hover_point_index is None):
            return

        point_pos = self.hover_point_index

        # Reset hovering point
        self.hover_point_index = None

        # I have a segment before point
        segment_before = None
        if point_pos > 0:
            segment_before = self.path_segments[point_pos-1]

        # I have a segment after point
        segment_after = None
        if point_pos < len(self.key_verts)-1:
            segment_after = self.path_segments[point_pos]

        if segment_before:
            self.path_segments.remove(segment_before)
        if segment_after:
            self.path_segments.remove(segment_after)

        # Remove position from keypoints
        self.key_verts.pop(point_pos)

        # Redo geodesic path if needed
        if segment_before and segment_after:
            start_vert = self.key_verts[point_pos-1]
            end_vert = self.key_verts[point_pos]
            # Recreate the position
            self.path_segments.insert(point_pos-1, [])
            self.redo_geodesic_segment(
                point_pos-1, start_vert, end_vert)

            # Avoid having garbage in the geo cache
            self.geo_data[0] = None

    def erase_cancel(self, context):
        # Reset hovering point
        self.hover_point_index = None
        context.window.cursor_set("DEFAULT")

    def insert_mouse_move(self, context, x, y):

        hit, hit_loc, face_ind = self.raycast(context, x, y)

        if not hit:
            self.insert_key_point = None
            self.insert_segment_index = None
            context.window.cursor_set("DEFAULT")
            return

        context.window.cursor_set("NONE")
        hit_face = self.bme.faces[face_ind]

        # establish the key point
        self.insert_key_point = self.decide_vert_from_face(
            self.bme, hit_loc, hit_face, self.distance_threshold)

        if self.is_inserting:

            # Reassign key point
            self.key_verts[self.insert_segment_index+1] = \
                self.insert_key_point

            # First segment locations
            start_vert = self.key_verts[self.insert_segment_index]
            end_vert = self.insert_key_point

            # Recreate the segment
            self.redo_geodesic_segment(
                self.insert_segment_index,
                start_vert, end_vert)

            # Second segment locations
            start_vert = \
                self.key_verts[self.insert_segment_index+1]

            end_vert = \
                self.key_verts[self.insert_segment_index+2]

            # Recreate the segment
            self.redo_geodesic_segment(
                self.insert_segment_index+1,
                start_vert, end_vert)

            return

        # Try find an intersection with a segment
        intersect_index = self.get_segment_point_intersection(
            hit_loc, 0.0009)  # TODO: Is epsilon good enough?

        if (intersect_index is None):
            self.insert_segment_index = None
            return

        self.insert_segment_index = intersect_index

    def insert_start(self):

        if self.insert_segment_index is None:
            return

        # Add new segment
        self.path_segments.insert(self.insert_segment_index, [])

        # First segment locations
        start_vert = self.key_verts[self.insert_segment_index]
        end_vert = self.insert_key_point

        # Recreate the position
        self.redo_geodesic_segment(
            self.insert_segment_index,
            start_vert, end_vert)

        # Add the new key_point
        self.key_verts.insert(self.insert_segment_index+1,
                              self.insert_key_point)

        # Avoid having garbage in the geo cache
        self.geo_data[0] = None

        # Second segment locations
        start_vert = self.insert_key_point
        end_vert = self.key_verts[self.insert_segment_index+2]

        # Recreate the geodesic path on next segment
        self.redo_geodesic_segment(
            self.insert_segment_index+1,
            start_vert, end_vert)

        # Avoid having garbage in the geo cache
        self.geo_data[0] = None

        # Set a flag por grabbing until not released
        self.is_inserting = True

    def insert_finish(self):
        self.insert_key_point = None
        self.insert_segment_index = None
        self.is_inserting = False
        self.geo_data = [None, None]

    def insert_cancel(self, context):
        self.insert_key_point = None
        self.insert_segment_index = None
        self.is_inserting = False
        self.geo_data = [None, None]
        context.window.cursor_set("DEFAULT")

    def toggle_debugging(self):
        self.is_debugging = not self.is_debugging

    def get_segment_point_intersection(self, hit_loc, epsilon):

        # Find closest segment to point
        segment_index = self.get_closest_segment_index(
            hit_loc, self.path_segments)

        # Within that segment, look for the closest subsegment
        # We'll create the subsegment zipping pair by pair
        segment = self.path_segments[segment_index]
        inner_segment_index = self.get_closest_segment_index(
            hit_loc, list(zip(segment[:-1], segment[1:])))

        segment_distance = self.point_segment_distance(
            hit_loc, segment[inner_segment_index],
            segment[inner_segment_index+1])

        # If the distance is very close
        # we can safely assume we're in the segment
        if (segment_distance <= epsilon):
            return segment_index

        return None

    def get_closest_segment_index(self, hit_loc, segment_list):

        distances = list(map(lambda x:
                             self.point_segment_distance(hit_loc, x[0], x[-1]),
                             segment_list))

        index_min = min(range(len(distances)), key=distances.__getitem__)

        return index_min

    def point_segment_distance(self, point, segment_start, segment_end):
        return (point - (intersect_point_line(point,
                                              segment_start,
                                              segment_end)[0])).length

    def redo_geodesic_segment(self, segment_pos,
                              start_vert, end_vert):

        # print("Redoing segment {} from {} to {}"
        #       .format(segment_pos, start_vert.co, end_vert.co))

        # print("Currently from {} to {}"
        #       .format(self.path_segments[segment_pos][0],
        #               self.path_segments[segment_pos][-1]))

        geos, fixed, close, far = geodesic_walk(
                self.bme.verts, start_vert, end_vert, self.max_iters)

        path_elements, path = gradient_descent(
                geos, end_vert, self.epsilon)

        if path[-1] == start_vert.co:
            path.reverse()

        self.path_segments[segment_pos] = path

        # print("Result {} to {}".format(path[0], path[-1]))

    def draw(self, context, plugin_state):

        mx = self.selected_obj.matrix_world

        points = [mx @ location.co for location in self.key_verts]

        point_highlight_idx = \
            self.hover_point_index if self.hover_point_index is not None \
            else self.selected_point_index

        # Draw Keypoints
        draw.draw_3d_points(context, points,
                            self.point_size, self.point_color)

        if point_highlight_idx is not None:
            point = self.key_verts[point_highlight_idx].co
            draw.draw_3d_points(context, [mx @ point],
                                self.point_size,
                                self.point_select_color)

        if plugin_state in {Geodesic_State.GRAB, Geodesic_State.ERASE}:
            draw.draw_3d_circles(context, points,
                                 self.circle_radius, self.point_color)
            if point_highlight_idx is not None:
                point = self.key_verts[point_highlight_idx].co
                draw.draw_3d_circles(context, [mx @ point],
                                     self.circle_radius,
                                     self.point_select_color)

        elif (plugin_state == Geodesic_State.INSERT
              and self.insert_key_point):

            color = self.point_select_color \
                    if self.insert_segment_index is not None \
                    else self.point_color

            draw.draw_3d_circles(context, [mx @ self.insert_key_point.co],
                                 self.circle_radius, color)
            draw.draw_3d_points(context, [mx @ self.insert_key_point.co],
                                self.point_size, color)

        # Draw segments
        if len(self.path_segments):
            path = self.get_whole_path()
            draw.draw_polyline_from_3dpoints(context, path,
                                             self.line_color,
                                             self.line_thickness)
            # Debugging points
            if self.is_debugging:
                draw.draw_3d_points(context, path,
                                    self.point_size * .45,
                                    self.debug_color)

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

        self.hover_point_index = None

        selected_keypoints = list(
            filter(lambda x: (x.co-point).length <= self.distance_threshold,
                   self.key_verts)
        )

        if selected_keypoints:
            self.hover_point_index = \
                self.key_verts.index(selected_keypoints[0])

    def decide_vert_from_face_2(self, bm: BMesh, point: Vector,
                                face: BMFace, epsilon):
        # Case 1: If any of the verts in the face is close enough,
        # start from that vert
        distances = list(map(lambda x: (x.co-point).length,
                         face.verts))
        index_min = min(range(len(distances)), key=distances.__getitem__)

        return face.verts[index_min]

    def decide_vert_from_face(self, bm: BMesh, point: Vector,
                              face: BMFace, epsilon):

        # Case 1: If any of the verts in the face is close enough,
        # start from that vert
        distances = list(map(lambda x: (x.co-point).length,
                         face.verts))
        index_min = min(range(len(distances)), key=distances.__getitem__)

        if distances[index_min] <= epsilon:
            # print("Case 1: Vertex close enough")
            return face.verts[index_min]

        # Case 2: Am I close enough to an edge?
        # Create a vertex of the collision point
        # Create four faces out of the 2 we have connecting to the new vertex
        # set the created vertex as seed
        distances = list(map(lambda x: self.point_edge_distance(point, x),
                         face.edges))
        index_min = min(range(len(distances)), key=distances.__getitem__)

        if distances[index_min] <= epsilon:
            edge = face.edges[index_min]
            new_vert = bm.verts.new(point)
            faces = list(edge.link_faces)
            for f in faces:
                opposed_vert = [v for v in f.verts if v not in edge.verts][0]
                bm.faces.remove(f)
                for vert in edge.verts:
                    bm.faces.new((new_vert, vert, opposed_vert))
            bm.edges.remove(edge)

            # Refresh the structures
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            # Update object back
            bm.to_mesh(self.selected_obj.data)
            self.selected_obj.data.update()

            # print("Case 2: Edge was close enough")
            return new_vert

        # Case 3: If not case 1 or 2
        # Create 3 faces out of the old one, all connecting to the collision
        new_vert = bm.verts.new(point)
        for e in face.edges:
            bm.faces.new((e.verts[0], e.verts[1], new_vert))

        bm.faces.remove(face)

        # Refresh the structures
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Update object back
        bm.to_mesh(self.selected_obj.data)
        self.selected_obj.data.update()

        # print("Case 3: Collision was quite at the center")
        return new_vert

    def point_edge_distance(self, point, edge):
        return (point - (intersect_point_line(point,
                                              edge.verts[0].co,
                                              edge.verts[1].co)[0])
                ).length


class Geodesic_State(Enum):
    POINTS = 1
    GRAB = 2
    ERASE = 3
    INSERT = 4

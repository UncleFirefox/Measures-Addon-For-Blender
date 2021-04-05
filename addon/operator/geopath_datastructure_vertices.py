import bmesh
from bmesh.types import BMFace
import bpy

from bpy_extras import view3d_utils
from functools import reduce
from enum import Enum

from mathutils import Vector
from ..algorithms.geodesic_vertices import geodesic_walk
# from ..algorithms.geodesic_edge_flipping import geodesic_walk
from mathutils.geometry import intersect_point_line
from ..utility import draw
from ..utility.geometry import create_face_with_ccw_normal
from ..utility.ray import mouse_raycast_to_scene


class GeoPath(object):
    '''
    A class which manages user placed points on an object to create a
    piecewise path of geodesics, adapted to the objects surface.
    '''
    def __init__(self, context, selected_obj):

        self.context = context
        self.selected_obj = selected_obj
        self.bme = bmesh.new()
        self.bme.from_mesh(selected_obj.data)
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()

        # Keep a backup of the original structure
        self.original_bme = self.bme.copy()

        self.sub_vert_undo = dict()

        non_tris = [f for f in self.bme.faces if len(f.verts) > 3]
        bmesh.ops.triangulate(self.bme, faces=non_tris)

        self.key_verts = []
        self.path_segments = []

        self.point_size = 8
        self.circle_radius = 8
        self.point_color = (1, 0, 0, 1)
        self.point_select_color = (0, 1, 0, 1)
        self.line_color = (.2, .1, .8, 1)
        self.line_thickness = 3
        self.debug_color = (1, 1, 0, 1)

        self.distance_threshold = 0.006

        # geos, fixed, close, far
        self.hover_point_index = None
        self.selected_point_index = None

        self.insert_cursor_info = None
        self.insert_segment_index = None
        self.insert_vert = None

        self.is_debugging = False

    def click_add_point(self, context, x, y):

        hit, hit_location, face_ind = self.raycast(context, x, y)

        if not hit:
            return

        hit_face = self.bme.faces[face_ind]

        vert = self.decide_vert_from_face(hit_location, hit_face,
                                          self.distance_threshold*0.5)

        self.key_verts.append(vert)

        if len(self.key_verts) < 2:
            return

        #  The elements just before the ones we just pushed
        start_vert = self.key_verts[-2]

        path = geodesic_walk(
            self.bme, start_vert, vert
        )

        self.path_segments.append(path)

    def grab_mouse_move(self, context, x, y):

        # At least one segment
        if len(self.path_segments) == 0:
            return

        hit, hit_loc, face_ind = self.raycast(context, x, y)

        if not hit:
            self.grab_cancel()
            return

        # look for keypoints to hover
        if self.selected_point_index is None:
            self.find_keypoint_hover(hit_loc)
            return

        # otherwise move the selected point
        point_pos = self.selected_point_index
        vert_moving = self.key_verts[point_pos]

        # If a vertex of the raycasted face is found in our key verts
        # it means we might make a mess if we carry on
        # we won't do any changes
        if any(x != vert_moving and x in self.key_verts
               for x in self.bme.faces[face_ind].verts):
            # print("I won't do any grabbing, bye!")
            return

        # Before deciding, try undoing
        if self.try_undo_subdivision(vert_moving) is True:
            # We'll need to do another raycast to get the new hit face
            hit, hit_loc, face_ind = self.raycast(context, x, y)

        new_vert = self.decide_vert_from_face(
            hit_loc, self.bme.faces[face_ind],
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
        # print(self.key_verts)

    def grab_start(self):

        if (self.hover_point_index is None):
            return

        self.selected_point_index = self.hover_point_index
        self.hover_point_index = None

        return True

    def grab_cancel(self):

        self.hover_point_index = None
        self.selected_point_index = None

        return

    def grab_finish(self):

        # Small trick to keep hovering on the point after releasing mouse
        self.hover_point_index = self.selected_point_index

        self.selected_point_index = None

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

    def erase_cancel(self, context):
        # Reset hovering point
        self.hover_point_index = None
        context.window.cursor_set("DEFAULT")

    def insert_mouse_move(self, context, x, y):

        hit, hit_loc, face_ind = self.raycast(context, x, y)

        if not hit:
            self.insert_cursor_info = None
            self.insert_segment_index = None
            self.insert_vert = None
            context.window.cursor_set("DEFAULT")
            return

        self.insert_cursor_info = (hit_loc, self.bme.faces[face_ind])
        context.window.cursor_set("NONE")

        if self.insert_vert is None:

            # Try find an intersection with a segment
            intersect_index = self.get_segment_point_intersection(
                hit_loc, 0.0009)  # TODO: Is epsilon good enough?

            # Bingo! We got an intersection (or was none)
            self.insert_segment_index = intersect_index

            return

        # If we reached this point it means we're dragging
        # the inserted point
        if self.try_undo_subdivision(self.insert_vert) is True:
            # We'll need to do another raycast to get the new hit face
            hit, hit_loc, face_ind = self.raycast(context, x, y)

        # establish the key point
        new_vert = self.decide_vert_from_face(
            hit_loc, self.bme.faces[face_ind], self.distance_threshold)

        # Reassign key point
        self.key_verts[self.insert_segment_index+1] = \
            new_vert

        # First segment locations
        start_vert = self.key_verts[self.insert_segment_index]
        end_vert = new_vert

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

    def insert_start(self):

        # Check whether when moving we reached
        # an intersection
        if self.insert_segment_index is None:
            return

        location, face = self.insert_cursor_info

        insert_vert = self.decide_vert_from_face(
            location, face, self.distance_threshold)

        # Very edge case but if we get a vertex
        # that was already assigned this will protect
        # from deleting and recreating geometry
        # making the whole chain blow up
        if insert_vert in self.key_verts:
            # print("I wont do insertion here, bye!")
            return

        # Add new segment
        self.path_segments.insert(self.insert_segment_index, [])

        # First segment locations
        start_vert = self.key_verts[self.insert_segment_index]
        end_vert = insert_vert

        # Recreate the position
        self.redo_geodesic_segment(
            self.insert_segment_index,
            start_vert, end_vert)

        # Add the new key_point
        self.key_verts.insert(self.insert_segment_index+1,
                              insert_vert)

        # Second segment locations
        start_vert = insert_vert
        end_vert = self.key_verts[self.insert_segment_index+2]

        # Recreate the geodesic path on next segment
        self.redo_geodesic_segment(
            self.insert_segment_index+1,
            start_vert, end_vert)

        # Set vertex property that will remain
        # until we release the mouse button
        self.insert_vert = insert_vert

    def insert_finish(self):
        self.insert_cursor_info = None
        self.insert_segment_index = None
        self.insert_vert = None

    def insert_cancel(self, context):
        self.insert_cursor_info = None
        self.insert_segment_index = None
        self.insert_vert = None
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

        path = geodesic_walk(self.bme, start_vert, end_vert)

        self.path_segments[segment_pos] = path

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
              and self.insert_cursor_info):

            color = self.point_select_color \
                    if self.insert_segment_index is not None \
                    else self.point_color

            draw.draw_3d_circles(context, [mx @ self.insert_cursor_info[0]],
                                 self.circle_radius, color)
            draw.draw_3d_points(context, [mx @ self.insert_cursor_info[0]],
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

        mouse_pos = (x, y)

        origin = view3d_utils.region_2d_to_origin_3d(
            context.region, context.region_data, mouse_pos)
        direction = view3d_utils.region_2d_to_vector_3d(
            context.region, context.region_data, mouse_pos)

        res, loc, normal, face_ind, object, matrix = context.scene.ray_cast(
            context.view_layer.depsgraph, origin, direction)

        return res, self.selected_obj.matrix_world.inverted() @ loc, face_ind

    def find_keypoint_hover(self, point):

        self.hover_point_index = None

        selected_keypoints = list(
            filter(lambda x: (x.co-point).length <= self.distance_threshold,
                   self.key_verts)
        )

        if selected_keypoints:
            self.hover_point_index = \
                self.key_verts.index(selected_keypoints[0])

    def decide_vert_from_face(self, point: Vector,
                              face: BMFace, epsilon):

        bm = self.bme

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
                    create_face_with_ccw_normal(
                        bm, new_vert, vert, opposed_vert)

            # Store undo of vertex
            self.sub_vert_undo[new_vert] = (
                Geodesic_Subdivide.EDGE,
                (edge.verts[0], edge.verts[1])
            )

            bm.edges.remove(edge)

            self.save_bm_to_object()

            # print("Case 2: Edge was close enough")
            return new_vert

        # Case 3: If not case 1 or 2
        # Create 3 faces out of the old one, all connecting to the collision
        new_vert = bm.verts.new(point)
        for e in face.edges:
            create_face_with_ccw_normal(
                bm, e.verts[0], e.verts[1], new_vert)

        bm.faces.remove(face)

        self.save_bm_to_object()

        # Store undo of vertex
        self.sub_vert_undo[new_vert] = (
            Geodesic_Subdivide.FACE,
            (None)
        )

        # print("Case 3: Collision was quite at the center")
        return new_vert

    def save_bm_to_object(self):
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()

        # Update objects back
        current_mode = bpy.context.object.mode
        bpy.ops.object.mode_set(mode='OBJECT')
        self.bme.to_mesh(self.selected_obj.data)
        self.selected_obj.data.update()
        bpy.ops.object.mode_set(mode=current_mode)

    def try_undo_subdivision(self, in_vert):

        if in_vert not in self.sub_vert_undo:
            return False  # There was not subdivision

        action, args = self.sub_vert_undo[in_vert]

        if action is Geodesic_Subdivide.EDGE:
            # Verts composing the original edge
            vert1, vert2 = args
            verts = [e.other_vert(in_vert) for e in in_vert.link_edges]
            faces = list(in_vert.link_faces)
            edges = list(in_vert.link_edges)
            for face in faces:
                self.bme.faces.remove(face)
            for edge in edges:
                self.bme.edges.remove(edge)
            for vert in [v for v in verts if v not in {vert1, vert2}]:
                create_face_with_ccw_normal(self.bme, vert1, vert2, vert)

        elif action is Geodesic_Subdivide.FACE:
            verts = [e.other_vert(in_vert) for e in in_vert.link_edges]
            faces = list(in_vert.link_faces)
            edges = list(in_vert.link_edges)
            for face in faces:
                self.bme.faces.remove(face)
            for edge in edges:
                self.bme.edges.remove(edge)
            create_face_with_ccw_normal(
                self.bme, verts[0], verts[1], verts[2])

        self.sub_vert_undo.pop(in_vert)
        self.bme.verts.remove(in_vert)
        self.save_bm_to_object()
        return True

    def point_edge_distance(self, point, edge):
        return (point - (intersect_point_line(point,
                                              edge.verts[0].co,
                                              edge.verts[1].co)[0])
                ).length

    def finish(self):
        self.bme.free()
        self.bme = self.original_bme
        self.save_bm_to_object()
        self.bme.free()


class Geodesic_State(Enum):
    POINTS = 1
    GRAB = 2
    ERASE = 3
    INSERT = 4


class Geodesic_Subdivide(Enum):
    EDGE = 1
    FACE = 2

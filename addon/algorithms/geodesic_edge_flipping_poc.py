'''
Created on April 1, 2021

@author: Albert Rodriguez (@UncleFirefox)

based on work by Nicholas Sharp and Keenan Crane
https://nmwsharp.com/media/papers/flip-geodesics/flip_geodesics.pdf
https://nmwsharp.com/research/flip-geodesics/

C++ implementation of the algorithm can be found here:
https://github.com/nmwsharp/flip-geodesics-demo

WARNING: This is just a proof of concept to see how far we could get without getting into
the intrisic world operations, does not work but illustrates how the algoritm works

'''

from bpy.types import Mesh
from ..utility.geometry import create_face_with_ccw_normal, get_angle_signed
from enum import Enum
from functools import reduce
from math import fabs, inf, degrees, pi
from queue import PriorityQueue
from typing import Tuple

from bmesh.types import BMEdge, BMFace, BMLoop, BMVert, BMesh
from mathutils import Vector
from mathutils.geometry import intersect_line_plane

EPS_ANGLE: float = 1e-5


class Angle_Type(Enum):
    SHORTEST = 0,
    LEFT_TURN = 1,
    RIGHT_TURN = 2


def geodesic_walk(bm: BMesh,
                  start_vert_idx: int,
                  end_vert_idx: int,
                  m: Mesh = None,
                  max_iters: int = 100000):
    '''
    bm - BMesh of the object

    start_vert_idx - Starting Vertex Id -> int

    end_vert_idx - Ending Vertex Id -> int

    m - (optional) selected mesh in the scene -> Mesh

    max_iters - (optional) limits number of marching steps

    '''

    # As the algoritm will modify the underlying structures
    # we'll make a copy of the BMesh
    bm_copy = bm.copy()
    bm_copy.verts.ensure_lookup_table()
    bm_copy.edges.ensure_lookup_table()
    bm_copy.faces.ensure_lookup_table()

    start_copy = bm_copy.verts[start_vert_idx]
    end_copy = bm_copy.verts[end_vert_idx]

    # Part 1: Perform a path as a reference
    edge_path: "list[BMEdge]" = dijkstra(bm_copy, start_copy, end_copy)

    # Populate the priority queue
    # queue = PriorityQueue()
    # for e1, e2 in zip(edge_path[:-1], edge_path[1:]):
    #     queue.put(
    #         (
    #             (get_minwedge_angle((e1, e2))[0]),
    #             (e1, e2)
    #         )
    #     )

    short_path: "list[BMEdge]" = iterative_shorten(
        bm_copy, edge_path, max_iters)

    path = reduce(lambda a, b:
                  a + [b.other_vert(a[-1])],
                  short_path,
                  [start_copy])

    # Yes, we need to copy positions as the
    # structure will be freed
    result = list([v.co.copy() for v in path])

    bm_copy.free()

    return result


def iterative_shorten(bm: BMesh,
                      path: "list[BMEdge]",
                      maxIterations: int) -> "list[BMEdge]":

    iterations = 0

    wedges: "list[float, tuple[BMEdge, BMEdge]]" = build_wedge_list(path)

    min_angle: float
    path_segment: Tuple[BMEdge, BMEdge]
    min_angle, path_segment = wedges.pop()

    while min_angle < pi and iterations < maxIterations:

        # Check if its a stale entry
        if not path_segment[0].is_valid or not path_segment[1].is_valid:
            continue

        curr_angle, angle_type = get_minwedge_angle(path_segment)

        insert_idx: int = path.index(path_segment[0])
        shortened_path = locally_shorten_at(bm, path_segment, angle_type)

        # We'll insert elements at a certain position, to keep order
        # we'll reverse
        shortened_path.reverse()

        # Replace the path segment with the new path
        path.pop(insert_idx)
        path.pop(insert_idx)
        for e in shortened_path:
            path.insert(insert_idx, e)

        wedges: "list[float, tuple[BMEdge, BMEdge]]" = build_wedge_list(path)
        min_angle, path_segment = wedges.pop()

        iterations += 1

    return path

    # TODO: Purge stale entries?
    # TODO: Stop on length threshold?


def build_wedge_list(path):

    wedges = list(
        map(lambda x: (get_minwedge_angle(x)[0], x),
            zip(path[:-1], path[1:]))
    )

    wedges.sort(key=lambda x: x[0])

    return wedges


def get_minwedge_angle(path_segment: Tuple[BMEdge, BMEdge]) \
                       -> Tuple[Angle_Type, float]:

    e1, e2 = path_segment

    common_vert = get_common_vert(e1, e2)

    v1 = e1.other_vert(common_vert).co - common_vert.co
    v2 = e2.other_vert(common_vert).co - common_vert.co

    angle = get_angle_signed(v1, v2, common_vert.normal)

    if fabs(angle) == pi:
        return (pi, Angle_Type.SHORTEST)

    if angle < 0:
        return (fabs(angle), Angle_Type.RIGHT_TURN)

    return (angle, Angle_Type.LEFT_TURN)


def locally_shorten_at(bm: BMesh,
                       path_segment: Tuple[BMEdge, BMEdge],
                       angle_type: Angle_Type) \
                       -> "list[BMEdge]":

    if angle_type == Angle_Type.SHORTEST:
        # Should now happen, you never know though
        print("Path was shortest")
        # return None

    # Compute the initial path length
    init_path_length = \
        path_segment[0].calc_length() + path_segment[1].calc_length()

    # The straightening logic below always walks CW,
    # so flip the ordering if this is a right turn
    s_prev: BMEdge
    s_next: BMEdge
    reversed: bool = False
    if angle_type == Angle_Type.LEFT_TURN:
        s_prev = path_segment[0]
        s_next = path_segment[1]
    else:
        s_prev = path_segment[1]
        s_next = path_segment[0]
        reversed = True

    # == Main logic: flip until a shorter path exists
    new_path: "list[BMEdge]" = [s_prev, s_next]
    pivot_vert: BMVert = get_common_vert(s_prev, s_next)

    # Reverse path so that we just need to check ccw angles
    new_path.reverse()

    while not is_local_geodesic(new_path):

        loop: BMLoop = [lo for lo in s_prev.link_loops
                        if lo.vert == s_prev.other_vert(pivot_vert)][0]

        loop = loop.link_loop_next

        while loop.edge != s_next:

            current_edge = loop.edge

            if is_edge_flippable(current_edge, pivot_vert):
                loop = flip_edge(bm, current_edge, pivot_vert)
            else:
                loop = loop.link_loop_radial_next

            loop = loop.link_loop_next

        new_path = get_new_path(
            [lo for lo in s_prev.link_loops
             if lo.vert == s_prev.other_vert(pivot_vert)][0],
            s_next.other_vert(pivot_vert)
        )

    # Build the list of edges representing the new path
    # measure the length of the new path along the boundary
    new_path_length: float = reduce(lambda a, b: a + b.calc_length(),
                                    new_path, .0)

    # Make sure the new path is actually shorter
    # (this would never happen in the Reals,
    # but can rarely happen if an edge is numerically
    # unflippable for floating point reasons)
    if new_path_length > init_path_length:
        print("New length was greater")
        # return None

    # Make sure the new path orientation matches
    # the orientation of the input edges
    if reversed:
        new_path.reverse()

    return new_path


def get_new_path(loop: BMLoop, end_vert: BMVert) \
                 -> "list[BMEdge]":

    result: "list[BMEdge]" = []

    while end_vert not in loop.edge.verts:
        loop = loop.link_loop_prev
        result.append(loop.edge)
        loop = loop.link_loop_prev.link_loop_radial_next

    return result


def is_local_geodesic(path: "list[BMEdge]") -> bool:

    for e1, e2 in zip(path[:-1], path[1:]):
        v_center = get_common_vert(e1, e2)
        v1 = e1.other_vert(v_center).co - v_center.co
        v2 = e2.other_vert(v_center).co - v_center.co
        angle = get_ccw_angle_vector(v1, v2, v_center.normal)
        print(degrees(angle))
        if angle < pi:
            return False

    return True


def is_edge_flippable(e: BMEdge, pivot_vert: BMVert) -> bool:

    # TODO: if (isFixed(e)) return false;

    prev_e = [loop for loop in e.link_loops
              if loop.vert == pivot_vert][0] \
        .link_loop_prev.edge

    next_e = [loop for loop in e.link_loops
              if loop.vert == e.other_vert(pivot_vert)][0] \
        .link_loop_next.edge

    # Check Bi < pi
    common_vert: BMVert = get_common_vert(e, prev_e)
    other_vert = e.other_vert(common_vert)
    v1: Vector = prev_e.other_vert(common_vert).co - other_vert.co
    v2: Vector = next_e.other_vert(common_vert).co - other_vert.co

    # Path is straightened enough
    # nothing to do here
    if get_ccw_angle_vector(v1, v2, other_vert.normal) >= pi:
        return False

    # According to the paper
    # Definition. An edge ij is flippable if i and j have
    # degree > 1, and the triangles containing ij form a
    # convex quadrilateral when laid out in the plane.

    # Degree check
    if len(e.verts[0].link_edges) < 2:
        return False
    if len(e.verts[1].link_edges) < 2:
        return False

    # Convexity check
    # /!\ WARNING: is_convex won't work if the normals
    # on the connected faces are not valid
    # be careful when recreating geometry with BMesh
    # alternatively we could use calc_face_angle_signed
    # NB: Strictly speaking we're interested in having the "straightest"
    # path possible if there is a short concavity it might be worth
    # to flip it anyway, so disabling for now
    # if not e.is_convex:
    #     return False

    # Manifold check
    # TODO: Should we also check self-intersecion vertices?
    if not e.is_manifold:
        return False

    # Boundary check
    if e.is_boundary:
        return False

    # TODO: Edge and face orientation checks
    # this might introduce side-effects reorienting faces

    # Get Edges of first face
    # e0_faces = e.link_faces[0].edges

    # Get Edges of second face
    # e1_faces = e.link_faces[1].edges
    # [...]

    return True


def flip_edge(bm: BMesh, e: BMEdge, pivot_vert: BMVert) \
              -> BMLoop:

    print("Flipping edge {}".format(e))

    # TODO: If the angle is completely flat
    # we could do a simpler edge flipping

    # As we don't do the projection with the signpost datastructure
    # what we'll do is simulate an edge flip performing an intersection
    # and creating 4 faces
    op_vert_1: BMVert = get_opposed_vert(e.link_faces[0], e)
    op_vert_2: BMVert = get_opposed_vert(e.link_faces[1], e)

    start_v = [loop for loop in e.link_loops if loop.vert == pivot_vert][0] \
        .link_loop_next.edge.other_vert(e.other_vert(pivot_vert))

    # end_v = [loop for loop in e.link_loops if loop.vert == pivot_vert][0] \
    #     .link_loop_radial_next.link_loop_next.edge.other_vert(pivot_vert)

    plane_no = e.verts[0].co - e.verts[1].co

    p = intersect_line_plane(e.verts[0].co, e.verts[1].co,
                             start_v.co, plane_no)

    print("New intersection point was {}".format(p))

    for face in list(e.link_faces):
        bm.faces.remove(face)

    intersection_vert = bm.verts.new(p)

    create_face_with_ccw_normal(bm, intersection_vert, op_vert_1, e.verts[0])
    create_face_with_ccw_normal(bm, intersection_vert, op_vert_1, e.verts[1])
    create_face_with_ccw_normal(bm, intersection_vert, op_vert_2, e.verts[0])
    create_face_with_ccw_normal(bm, intersection_vert, op_vert_2, e.verts[1])

    intersection_vert.normal = (start_v.co - p).cross(pivot_vert.co - p)

    print("Removing edge {}".format(e))
    bm.edges.remove(e)

    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.edges.ensure_lookup_table()
    bm.edges.index_update()
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()

    loop = [lo for lo in intersection_vert.link_loops
            if lo.edge.other_vert(intersection_vert)
            == pivot_vert][0]

    return loop


def get_opposed_vert(face: BMFace, edge: BMEdge) -> BMVert:
    return [v for v in face.verts if v not in edge.verts][0]


def get_edges_in_wedge(s_prev: BMEdge, s_next: BMEdge) -> "list[BMEdge]":

    # We'll get the clock wise aka left angle
    # between the edges in the wedge
    max_angle: float = get_clockwise_angle(s_prev, s_next)

    pivot_vert: BMVert = get_common_vert(s_prev, s_next)

    # We'll get only the left angle
    edges_with_angle = list(map(lambda e: (get_clockwise_angle(s_prev, e), e),
                            pivot_vert.link_edges))

    edges_filtered = list(filter(lambda x: x[0] >= 0 and x[0] <= max_angle,
                          edges_with_angle))

    edges_sorted = list(sorted(edges_filtered, key=lambda x: x[0]))

    edges = list(map(lambda x: x[1], edges_sorted))

    return edges


def is_within_wedge(start_edge: BMEdge,
                    end_edge: BMEdge,
                    max_angle: float) -> bool:

    common_vert = get_common_vert(start_edge, end_edge)

    v1: BMVert = start_edge.other_vert(common_vert).co - common_vert.co
    v2: BMVert = end_edge.other_vert(common_vert).co - common_vert.co

    angle_signed = v1.angle_signed(v2)

    # Is CW and the angle is lower than max_angle
    return angle_signed > 0 and angle_signed < max_angle


def is_geodesic(edge_path) -> bool:

    # Create the angles
    angles = map(lambda a: degrees(get_angles_signed(a[0], a[1])[0]),
                 zip(edge_path[:-1], edge_path[1:]))

    return any(angle for angle in angles if angle < pi)


def get_clockwise_angle(start_edge: BMEdge, end_edge: BMEdge) -> float:
    n = get_common_vert(start_edge, end_edge).normal
    v1, v2 = get_vectors(start_edge, end_edge)

    return get_clockwise_angle_vector(v1, v2, n)


def get_clockwise_angle_vector(v1: Vector, v2: Vector, n: Vector) -> float:
    angle = get_angle_signed(v1, v2, n)

    if angle < 0:
        return 2*pi-fabs(angle)

    return angle


def get_ccw_angle_vector(v1: Vector, v2: Vector, n: Vector) -> float:
    angle = get_angle_signed(v1, v2, n)

    if angle > 0:
        return 2*pi-angle

    return fabs(angle)


def get_angles_signed(start_edge: BMEdge, end_edge: BMEdge) \
                      -> Tuple[float, float]:

    v1, v2 = get_vectors(start_edge, end_edge)
    n = get_common_vert(start_edge, end_edge).normal

    left_angle = get_angle_signed(v1, v2, n)
    right_angle = -(2*pi-left_angle) if left_angle > 0 \
        else (2*pi-fabs(left_angle))

    result = (left_angle, right_angle)

    # print("left {} - right {}".format(
    # degrees(result[0]), degrees(result[1]))
    # )

    return result


def get_vectors(start_edge, end_edge):

    common_vert = get_common_vert(start_edge, end_edge)
    v1: Vector = start_edge.other_vert(common_vert).co - common_vert.co
    v2: Vector = end_edge.other_vert(common_vert).co - common_vert.co

    return v1, v2


def get_common_vert(start_edge, end_edge) -> BMVert:
    return [v for v in start_edge.verts if v in end_edge.verts][0]


def get_path_segment_verts(path_segment: Tuple[BMEdge, BMEdge]) \
                           -> Tuple[BMVert, BMVert, BMVert]:

    middle_vert = [v for v in path_segment[0].verts
                   if v in path_segment[1].verts][0]

    prev_vert = path_segment[0].other_vert(middle_vert)
    next_vert = path_segment[1].other_vert(middle_vert)

    return (prev_vert, middle_vert, next_vert)


def get_angle_type(left_angle: float, right_angle: float) -> Angle_Type:

    if left_angle < right_angle:
        if left_angle > (pi-EPS_ANGLE):
            return Angle_Type.SHORTEST
        return Angle_Type.LEFT_TURN
    else:
        if right_angle > (pi-EPS_ANGLE):
            return Angle_Type.SHORTEST
        return Angle_Type.RIGHT_TURN


class Node:
    @property
    def edges(self):
        return (e for e in self.vert.link_edges if not e.tag)

    def __init__(self, v):
        self.vert = v
        self.length = inf
        self.shortest_path: "list[BMEdge]" = []


def dijkstra(bm, v_start, v_target) -> "list[BMEdge]":
    for e in bm.edges:
        e.tag = False

    d = {v: Node(v) for v in bm.verts}
    node = d[v_start]
    node.length = 0

    visiting = [node]

    while visiting:

        node = visiting.pop(0)

        if node.vert is v_target:
            return d[v_target].shortest_path

        for e in node.edges:
            e.tag = True
            length = node.length + e.calc_length()
            v = e.other_vert(node.vert)

            visit = d[v]
            visiting.append(visit)
            if visit.length > length:
                visit.length = length
                visit.shortest_path = node.shortest_path + [e]

        visiting.sort(key=lambda n: n.length)

    return d[v_target].shortest_path

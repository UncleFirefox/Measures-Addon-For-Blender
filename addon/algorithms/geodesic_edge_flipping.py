'''
Created on April 1, 2021

@author: Albert Rodriguez (@UncleFirefox)

based on work by Nicholas Sharp and Keenan Crane
https://nmwsharp.com/media/papers/flip-geodesics/flip_geodesics.pdf
https://nmwsharp.com/research/flip-geodesics/

C++ implementation of the algorithm can be found here:
https://github.com/nmwsharp/flip-geodesics-demo
'''

from enum import Enum
from functools import reduce
from math import fabs, inf, degrees, pi
from queue import PriorityQueue
from typing import Tuple

from bmesh.types import BMEdge, BMFace, BMVert, BMesh
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_line_line

EPS_ANGLE: float = 1e-5


class Angle_Type(Enum):
    SHORTEST = 0,
    LEFT_TURN = 1,
    RIGHT_TURN = 2


def geodesic_walk(bm: BMesh, start_vert: BMVert, end_vert: BMVert,
                  max_iters=100000):
    '''
    bm - geometry holder

    start_vert - Starting Vertex -> BMVert

    end_vert - Ending Vertex -> BMVert

    max_iters - limits number of marching steps
    '''

    # As the algoritm will modify the underlying structures
    # we'll make a copy of the BMesh
    bm_copy = bm.copy()
    bm_copy.verts.ensure_lookup_table()
    bm_copy.edges.ensure_lookup_table()
    bm_copy.faces.ensure_lookup_table()

    start_copy = bm_copy.verts[start_vert.index]
    end_copy = bm_copy.verts[end_vert.index]

    # Part 1: Perform a path as a reference
    node = dijkstra(bm_copy,
                    start_copy,
                    end_copy)

    # if is_geodesic(node.shortest_path) is False:
    #     print("Path is not geodesic")

    # path = reduce(lambda a, b:
    #               a + [b.other_vert(a[-1])],
    #               node.shortest_path,
    #               [start_copy])

    # Yes, we need to copy positions as the
    # structure will be freed
    # result = list([v.co.copy() for v in path])
    # return result

    edge_path = node.shortest_path

    # Populate the priority queue
    queue = PriorityQueue()
    for e1, e2 in zip(edge_path[:-1], edge_path[1:]):
        queue.put((min(get_angles(e1, e2)), (e1, e2)))

    iterative_shorten(bm_copy, queue, 50000)

    bm_copy.free()

    return None


def iterative_shorten(bm: BMesh, queue: PriorityQueue, maxIterations: int):

    iterations = 0

    while queue.qsize() and iterations < maxIterations:

        min_angle: float
        path_segment: Tuple[BMEdge, BMEdge]

        min_angle, path_segment = queue.get()

        # Check if its a stale entry
        if not path_segment[0].is_valid or not path_segment[1].is_valid:
            continue

        angle_type, curr_angle = get_minwedge_angle(path_segment)

        if min_angle != curr_angle:
            continue  # angle has changed

        # TODO: Determine if wedge_is_clear is really necessary

        locally_shorten_at(bm, path_segment, angle_type)

        iterations += 1

        # TODO: Purge stale entries?
        # TODO: Stop on length threshold?


def get_minwedge_angle(path_segment: Tuple[BMEdge, BMEdge]) \
                       -> Tuple[Angle_Type, float]:

    left_angle, right_angle = get_angles(path_segment[0],
                                         path_segment[1])

    angle_type = get_angle_type(left_angle, right_angle)

    return (angle_type, min(left_angle, right_angle))


def locally_shorten_at(bm: BMesh,
                       path_segment: Tuple[BMEdge, BMEdge],
                       angle_type: Angle_Type):

    if angle_type == Angle_Type.SHORTEST:
        # nothing to do here
        return

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
    edges_in_wedge: "list[BMEdge]" = get_edges_in_wedge(s_prev, s_next)

    # Should not happen if angle_type was SHORTEST but you never know
    if edges_in_wedge == 2:
        return

    new_path: "list[BMEdge]" = []
    pivot_vert: BMVert = get_common_vert(s_prev, s_next)
    for i in range(1, len(edges_in_wedge)-1):

        if not is_edge_flippable(edges_in_wedge[i],
                                 edges_in_wedge[i-1],
                                 edges_in_wedge[i+1]):

            other_vert: BMVert = edges_in_wedge[i].other_vert(pivot_vert)

            # For now we know we'll need to take the
            # part on the outer arc
            next_edge = [ed for ed in other_vert.link_edges
                         if ed.other_vert(other_vert) ==
                         edges_in_wedge[i-1].other_vert(pivot_vert)][0]

            new_path.append(next_edge)
            continue

        e1, e2, updated_wedge = flip_edge(bm, edges_in_wedge[i], pivot_vert)
        print("Edge was flipped!")
        print("e1 is {} e2 is {} updated wedge is {}"
              .format(e1, e2, updated_wedge))

        # After altering the geometry, we'll add the path plus
        # the new edge to compare against in next iterations
        new_path.append(e1)
        new_path.append(e2)
        edges_in_wedge[i] = updated_wedge

    # Build the list of edges representing the new path
    # measure the length of the new path along the boundary
    new_path_length: float = reduce(lambda a, b: a + b.calc_length(),
                                    new_path, .0)

    # Make sure the new path is actually shorter
    # (this would never happen in the Reals,
    # but can rarely happen if an edge is numerically
    # unflippable for floating point reasons)
    if new_path_length > init_path_length:
        return

    # Make sure the new path orientation matches
    # the orientation of the input edges
    if reversed:
        new_path.reverse()

    # TODO: Replace the path segment with the new path
    # (most of the bookkeeping to update data structures happens in here)

    print(new_path)


def is_edge_flippable(e: BMEdge, prev_e: BMEdge, next_e: BMEdge) -> bool:

    # TODO: if (isFixed(e)) return false;

    # Check Bi < pi
    common_vert: BMVert = get_common_vert(e, prev_e)
    v0: Vector = prev_e.other_vert(common_vert).co - common_vert.co
    v1: Vector = next_e.other_vert(common_vert).co - common_vert.co

    # Path is straightened enough
    # nothing to do here
    if v1.angle(v0) >= pi:
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
    if not e.is_convex:
        return False

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
              -> Tuple[BMEdge, BMEdge]:

    # TODO: If the angle is completely flat
    # we could do a simpler edge flipping

    # As we don't do the projection with the signpost datastructure
    # what we'll do is simulate an edge flip performing an intersection
    # and creating 4 faces
    op_vert_1: BMVert = get_opposed_vert(e.link_faces[0], e)
    op_vert_2: BMVert = get_opposed_vert(e.link_faces[1], e)

    # Do the intersection, choosing p1 or p2 would result
    # on same vector
    p1, p2 = intersect_line_line(e.verts[0].co, e.verts[1].co,
                                 op_vert_1.co, op_vert_2.co)

    for face in list(e.link_faces):
        bm.faces.remove(face)

    intersection_vert = bm.verts.new(p1)

    create_face_with_ccw_normal(bm, op_vert_1, intersection_vert, e.verts[0])
    create_face_with_ccw_normal(bm, op_vert_1, intersection_vert, e.verts[1])
    create_face_with_ccw_normal(bm, op_vert_2, intersection_vert, e.verts[0])
    create_face_with_ccw_normal(bm, op_vert_2, intersection_vert, e.verts[1])

    e1 = [ed for ed in op_vert_1.link_edges
          if intersection_vert in ed.verts][0]
    e2 = [ed for ed in op_vert_1.link_edges
          if intersection_vert in ed.verts][0]

    bm.edges.remove(e)

    updated_edge: BMEdge = [ed for ed in pivot_vert.link_edges
                            if ed.other_vert(pivot_vert)
                            == intersection_vert][0]

    # Ensure the order of edge follows the order to reach the path
    # i.e ensure going from e1 to updated edge is CCW
    if get_angles_signed(e1, updated_edge)[0] < 0:
        return (e1, e2, updated_edge)
    else:
        return (e2, e1, updated_edge)


def create_face_with_ccw_normal(bm: BMesh,
                                v1: BMVert, v2: BMVert, v3: BMVert) -> BMFace:
    # Detect ccw
    if get_angle_signed((v1.co-v2.co), (v3.co-v2.co), v2.normal) < 0:
        return bm.faces.new((v3, v2, v1))
    else:
        return bm.faces.new((v1, v2, v3))


def get_opposed_vert(face: BMFace, edge: BMEdge) -> BMVert:
    return [v for v in face.verts if v not in edge.verts][0]


def get_edges_in_wedge(s_prev: BMEdge, s_next: BMEdge) -> "list[BMEdge]":

    # We'll get the clock wise aka left angle
    # between the edges in the wedge
    max_angle: float = get_angles_signed(s_prev, s_next)[0]

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


def get_angles(start_edge: BMEdge, end_edge: BMEdge) \
                      -> Tuple[float, float]:

    v1, v2 = get_vectors(start_edge, end_edge)

    left_angle = v1.angle(v2)
    right_angle = 2*pi-left_angle

    result = (left_angle, right_angle)

    return result


def get_clockwise_angle(start_edge: BMEdge, end_edge: BMEdge) -> float:
    n = get_common_vert(start_edge, end_edge).normal
    v1, v2 = get_vectors(start_edge, end_edge)
    angle = get_angle_signed(v1, v2, n)

    if angle < 0:
        return 2*pi*fabs(angle)

    return angle


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


def get_angle_signed(v1: Vector, v2: Vector, n: Vector) -> float:
    # Implementing this idea:
    # https://math.stackexchange.com/questions/1027476/calculating-clockwise-anti-clockwise-angles-from-a-point
    matrix: Matrix = Matrix((v1, v2, n))
    matrix.transpose()
    det = matrix.determinant()
    angle = v1.angle(v2)

    if det < 0:  # clockwise
        return angle
    elif det > 0:  # anticlockwise
        return -angle
    else:
        return 0


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


def dijkstra(bm, v_start, v_target):
    for e in bm.edges:
        e.tag = False

    d = {v: Node(v) for v in bm.verts}
    node = d[v_start]
    node.length = 0

    visiting = [node]

    while visiting:

        node = visiting.pop(0)

        if node.vert is v_target:
            return d[v_target]

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

    return d[v_target]

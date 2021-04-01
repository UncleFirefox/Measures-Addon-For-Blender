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

from bmesh.types import BMEdge, BMVert, BMesh
from mathutils import Matrix, Vector

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

    iterative_shorten(queue, 50000)

    bm_copy.free()

    return None


def iterative_shorten(queue: PriorityQueue, maxIterations: int):

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

        locally_shorten_at(path_segment, angle_type)

        iterations += 1

        # TODO: Purge stale entries?
        # TODO: Stop on length threshold?


def get_minwedge_angle(path_segment: Tuple[BMEdge, BMEdge]) \
                       -> Tuple[Angle_Type, float]:

    left_angle, right_angle = get_angles(path_segment[0],
                                         path_segment[1])

    angle_type = get_angle_type(left_angle, right_angle)

    return (angle_type, min(left_angle, right_angle))


def locally_shorten_at(path_segment: Tuple[BMEdge, BMEdge],
                       angle_type: Angle_Type):

    if angle_type == Angle_Type.SHORTEST:
        # nothing to do here
        return

    # TODO: This does not seem to be used...
    # prev_vert, middle_vert, next_vert = get_path_segment_verts(path_segment)

    # TODO: Special case for loop consisting of a single self-edge?

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
    s_curr: BMEdge = edges_in_wedge.pop(0)
    while s_curr != s_next:
        if flip_edge_if_possible(s_curr, 1e-6):
            # flips++
            # Flip happened! Update data and continue processing
            # Re-check previous edge
            s_curr = None
        else:
            s_curr = None  # advance to next edge

    # Build the list of edges representing the new path
    # measure the length of the new path along the boundary
    new_path_length: float = .0
    s_curr = edges_in_wedge[0]
    new_path: "list[BMEdge]" = []
    while True:
        new_path.append(s_curr)
        new_path_length += s_curr.calc_length()
        if (s_curr == s_next):
            break
        s_curr = None

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


def flip_edge_if_possible(s_curr: BMEdge, possible_eps: float) -> bool:
    return False


def get_edges_in_wedge(s_prev: BMEdge, s_next: BMEdge) -> "list[BMEdge]":

    # We'll get the clock wise aka left angle
    # between the edges in the wedge
    max_angle: float = get_angles_signed(s_prev, s_next)[0]

    pivot_vert: BMVert = get_common_vert(s_prev, s_next)

    # We'll get only the left angle
    edges_with_angle = map(lambda e: (get_angles_signed(s_prev, e)[0], e),
                           pivot_vert.link_edges)

    edges = \
        list(
            map(lambda x: x[1],
                sorted(
                    filter(lambda x:
                           # filter anti clockwise edges
                           # check only the ones inside the wedge
                           x[0] > 0 and x[0] < max_angle,
                           edges_with_angle),
                    key=lambda x: x[0])  # sort by angle
                )
        )

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


def get_angles_signed(start_edge: BMEdge, end_edge: BMEdge) \
                      -> Tuple[float, float]:

    v1, v2 = get_vectors(start_edge, end_edge)

    left_angle = get_angle_signed(v1, v2)
    right_angle = -(2*pi-left_angle) if left_angle > 0 \
        else (2*pi-fabs(left_angle))

    result = (left_angle, right_angle)

    # print("left {} - right {}".format(
    # degrees(result[0]), degrees(result[1]))
    # )

    return result


def get_angle_signed(v1: Vector, v2: Vector) -> float:
    # Implementing this idea:
    # https://math.stackexchange.com/questions/1027476/calculating-clockwise-anti-clockwise-angles-from-a-point

    matrix: Matrix = Matrix((v1, v2, v1.cross(v2)))
    det = matrix.determinant()
    angle = v1.angle(v2)

    if det > 0:  # clockwise
        return angle
    elif det < 0:  # anticlockwise
        return -angle
    else:
        print("Why am I here?")
        return angle


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

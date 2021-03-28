from functools import reduce
from math import inf

from bmesh.types import BMVert, BMesh


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

    path = reduce(lambda a, b:
                  a + [b.other_vert(a[-1])],
                  node.shortest_path,
                  [start_copy])

    # Yes, we need to copy positions as the
    # structure will be freed
    result = list([v.co.copy() for v in path])

    bm_copy.free()

    return result


class Node:
    @property
    def edges(self):
        return (e for e in self.vert.link_edges if not e.tag)

    def __init__(self, v):
        self.vert = v
        self.length = inf
        self.shortest_path = []


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

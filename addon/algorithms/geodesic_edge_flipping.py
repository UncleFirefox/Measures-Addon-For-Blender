'''
Created on April 1, 2021

@author: Albert Rodriguez (@UncleFirefox)

based on work by Nicholas Sharp and Keenan Crane
https://nmwsharp.com/media/papers/flip-geodesics/flip_geodesics.pdf
https://nmwsharp.com/research/flip-geodesics/

C++ implementation of the algorithm can be found here:
https://github.com/nmwsharp/flip-geodesics-demo

This version uses the Python bindings exposed by the same authors

'''

from bmesh.types import BMVert, BMesh
from mathutils import Vector
import potpourri3d as pp3d
import numpy as np


def geodesic_walk(bm: BMesh, start_vert: BMVert, end_vert: BMVert,
                  max_iters=100000) -> "list[Vector]":

    print("Calling geodesic walk with start: {} end: {}".format(
        start_vert.index, end_vert.index))

    V = np.ndarray(shape=(len(bm.verts), 3), dtype=np.float64)
    F = np.ndarray(shape=(len(bm.faces), 3), dtype=np.int64)

    for i in range(len(bm.verts)):
        coordinates = bm.verts[i].co
        V[i] = np.array((coordinates.x, coordinates.y, coordinates.z))

    for i in range(len(bm.faces)):
        # We'll asume the mesh was triangulated
        vert_indexes = list([v_ind.index for v_ind in bm.faces[i].verts])
        F[i] = np.array((vert_indexes[0], vert_indexes[1], vert_indexes[2]))

    path_solver = pp3d.EdgeFlipGeodesicSolver(V, F)

    path_ptsA = path_solver.find_geodesic_path(v_start=start_vert.index,
                                               v_end=end_vert.index)

    result: "list[Vector]" = list(
        map(lambda x: Vector((x[0], x[2], x[2])), path_ptsA)
    )

    return result

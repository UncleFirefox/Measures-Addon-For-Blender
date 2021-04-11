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

from bmesh.types import BMesh
from mathutils import Vector
import potpourri3d as pp3d
import numpy as np
import time


def geodesic_walk(bm: BMesh, start_vert_idx: int, end_vert_idx: int,
                  max_iters=100000) -> "list[Vector]":

    # print("Calling geodesic walk with start: {} end: {}".format(
    #     start_vert_idx, end_vert_idx))

    total_start = time.time()

    start = time.time()

    V = np.ndarray(shape=(len(bm.verts), 3), dtype=np.float64)
    F = np.ndarray(shape=(len(bm.faces), 3), dtype=np.int64)

    end = time.time()

    print(f"Allocating the numpy array took {end-start}")

    start = time.time()

    for i in range(len(bm.verts)):
        coordinates = bm.verts[i].co
        V[i] = np.array((coordinates.x, coordinates.y, coordinates.z))

    for i in range(len(bm.faces)):
        # We'll asume the mesh was triangulated
        F[i] = np.array((bm.faces[i].verts[0].index,
                         bm.faces[i].verts[1].index,
                         bm.faces[i].verts[2].index))

    end = time.time()

    print(f"Mapping from bmesh to numpy took {end-start}")

    start = time.time()

    path_solver = pp3d.EdgeFlipGeodesicSolver(V, F)

    path_ptsA = path_solver.find_geodesic_path(v_start=start_vert_idx,
                                               v_end=end_vert_idx)

    end = time.time()

    print(f"Executing the algorithm took {end-start}")

    start = time.time()

    result: "list[Vector]" = list(
        map(lambda x: Vector((x[0], x[1], x[2])), path_ptsA)
    )

    end = time.time()

    print(f"Projecting results back took {end-start}")

    total_end = time.time()

    print(f"Total time taken: {total_end-total_start}")

    return result

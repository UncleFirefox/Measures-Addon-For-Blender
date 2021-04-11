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
from bpy.types import Mesh
from mathutils import Vector
import potpourri3d as pp3d
import numpy as np
# import time


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

    # print("Calling geodesic walk with start: {} end: {}".format(
    #     start_vert_idx, end_vert_idx))

    # total_start = time.time()

    # Fast allocation of data structures
    # https://developer.blender.org/rBae9d61e7fea25535803e92298f44b184c9190f76
    V = np.zeros((len(m.vertices), 3), dtype=np.float)
    m.vertices.foreach_get("co", V.ravel())

    F = np.zeros((len(m.polygons), 3), dtype=np.int)
    m.polygons.foreach_get("vertices", F.ravel())

    path_solver = pp3d.EdgeFlipGeodesicSolver(V, F)

    path_ptsA = path_solver.find_geodesic_path(v_start=start_vert_idx,
                                               v_end=end_vert_idx)

    result: "list[Vector]" = list(
        map(lambda x: Vector((x[0], x[1], x[2])), path_ptsA)
    )

    # total_end = time.time()

    # print(f"Total time taken: {total_end-total_start}")

    return result

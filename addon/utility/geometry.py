
from bmesh.types import BMFace, BMVert, BMesh
from mathutils import Matrix, Vector


def create_face_with_ccw_normal(bm: BMesh,
                                v1: BMVert, v2: BMVert, v3: BMVert) -> BMFace:
    # Detect ccw
    if get_angle_signed((v1.co-v2.co), (v3.co-v2.co), v2.normal) < 0:
        return bm.faces.new((v3, v2, v1))
    else:
        return bm.faces.new((v1, v2, v3))


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

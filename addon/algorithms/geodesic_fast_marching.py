'''
Created on April 11, 2021

@author: Albert Rodriguez Franco

Based on the original idea from Patrick Moore: https://github.com/patmo141/cut_mesh

'''
# python imports
# import time

# blender imports
import bmesh
from bmesh.types import BMesh
from bpy.types import Mesh
from mathutils import Vector, Quaternion, Matrix
from mathutils.geometry import intersect_point_line, intersect_line_line
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

    m - (optional) object representing the mesh in the scene -> Mesh

    max_iters - (optional) limits number of marching steps

    '''

    # start = time.time()

    # Copy the bmesh to do manipulations
    # on the object without affecting the caller
    # TODO: Clone only if necessary
    # my_bm = bm.copy()

    geos = dict()

    fixed_verts = set()
    close_verts = set()
    stop_targets = set()

    far = set(bm.verts)

    # Threshold value for gradient descent
    epsilon = .0000001

    start_vert = bm.verts[start_vert_idx]
    end_vert = bm.verts[end_vert_idx]

    geos[start_vert] = 0

    # Simulating face neighbors
    neighbors = [(e.calc_length(), e.other_vert(start_vert))
                 for e in start_vert.link_edges]

    for (distance, neighbor) in neighbors:
        geos[neighbor] = distance

    fixed_verts.update([start_vert])
    far.difference_update([start_vert])

    for ed in start_vert.link_edges:

        efs = [fc for fc in ed.link_faces if start_vert in fc.verts]

        if not len(efs):
            continue  # seed on border case

        ef = efs[0]

        nv = ed.other_vert(start_vert)

        close_verts.add(nv)
        v1 = min(ed.verts, key=geos.get)
        v2 = max(ed.verts, key=geos.get)

        T = calc_T(nv, v2, v1, ef, geos, ignore_obtuse=True)

        if nv in geos:
            # perhaps min() is better but its supposed
            # to be monotonicly increasing!
            geos[nv] = max(geos[nv], T)
        else:
            geos[nv] = T

    stop_targets.add(end_vert)

    iters = 0

    while (should_algorithm_continue(far, close_verts, iters, max_iters,
                                     stop_targets)):

        begin_loop(close_verts, far, geos, fixed_verts, stop_targets)
        iters += 1

    path_elements, path = gradient_descent(geos, end_vert, epsilon)

    # Resulting path from grading descent
    # goes from end_vert to start_vert,
    # were interested in the opposite
    path.reverse()

    # end = time.time()

    # print(f"Total time taken: {end-start}")

    return path


def calc_T(v3, v2, v1, f, geos, ignore_obtuse=False):
    if not ignore_obtuse and v2 not in geos:
        if not test_accute(v3.co, v1.co, v2.co):
            print('new vert is obtuse and we made a virtual edge')
            vco, v2, vcos = unwrap_tri_obtuse(v1, v3, f)
        else:
            print("V2 not in geos and triangle is not obtuse")

    # potentially use custom bmesh layer instead of a dictionary
    Tv1 = geos[v1]
    Tv2 = geos[v2]

    # calculate 2 origins which are the 2 intersections of 2 circles
    # ceneterd on v1 and v2 with radii Tv1, Tv2 respectively
    # http://mathworld.wolfram.com/Circle-CircleIntersection.html

    # transform points into the reference frame of v1 with v2 on x axis
    # http://math.stackexchange.com/questions/856666/how-can-i-transform-a-3d-triangle-to-xy-plane
    u = v2.co - v1.co  # x - axis
    v2x = u.length

    U = u.normalized()

    c = v3.co - v1.co
    w = u.cross(c)  # z axis

    W = w.normalized()
    V = U.cross(W)  # y axis   x,y,z = u,v,w

    # rotation matrix from principal axes
    T = Matrix.Identity(3)  # make the columns of matrix U, V, W
    T[0][0], T[0][1], T[0][2] = U[0], V[0], W[0]
    T[1][0], T[1][1], T[1][2] = U[1], V[1], W[1]
    T[2][0], T[2][1], T[2][2] = U[2], V[2], W[2]

    v3p = T.transposed() @ c
    # print('converted vector to coordinates on Vo so Z should be 0')
    # print(v3p)
    # solution to the intersection of the 2 circles
    A = 2 * Tv1**2 * v2x**2 - v2x**4 + 2 * Tv2**2 * v2x**2
    B = (Tv1**2 - Tv2**2)**2

    x = 1/2 * (v2x**2 + Tv1**2 - Tv2**2)/(v2x)
    y = 1/2 * ((A-B)**.5)/v2x

    if isinstance(x, complex):
        # print('x is complex')
        # print(x)
        x = 0
    if isinstance(y, complex):
        # print('y is complex, setting to 0')
        # print(A-B)
        # print(y)
        y = 0

    T3a = v3p - Vector((x, y, 0))
    T3b = v3p - Vector((x, -y, 0))
    T3 = max(T3a.length, T3b.length)

    return T3


def begin_loop(close, far, geos, fixed_verts, stop_targets):
    # Let Trial be the vertex in close with the smallest T value
    trial_v = min(close, key=geos.get)
    fixed_verts.add(trial_v)  # add this vertex to Fixed
    close.remove(trial_v)  # remove it from close

    if trial_v in stop_targets:
        stop_targets.remove(trial_v)

    # Compute the distance values for all vertices from Close (UNION)
    # Unprocessed which are incident to triangles containing Trial
    # and another vertex in fixed

    for f in trial_v.link_faces:
        # all link faces have Trial as one vert.  need exactly 1 fixed_vert
        fvs = [v for v in f.verts if v != trial_v and v in fixed_verts]
        cvs = [v for v in f.verts if v != trial_v and v not in fixed_verts]
        if len(fvs) == 1:

            if len(cvs) != 1:
                print('not one close vert in the triangle, what the heck')

            cv = cvs[0]
            fv = fvs[0]

            if cv not in close:
                close.add(cv)
                if cv in far:
                    far.remove(cv)

            T = calc_T(cv, trial_v, fv, f, geos)
            if cv in geos:
                # print('close vert already calced before')
                if T != geos[cv]:
                    # print('and the distance value is changing! %f, %f' \
                    #  % (geos[cv],T))
                    geos[cv] = min(geos[cv], T)  # maybe min?
            else:
                geos[cv] = T


def should_algorithm_continue(far, close, iters, max_iters,
                              stop_targets):
    return (len(far) and
            len(close) and
            ((max_iters and iters < max_iters) or max_iters is None) and
            (len(stop_targets)))


def gradient_descent(geos, start_vert, epsilon=.0000001):

    def grad_v(v):
        '''
        walk down from a vert
        '''
        eds = [ed for ed in v.link_edges
               if ed.other_vert(v) in geos
               and geos[ed.other_vert(v)] <= geos[v]]

        if len(eds) == 0:
            # print('lowest vert or local minima')
            return None, None, None

        fs = set()

        for ed in eds:
            fs.update(ed.link_faces)

        ffs = []
        for f in fs:
            if all([vert in geos for vert in f.verts]):
                ffs.append(f)

        # fs = set(filter(lambda x: all(vert in geos for vert in x.verts), fs))

        minf = min(ffs,
                   key=lambda x:
                   sum([geos[vrt] for vrt in x.verts if vrt in geos]))

        for ed in minf.edges:
            if v not in ed.verts:
                g = gradient_face(minf, geos)
                L = minf.calc_perimeter()

                v0, v1 = intersect_line_line(
                    ed.verts[0].co, ed.verts[1].co, v.co, v.co-L*g)

                V = v0 - ed.verts[0].co
                edV = ed.verts[1].co - ed.verts[0].co

                if V.length - edV.length > epsilon:
                    continue
                    # print('intersects outside segment')
                elif V.dot(edV) < 0:
                    # print('intersects behind')
                    continue
                else:
                    # print('regular edge crossing')

                    return v0, ed, minf

        # we were not able to walk through a face
        # print('must walk on edge')
        vs = [ed.other_vert(v) for ed in eds]
        minv = min(vs, key=geos.get)

        if geos[minv] > geos[v]:
            print('Found smallest geodesic already')
            return None, None, None

        return minv.co, minv, None

    def grad_f_ed(ed, p, last_face):
        # walk around non manifold edges
        if len(ed.link_faces) == 1:
            minv = min(ed.verts, key=geos.get)
            return minv.co, minv, None

        f = [fc for fc in ed.link_faces if fc != last_face][0]
        g = gradient_face(f, geos)
        L = f.calc_perimeter()

        # test for vert intersection
        for v in f.verts:
            v_inter, pct = intersect_point_line(v.co, p, p-L*g)

            delta = v.co - v_inter
            if delta.length < epsilon:
                # print('intersect vert')
                return v.co, v, None

        tests = [e for e in f.edges if e != ed]

        for e in tests:
            v0, v1 = intersect_line_line(
                e.verts[0].co, e.verts[1].co, p, p-L*g)

            V = v0 - e.verts[0].co
            edV = e.verts[1].co - e.verts[0].co
            Vi = v0 - p

            if V.length - edV.length > epsilon:
                # print('intersects outside segment')
                continue
            elif V.dot(edV) < 0:
                # print('intersects behind')
                continue
            # remember we watnt to travel DOWN the gradient
            elif Vi.dot(g) > 0:
                # print('shoots out the face, not across the face')
                continue
            else:
                # print('regular face edge crossing')
                return v0, e, f

        # we didn't intersect across an edge, or on a vert,
        # therefore, we should travel ALONG the edge

        vret = min(ed.verts, key=geos.get)
        return vret.co, vret, None

    iters = 0
    path_elements = []
    path_coords = []

    new_ele = start_vert
    new_coord = start_vert.co
    last_face = None

    while new_ele is not None and iters < 1000:
        if new_ele not in path_elements:
            path_elements += [new_ele]
            path_coords += [new_coord]
        else:
            # print('uh oh we reversed')
            # print('stopped walking at %i' % iters)
            return path_elements, path_coords

        if isinstance(path_elements[-1], bmesh.types.BMVert):
            new_coord, new_ele, last_face = grad_v(path_elements[-1])
        elif isinstance(path_elements[-1], bmesh.types.BMEdge):
            new_coord, new_ele, last_face = grad_f_ed(
                path_elements[-1], path_coords[-1], last_face)

        # if new_coord is None:
            # print('stopped walking at %i' % iters)

        iters += 1

    return path_elements, path_coords


def test_obtuse(f):
    '''
    tests if any verts have obtuse angles in a bmesh face
    if so returns True, vert_index, edge_index opposite (for splitting)
    if not, returns False, -1, -1

    follow notations set out here
    http://mathworld.wolfram.com/LawofCosines.html
    http://mathworld.wolfram.com/ObtuseTriangle.html

    internal bisector theorem
    http://www.codecogs.com/users/22109/gm_18.gif
    '''
    assert len(f.verts) == 3, "face is not a triangle: %i" % len(f.verts)

    A = f.verts[0]
    B = f.verts[1]
    C = f.verts[2]

    a = C.co - B.co  # side opposite a
    b = A.co - C.co  # side opposite b
    c = B.co - A.co  # side opposite c

    AA, BB, CC = a.length**2, b.length**2, c.length**2

    if AA + BB < CC:
        ob_bool = True
        cut_location = A.co + b.length/(a.length + b.length)*c
        v_ind = C.index
        e_ind = [e.index for e in f.edges if e.other_vert(A) == B][0]

    elif BB + CC < AA:
        ob_bool = True
        v_ind = A.index
        cut_location = B.co + c.length/(b.length + c.length)*a
        e_ind = [e.index for e in f.edges if e.other_vert(B) == C][0]

    elif CC + AA < BB:
        ob_bool = True
        v_ind = B.index
        cut_location = C.co + a.length/(c.length + a.length)*b
        e_ind = [e.index for e in f.edges if e.other_vert(C) == A][0]

    else:
        ob_bool, v_ind, e_ind, cut_location = False, -1, -1, Vector((0, 0, 0))

    return ob_bool, v_ind, e_ind, cut_location


def unwrap_tri_fan(bme, vcenter, ed_split, face_ref, max_folds=None):

    # this allows us to sort them

    loop = vcenter.link_loops[0]
    edges = [loop.edge]

    for i in range(0, len(vcenter.link_edges)-1):
        loop = loop.link_loop_prev.link_loop_radial_next
        if loop.edge in edges:
            print('bad indexing dummy')
            continue
        edges += [loop.edge]

    verts = [ed.other_vert(vcenter) for ed in edges]

    if max_folds is not None:
        max_folds = min(max_folds, len(edges)-1)
    else:
        max_folds = len(edges) - 1

    n = edges.index(ed_split)
    edges = edges[n:] + edges[0:n]
    verts = verts[n:] + verts[0:n]

    reverse = -1

    if edges[1] not in face_ref.edges:
        edges.reverse()
        verts.reverse()
        edges = [edges[-1]] + edges[1:]
        verts = [verts[-1]] + verts[1:]
        reverse = 1

    for i in range(1, len(edges)-1):
        if (i + 1) > max_folds:
            print('Maxed out on %i iterate' % i)
            print('Max folds %i' % max_folds)
            continue

        axis = vcenter.co - verts[i].co
        angle = edges[i].calc_face_angle_signed()

        if angle < 0:
            print('negative angle')
            if edges[i].verts[1] != vcenter:
                rev2 = -1
        else:
            rev2 = 1
        q = Quaternion(axis.normalized(), rev2 * reverse * angle)
        for n in range(i+1, len(edges)):
            print('changing vert %i with index %i' % (n, verts[n].index))
            verts[n].co = q * (verts[n].co - verts[i].co) + verts[i].co


def test_obtuse_pts(v0, v1, v2):

    a = v2 - v1  # side opposite a
    b = v0 - v2  # side opposite b
    c = v1 - v0  # side opposite c

    AA, BB, CC = a.length**2, b.length**2, c.length**2

    if AA + BB < CC:
        return True, 0

    elif BB + CC < AA:
        return True, 1

    elif CC + AA < BB:
        return True, 2

    else:
        return False, -1


def test_accute(v0, v1, v2):
    '''
    checks if angle formed by v0->v1 and v0->v2 is accute
    (the angle at v0 is acute
    '''
    a = v2 - v1  # side opposite a
    b = v0 - v2  # side opposite b
    c = v1 - v0  # side opposite c

    AA, BB, CC = a.length**2, b.length**2, c.length**2

    if CC + BB > AA:
        return True
    return False


def unwrap_tri_obtuse(vcenter, vobtuse, face):
    '''
    vcenter - a vertex within the wave front
    vobtuse - the obtuse vertex
    face - the face that vcenter and vobtuse share

    return -
        unwrapped_position, the actual vert, j number of unwraps
        v_cos[j], verts[j], j
    '''

    if vcenter not in face.verts:
        print('vcenter not in face')
        print('v index %i, face index %i' % (vcenter.index, face.index))

        for v in face.verts:
            print(v.index)

        vcenter.select = True
        face.select = True

    if vobtuse not in face.verts:
        print('vobtuse not in face')
        print('v index %i, face index %i' % (vobtuse.index, face.index))
        vobtuse.select = True
        face.select = True

        for v in face.verts:
            print(v.index)

    ed_base = [
        e for e in face.edges if vcenter in e.verts and vobtuse in e.verts
    ][0]

    ed_unfold = [
        e for e in face.edges if e in vcenter.link_edges and e != ed_base
    ][0]

    print(ed_base.index)
    print(ed_unfold.index)
    # this allows us to sort them

    loop = vcenter.link_loops[0]
    edges = [loop.edge]

    for i in range(0, len(vcenter.link_edges)-1):
        loop = loop.link_loop_prev.link_loop_radial_next
        if loop.edge in edges:
            print('bad indexing dummy')
            continue
        edges += [loop.edge]

    verts = [ed.other_vert(vcenter) for ed in edges]
    v_cos = [v.co for v in verts]

    N = len(edges)
    print('there are %i verts' % N)
    n = edges.index(ed_base)
    m = edges.index(ed_unfold)

    edges = edges[n:] + edges[0:n]
    verts = verts[n:] + verts[0:n]
    v_cos = v_cos[n:] + v_cos[0:n]
    print([v.index for v in verts])

    reverse = -1
    if m == (n-1) % N:
        edges.reverse()
        verts.reverse()
        v_cos.reverse()

        edges = [edges[-1]] + edges[0:len(edges)-1]
        verts = [verts[-1]] + verts[0:len(edges)-1]
        v_cos = [v_cos[-1]] + v_cos[0:len(edges)-1]
        reverse = 1

    elif m != (n+1) % N:
        print('uh oh, seems like the edges loops are trouble')

    print([v.index for v in verts])
    acute = False  # assume it's true,
    i = 1

    # for i in range(1,len(edges)-1):
    while i < len(edges)-1 and not acute:
        axis = vcenter.co - v_cos[i]
        print('unwrap edge axis vert is %i' % verts[i].index)
        angle = edges[i].calc_face_angle_signed()

        if edges[i].verts[1] != vcenter:
            rev2 = -1
        else:
            rev2 = 1
        q = Quaternion(axis.normalized(), rev2 * reverse * angle)
        for j in range(i+1, len(edges)):
            print('changing vert %i with index %i' % (j, verts[j].index))
            v_cos[j] = q * (v_cos[j] - v_cos[i]) + v_cos[i]

        acute = test_accute(vobtuse.co, v_cos[i+1], vcenter.co)
        if acute:
            print('We found an unwrapped acute vert')

        i += 1
    return v_cos[i], verts[i], v_cos


def gradient_face(f, geos):
    # http://saturno.ge.imati.cnr.it/ima/personal-old/attene/PersonalPage/pdf/steepest-descent-paper.pdf
    [vi, vj, vk] = f.verts

    U = vj.co - vi.co
    V = vk.co - vj.co
    N = U.cross(V)
    N.normalize()

    T = Matrix.Identity(3)  # make the columns of matrix U, V, W
    T[0][0], T[0][1], T[0][2] = U[0], U[1], U[2]
    T[1][0], T[1][1], T[1][2] = V[0], V[1], V[2]
    T[2][0], T[2][1], T[2][2] = N[0], N[1], N[2]

    GeoV = Vector((geos[vj]-geos[vi],
                   geos[vk]-geos[vj],
                   0))

    grad = T.inverted() @ GeoV
    grad.normalize()

    return grad


def next_vert(ed, face):
    next_fs = [f for f in ed.link_faces if f != face]

    if not len(next_fs):
        return None

    f = next_fs[0]
    v = [v for v in f.verts if v not in ed.verts][0]
    return v


def ring_neighbors(v):
    return [e.other_vert(v) for e in v.link_edges]

from addon.algorithms.geodesic import \
    continue_geodesic_walk, geodesic_walk, gradient_descent


class GeoPath(object):
    '''
    A class which manages a geodesic gradient on a BMesh
    '''
    def __init__(self, bme, bvh, mx):
        self.bme = bme
        non_tris = [f for f in self.bme.faces if len(f.verts) > 3]
        print('there are %i non tris' % len(non_tris))
        self.bvh = bvh
        self.mx = mx

        self.seed = None  # BMFace
        # Vector in local coordinates, preferable ony the seed face
        self.seed_loc = None

        self.target = None
        self.target_loc = None

        # geos, fixed, close, far
        self.geo_data = [dict(), set(), set(), set()]
        self.path = []

    def reset_vars(self):
        self.seed = None
        self.seed_loc = None

        self.target = None
        self.target_loc = None
        # geos, fixed, close, far
        self.geo_data = [dict(), set(), set(), set()]
        self.path = []
        self.path_elements = []

    # TODO? Maybe some get, set fns
    def add_seed(self, seed_bmface, loc):
        self.seed = seed_bmface
        self.seed_loc = loc

    def add_target(self, target_bmface, loc):
        self.target = target_bmface
        self.target_loc = loc
        return

    # TODO, this is more of a gradient field
    def calculate_walk(self, iterations=100000):
        geos, fixed, close, far = geodesic_walk(
            self.bme, self.seed, self.seed_loc, targets=[self.target],
            subset=None, max_iters=iterations, min_dist=None)

        self.geo_data = [geos, fixed, close, far]
        return

    def continue_walk(self, iterations):
        if self.found_target():
            return True

        geos, fixed, close, far = self.geo_data

        continue_geodesic_walk(
            self.bme, self.seed, self.seed_loc,
            geos, fixed, close, far,
            targets=[self.target], subset=None,
            max_iters=iterations, min_dist=None)

        if self.found_target():
            return True
        else:
            return False

    def gradient_descend(self):
        geos, fixed, close, far = self.geo_data
        self.path_elements, self.path = gradient_descent(
            self.bme, geos, self.target, self.target_loc, epsilon=.0000001)

    # TODO, turn this method into a property?
    def found_target(self):
        '''
        indicates whther the fast marching method of the geodesic distnace
        field has encountered the desired "taget" mesh element
        '''
        geos, fixed, close, far = self.geo_data
        if all([v in fixed for v in self.target.verts]):
            return True
        else:
            return False

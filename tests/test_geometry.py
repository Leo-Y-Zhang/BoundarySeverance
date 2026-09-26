# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Unit tests for the geometric primitives the whole analysis rests on.

These run offline in seconds. The integration check that needs live data is
validate_wall.py, which asserts the reconstructed ring against real landmarks;
these tests cover the functions that check does not exercise in isolation.
"""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from barriers import Grid  # noqa: E402
from cyprus import close_ring  # noqa: E402
from osm import haversine, local_xy, seg_intersect  # noqa: E402
from severance import measure, parity_inside, rotate  # noqa: E402
from wall import chain, point_in_ring, ring_area_km2  # noqa: E402


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertEqual(haversine(52.5, 13.4, 52.5, 13.4), 0.0)

    def test_known_distance_berlin_hamburg(self):
        # Berlin Mitte to Hamburg Rathaus, about 255 km
        d = haversine(52.5200, 13.4050, 53.5503, 9.9937) / 1000
        self.assertAlmostEqual(d, 255, delta=6)

    def test_symmetry(self):
        a = haversine(52.1, 13.1, 53.2, 10.2)
        b = haversine(53.2, 10.2, 52.1, 13.1)
        self.assertAlmostEqual(a, b, places=6)

    def test_one_degree_latitude(self):
        # a degree of latitude is about 111.2 km anywhere
        self.assertAlmostEqual(haversine(52.0, 13.0, 53.0, 13.0) / 1000,
                               111.2, delta=0.5)

    def test_long_distance_needs_the_arcsine(self):
        """At city scale asin(x) ~ x, so a dropped arcsine hides. Over a third
        of the globe it does not: London to Sydney is about 16,990 km."""
        d = haversine(51.5074, -0.1278, -33.8688, 151.2093) / 1000
        self.assertAlmostEqual(d, 16990, delta=60)

    def test_antipodal_is_half_the_circumference(self):
        d = haversine(0.0, 0.0, 0.0, 180.0) / 1000
        self.assertAlmostEqual(d, math.pi * 6371.0088, delta=1.0)


class TestProjection(unittest.TestCase):
    def test_origin_maps_to_zero(self):
        x, y = local_xy(52.5, 13.4, 52.5, 13.4)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_east_is_positive_x_north_is_positive_y(self):
        x, _ = local_xy(52.5, 13.5, 52.5, 13.4)
        _, y = local_xy(52.6, 13.4, 52.5, 13.4)
        self.assertGreater(x, 0)
        self.assertGreater(y, 0)

    def test_longitude_compresses_with_latitude(self):
        """A degree of longitude is shorter nearer the pole."""
        x_lo, _ = local_xy(10.0, 1.0, 10.0, 0.0)
        x_hi, _ = local_xy(60.0, 1.0, 60.0, 0.0)
        self.assertLess(x_hi, x_lo)

    def test_agrees_with_haversine_at_city_scale(self):
        x, y = local_xy(52.55, 13.45, 52.50, 13.40)
        planar = math.hypot(x, y)
        great_circle = haversine(52.50, 13.40, 52.55, 13.45)
        self.assertAlmostEqual(planar / great_circle, 1.0, delta=0.001)


class TestPointInRing(unittest.TestCase):
    SQUARE = [(0.0, 0.0), (0.0, 1000.0), (1000.0, 1000.0), (1000.0, 0.0),
              (0.0, 0.0)]

    def _inside(self, lat, lon, ring):
        return point_in_ring(lat, lon, ring, 0.0, 0.0)

    def test_centre_of_square_is_inside(self):
        ring = [(0, 0), (0, 2000), (2000, 2000), (2000, 0), (0, 0)]
        # ring is already in xy; place the test point via the same projection
        pt_x, pt_y = 1000.0, 1000.0
        lat = math.degrees(pt_y / 6371008.8)
        lon = math.degrees(pt_x / (6371008.8 * math.cos(0.0)))
        self.assertTrue(point_in_ring(lat, lon, ring, 0.0, 0.0))

    def test_far_point_is_outside(self):
        ring = [(0, 0), (0, 2000), (2000, 2000), (2000, 0), (0, 0)]
        lat = math.degrees(50000.0 / 6371008.8)
        self.assertFalse(point_in_ring(lat, 0.0, ring, 0.0, 0.0))

    def test_concave_ring_notch_is_outside(self):
        """An L-shape: a point in the missing corner must read as outside."""
        ring = [(0, 0), (0, 2000), (1000, 2000), (1000, 1000),
                (2000, 1000), (2000, 0), (0, 0)]
        # the notch is the region x>1000, y>1000
        x, y = 1500.0, 1500.0
        lat = math.degrees(y / 6371008.8)
        lon = math.degrees(x / 6371008.8)
        self.assertFalse(point_in_ring(lat, lon, ring, 0.0, 0.0))
        # while a point in the occupied arm is inside
        x2, y2 = 500.0, 1500.0
        lat2 = math.degrees(y2 / 6371008.8)
        lon2 = math.degrees(x2 / 6371008.8)
        self.assertTrue(point_in_ring(lat2, lon2, ring, 0.0, 0.0))


class TestRingArea(unittest.TestCase):
    def test_unit_square(self):
        ring = [(0, 0), (0, 1000), (1000, 1000), (1000, 0)]
        self.assertAlmostEqual(ring_area_km2(ring), 1.0, places=6)

    def test_area_is_orientation_independent(self):
        ring = [(0, 0), (0, 1000), (1000, 1000), (1000, 0)]
        self.assertAlmostEqual(ring_area_km2(ring),
                               ring_area_km2(list(reversed(ring))), places=9)

    def test_triangle(self):
        ring = [(0, 0), (2000, 0), (0, 2000)]
        self.assertAlmostEqual(ring_area_km2(ring), 2.0, places=6)


class TestSegIntersect(unittest.TestCase):
    def test_crossing_segments(self):
        self.assertTrue(seg_intersect((0, 0), (10, 10), (0, 10), (10, 0)))

    def test_parallel_segments_do_not_cross(self):
        self.assertFalse(seg_intersect((0, 0), (10, 0), (0, 5), (10, 5)))

    def test_disjoint_segments_do_not_cross(self):
        self.assertFalse(seg_intersect((0, 0), (1, 1), (5, 5), (6, 6)))


class TestRotate(unittest.TestCase):
    def setUp(self):
        self.rx = np.array([0.0, 100.0, 100.0, 0.0])
        self.ry = np.array([0.0, 0.0, 100.0, 100.0])

    def test_zero_rotation_is_identity(self):
        rx, ry = rotate(self.rx, self.ry, 0)
        np.testing.assert_array_equal(rx, self.rx)
        np.testing.assert_array_equal(ry, self.ry)

    def test_360_returns_to_start(self):
        rx, ry = rotate(self.rx, self.ry, 360)
        np.testing.assert_allclose(rx, self.rx, atol=1e-9)
        np.testing.assert_allclose(ry, self.ry, atol=1e-9)

    def test_rotation_preserves_distance_from_centroid(self):
        """This is the property the permutation null depends on: the placebo
        curve must be the same shape and size as the true one."""
        cx, cy = self.rx.mean(), self.ry.mean()
        before = np.hypot(self.rx - cx, self.ry - cy)
        for deg in (15, 47, 90, 233):
            rx, ry = rotate(self.rx, self.ry, deg)
            after = np.hypot(rx - rx.mean(), ry - ry.mean())
            np.testing.assert_allclose(np.sort(after), np.sort(before), atol=1e-9)

    def test_rotation_preserves_centroid(self):
        rx, ry = rotate(self.rx, self.ry, 137)
        self.assertAlmostEqual(rx.mean(), self.rx.mean(), places=9)
        self.assertAlmostEqual(ry.mean(), self.ry.mean(), places=9)

    def test_90_degrees_maps_x_axis_to_y_axis(self):
        rx, ry = rotate(np.array([0.0, 2.0]), np.array([0.0, 0.0]), 90)
        # centroid is (1, 0); the point at (2,0) goes to (1,1)
        self.assertAlmostEqual(rx[1], 1.0, places=9)
        self.assertAlmostEqual(ry[1], 1.0, places=9)


class TestParityInside(unittest.TestCase):
    def test_matches_scalar_implementation(self):
        rng = np.random.default_rng(0)
        ring = [(0, 0), (0, 2000), (2000, 2000), (2000, 0), (0, 0)]
        rx = np.array([p[0] for p in ring])
        ry = np.array([p[1] for p in ring])
        px = rng.uniform(-500, 2500, 200)
        py = rng.uniform(-500, 2500, 200)
        vec = parity_inside(px, py, rx, ry)
        for i in range(len(px)):
            lat = math.degrees(py[i] / 6371008.8)
            lon = math.degrees(px[i] / 6371008.8)
            scalar = point_in_ring(lat, lon, ring, 0.0, 0.0)
            self.assertEqual(bool(vec[i]), scalar, f"disagreement at point {i}")

    def test_horizontal_edges_do_not_break_parity(self):
        """Edges with y1 == y2 are skipped; the square has two of them."""
        ring = [(0, 0), (0, 1000), (1000, 1000), (1000, 0), (0, 0)]
        rx = np.array([p[0] for p in ring])
        ry = np.array([p[1] for p in ring])
        got = parity_inside(np.array([500.0]), np.array([500.0]), rx, ry)
        self.assertTrue(bool(got[0]))


class TestBarrierGrid(unittest.TestCase):
    def setUp(self):
        # a north-south barrier along lon = 13.40, from lat 52.40 to 52.60
        lats = np.linspace(52.40, 52.60, 60)
        self.line = [[(float(la), 13.40) for la in lats]]
        self.grid = Grid(self.line, 52.50, 13.40)

    def _xy(self, lat, lon):
        return local_xy(lat, lon, 52.50, 13.40)

    def test_segment_crossing_the_barrier_is_detected(self):
        a = self._xy(52.50, 13.38)
        b = self._xy(52.50, 13.42)
        got = self.grid.crosses(np.array([a[0]]), np.array([a[1]]),
                                np.array([b[0]]), np.array([b[1]]))
        self.assertTrue(bool(got[0]))

    def test_segment_parallel_to_the_barrier_is_not_detected(self):
        a = self._xy(52.45, 13.36)
        b = self._xy(52.55, 13.36)
        got = self.grid.crosses(np.array([a[0]]), np.array([a[1]]),
                                np.array([b[0]]), np.array([b[1]]))
        self.assertFalse(bool(got[0]))

    def test_segment_beyond_the_barrier_ends_is_not_detected(self):
        a = self._xy(52.70, 13.38)
        b = self._xy(52.70, 13.42)
        got = self.grid.crosses(np.array([a[0]]), np.array([a[1]]),
                                np.array([b[0]]), np.array([b[1]]))
        self.assertFalse(bool(got[0]))

    def test_vectorises_over_many_segments(self):
        a1 = self._xy(52.50, 13.38); b1 = self._xy(52.50, 13.42)   # crosses
        a2 = self._xy(52.45, 13.36); b2 = self._xy(52.55, 13.36)   # does not
        got = self.grid.crosses(np.array([a1[0], a2[0]]), np.array([a1[1], a2[1]]),
                                np.array([b1[0], b2[0]]), np.array([b1[1], b2[1]]))
        self.assertEqual(list(got), [True, False])

    def test_occupancy_is_a_small_fraction(self):
        self.assertGreater(self.grid.occupancy(), 0.0)
        self.assertLess(self.grid.occupancy(), 0.5)

    def test_short_segment_keeps_a_usable_middle(self):
        """skip_ends trims both ends so a quayside road is not counted as
        crossing the water beside it. On a segment short enough for the trim to
        bind, the clip must still leave a real middle band: here the crossing
        sits at 47 percent of the way along a ~100 m segment, inside the middle
        tenth the clip guarantees but outside any tighter trim."""
        deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(52.50)))
        a = self._xy(52.50, 13.40 - 47 * deg_per_m)
        b = self._xy(52.50, 13.40 + 53 * deg_per_m)
        got = self.grid.crosses(np.array([a[0]]), np.array([a[1]]),
                                np.array([b[0]]), np.array([b[1]]))
        self.assertTrue(bool(got[0]),
                        "a short off-centre crossing must still be detected")

    def test_road_running_alongside_the_barrier_is_not_a_crossing(self):
        """The reason skip_ends exists: a segment that merely starts on the
        quayside must not count as crossing the water."""
        deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(52.50)))
        a = self._xy(52.50, 13.40 + 2 * deg_per_m)      # 2 m from the barrier
        b = self._xy(52.50, 13.40 + 800 * deg_per_m)    # heading away
        got = self.grid.crosses(np.array([a[0]]), np.array([a[1]]),
                                np.array([b[0]]), np.array([b[1]]))
        self.assertFalse(bool(got[0]))

    def test_multi_crossing_parity_is_not_or(self):
        """Two barriers: a segment crossing both must still report True, and
        the implementation must not collapse to a plain OR of edge tests."""
        lats = np.linspace(52.40, 52.60, 60)
        two = [[(float(la), 13.40) for la in lats],
               [(float(la), 13.45) for la in lats]]
        g2 = Grid(two, 52.50, 13.40)
        a = self._xy(52.50, 13.38)
        b = self._xy(52.50, 13.47)
        got = g2.crosses(np.array([a[0]]), np.array([a[1]]),
                         np.array([b[0]]), np.array([b[1]]))
        self.assertTrue(bool(got[0]))


class TestChain(unittest.TestCase):
    @staticmethod
    def _as_set(pts):
        return {(round(a, 6), round(b, 6)) for a, b in pts}

    def _assert_is_a_path(self, pts, expected):
        """A chain is correct only if consecutive points are genuinely adjacent
        in the input. Checking the length alone lets a mis-ordered join pass."""
        self.assertEqual(len(pts), len(expected))
        self.assertEqual(self._as_set(pts), self._as_set(expected))
        for i in range(len(pts) - 1):
            self.assertNotEqual(pts[i], pts[i + 1], "duplicate consecutive point")
        # the path must run end to end, in one direction or its reverse
        self.assertIn(list(pts), [list(expected), list(reversed(expected))],
                      f"points present but mis-ordered: {pts}")

    def test_assembles_ordered_segments(self):
        members = [
            {"role": "", "geom": [{"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0}]},
            {"role": "", "geom": [{"lat": 0.0, "lon": 1.0}, {"lat": 1.0, "lon": 1.0}]},
        ]
        chains = chain(members, prec=6)
        self.assertEqual(len(chains), 1)
        self._assert_is_a_path(chains[0],
                               [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)])

    def test_assembles_reversed_segments(self):
        """A member given tail-first must still join, the right way round."""
        members = [
            {"role": "", "geom": [{"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0}]},
            {"role": "", "geom": [{"lat": 1.0, "lon": 1.0}, {"lat": 0.0, "lon": 1.0}]},
        ]
        chains = chain(members, prec=6)
        self.assertEqual(len(chains), 1)
        self._assert_is_a_path(chains[0],
                               [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)])

    def test_three_segments_join_in_geometric_order(self):
        members = [
            {"role": "", "geom": [{"lat": 0.0, "lon": 1.0}, {"lat": 0.0, "lon": 2.0}]},
            {"role": "", "geom": [{"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0}]},
            {"role": "", "geom": [{"lat": 0.0, "lon": 2.0}, {"lat": 0.0, "lon": 3.0}]},
        ]
        chains = chain(members, prec=6)
        self.assertEqual(len(chains), 1)
        self._assert_is_a_path(
            chains[0],
            [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0), (0.0, 3.0)])

    def test_disjoint_segments_stay_separate(self):
        members = [
            {"role": "", "geom": [{"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0}]},
            {"role": "", "geom": [{"lat": 5.0, "lon": 5.0}, {"lat": 5.0, "lon": 6.0}]},
        ]
        self.assertEqual(len(chain(members, prec=6)), 2)

    def test_tolerance_bridges_a_small_gap(self):
        """The Mauerweg needs an ~11 m snap; verify coarse precision joins."""
        members = [
            {"role": "", "geom": [{"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.00000}]},
            {"role": "", "geom": [{"lat": 0.0, "lon": 1.00004}, {"lat": 0.0, "lon": 2.0}]},
        ]
        self.assertEqual(len(chain(members, prec=6)), 2)   # strict: stays split
        self.assertEqual(len(chain(members, prec=4)), 1)   # tolerant: joins


class TestCloseRing(unittest.TestCase):
    def test_closure_encloses_the_north(self):
        line = [(35.15, 33.30), (35.16, 33.35), (35.15, 33.40)]
        ring = close_ring(line, north_lat=36.0, pad_lon=0.5)
        ring_xy = [local_xy(la, lo, 35.15, 33.35) for la, lo in ring]
        north = point_in_ring(35.50, 33.35, ring_xy, 35.15, 33.35)
        south = point_in_ring(34.80, 33.35, ring_xy, 35.15, 33.35)
        self.assertTrue(north, "a point north of the line should be inside")
        self.assertFalse(south, "a point south of the line should be outside")

    def test_ring_contains_the_original_line(self):
        line = [(35.15, 33.30), (35.16, 33.35), (35.15, 33.40)]
        ring = close_ring(line)
        for p in line:
            self.assertIn(p, ring)


def _synthetic_city(lat0, lon0, half=2000.0, step=100.0):
    """A square lattice of roads around (lat0, lon0), in lat/lon, with its graph."""
    from scipy.sparse import coo_matrix

    ticks = np.arange(-half, half + step / 2, step)
    gx, gy = np.meshgrid(ticks, ticks)
    x, y = gx.ravel(), gy.ravel()
    lat = lat0 + np.degrees(y / 6371008.8)
    lon = lon0 + np.degrees(x / (6371008.8 * math.cos(math.radians(lat0))))
    k = len(ticks)
    rows, cols = [], []
    for i in range(k):
        for j in range(k):
            a = i * k + j
            if j + 1 < k:
                rows.append(a); cols.append(a + 1)
            if i + 1 < k:
                rows.append(a); cols.append(a + k)
    w = np.full(len(rows), step)
    g = coo_matrix((w, (rows, cols)), shape=(len(x), len(x))).tocsr()
    return lat, lon, g + g.T, y


class TestMeasureSides(unittest.TestCase):
    """measure() must put every node on the side the full ring says it is on.

    It thins the ring before the parity test for speed. That thinning must not
    drop the vertex that closes the ring, nor the far corners that close an
    open line into a ring (cyprus.close_ring): losing them replaces the
    closure with a chord, and the chord can cut straight through the city.
    """

    def test_open_line_closed_into_a_ring(self):
        lat0, lon0 = 35.17, 33.37
        lat, lon, g, y = _synthetic_city(lat0, lon0)
        # an east-west divide through the middle of the city, ~30 m vertex
        # spacing; 2001 points, so a stride-3 thinning lands on the corners
        xs = np.arange(-30000.0, 30000.0 + 1, 30.0)
        self.assertEqual(len(xs) % 3, 0)
        line = [(lat0, lon0 + math.degrees(x / (6371008.8 * math.cos(math.radians(lat0)))))
                for x in xs]
        ring = close_ring(line)
        band = np.array([True] * len(line) + [False] * (len(ring) - len(line)))
        bbox = (lat.min(), lon.min(), lat.max(), lon.max())
        res = measure(lat, lon, g, ring, bbox, lat0, lon0, n_sources=60, seed=0,
                      band_mask=band, band=1000.0, dmin=300.0, dmax=1500.0,
                      exclude=50.0)
        self.assertIsNotNone(res, "no crossing pairs: the sides were lost")
        north = y > 0
        want = north[res["src"]] != north[res["dst"]]
        np.testing.assert_array_equal(res["cross"], want)

    def test_closed_ring_keeps_its_closing_edge(self):
        """A closed ring whose length is not 1 + a multiple of the stride: the
        closing edge must survive thinning, or every node in a strip level
        with it, all the way across the city, is put on the wrong side."""
        lat0, lon0 = 52.5, 13.4
        lat, lon, g, y = _synthetic_city(lat0, lon0)
        # rectangle: north edge along y = 0 through the city, the rest far
        # south; it starts and ends on the east edge at y = -990 m, so the
        # closing edge is level with the road row at y = -1000 m
        east = [(30000.0, v) for v in np.arange(-990.0, 0.0, 30.0)]
        north = [(v, 0.0) for v in np.arange(30000.0, -30000.0, -30.0)]
        west = [(-30000.0, v) for v in np.arange(0.0, -30000.0, -30.0)]
        south = [(v, -30000.0) for v in np.arange(-30000.0, 30000.0, 40.0)]
        back = [(30000.0, v) for v in np.arange(-30000.0, -990.0, 30.0)]
        pts = east + north + west + south + back
        pts.append(pts[0])
        self.assertNotEqual((len(pts) - 1) % 3, 0)
        k = 6371008.8
        ring = [(lat0 + math.degrees(py / k),
                 lon0 + math.degrees(px / (k * math.cos(math.radians(lat0)))))
                for px, py in pts]
        mask = np.array([abs(py) < 1 for _, py in pts])
        bbox = (lat.min(), lon.min(), lat.max(), lon.max())
        res = measure(lat, lon, g, ring, bbox, lat0, lon0, n_sources=60, seed=0,
                      band_mask=mask, band=1000.0, dmin=300.0, dmax=1500.0,
                      exclude=50.0)
        self.assertIsNotNone(res)
        inside = y < 0
        want = inside[res["src"]] != inside[res["dst"]]
        np.testing.assert_array_equal(res["cross"], want)


if __name__ == "__main__":
    unittest.main(verbosity=2)

# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Small routable lattices and explicit bootstrap draws check the statistic."""
import numpy as np
import pytest
from scipy.sparse import coo_matrix

import severance as sv


@pytest.fixture
def city():
    ticks = np.arange(-1500, 1501, 100, dtype=float)
    x, y = (a.ravel() for a in np.meshgrid(ticks, ticks))
    indices = np.arange(len(x)).reshape(len(ticks), len(ticks))
    rows = np.concatenate([indices[:, :-1].ravel(), indices[:-1, :].ravel()])
    cols = np.concatenate([indices[:, 1:].ravel(), indices[1:, :].ravel()])
    g = coo_matrix((np.full(len(rows), 100.0), (rows, cols)),
                   shape=(len(x), len(x))).tocsr()
    g = g + g.T
    lat, lon = np.degrees(y / 6371008.8), np.degrees(x / 6371008.8)
    line = [(la, 0) for la in np.degrees(np.arange(-3000, 3001, 25) / 6371008.8)]
    # A vertical dividing line with its closing corners far east of the city.
    ring = [*line, (line[-1][0], 1), (line[0][0], 1), line[0]]
    bbox = (lat.min(), lon.min(), lat.max(), lon.max())

    def measure(crossing_cost=0, **kwargs):
        network = g
        if crossing_cost:
            weights = 100.0 + crossing_cost * ((x[rows] > 0) != (x[cols] > 0))
            network = coo_matrix((weights, (rows, cols)), shape=g.shape).tocsr()
            network = network + network.T
        options = dict(n_sources=40, seed=4, band=800, dmin=200, dmax=1000, exclude=50)
        options.update(kwargs)
        return sv.measure(lat, lon, network, ring, bbox, 0, 0, **options)

    return x, y, measure


def test_measure_routes_distances_counts_and_ratio(city):
    x, y, measure = city
    result = measure()
    assert result is not None
    src, dst = result["src"], result["dst"]
    dx, dy = abs(x[src] - x[dst]), abs(y[src] - y[dst])
    crow = np.hypot(dx, dy)
    np.testing.assert_allclose(result["crow"], crow)
    np.testing.assert_allclose(result["circ"], (dx + dy) / crow)
    cross = (x[src] > 0) != (x[dst] > 0)
    np.testing.assert_array_equal(result["cross"], cross)
    for mask, name in [(cross, "cross"), (~cross, "same")]:
        assert result[f"n_{name}"] == int(mask.sum())
        assert result[f"med_{name}"] == pytest.approx(np.median(result["circ"][mask]))
        assert result[f"mean_{name}"] == pytest.approx(np.mean(result["circ"][mask]))
    assert result["ratio"] == pytest.approx(result["med_cross"] / result["med_same"])
    assert np.all(crow >= 200 - 1e-9)
    assert np.all(crow <= 1000 + 1e-9)
    assert np.all(abs((x[src] + x[dst]) / 2) <= 800 + 1e-9)
    assert np.all(abs(x[src]) > 50)
    assert np.all(abs(x[dst]) > 50)
    assert np.max(np.unique(src, return_counts=True)[1]) <= sv.MAX_TARGETS


def test_measure_ratio_for_a_boundary_with_real_route_cost(city):
    x, y, measure = city
    result = measure(crossing_cost=1000)
    assert result is not None
    src, dst = result["src"], result["dst"]
    cross = (x[src] > 0) != (x[dst] > 0)
    distance = abs(x[src] - x[dst]) + abs(y[src] - y[dst]) + 1000 * cross
    np.testing.assert_allclose(result["circ"], distance / result["crow"])
    assert result["med_cross"] > result["med_same"]
    assert result["ratio"] > 1.5
    assert result["ratio"] == pytest.approx(result["med_cross"] / result["med_same"])


class HorizontalBarrier:
    def crosses(self, xa, ya, xb, yb):
        return (ya < 0) != (yb < 0)


@pytest.mark.parametrize("control", ["barriers", "require"])
def test_measure_enforces_each_barrier_control(city, control):
    _, y, measure = city
    result = measure(n_sources=120, **{control: [HorizontalBarrier()]})
    assert result is not None
    crosses = (y[result["src"]] < 0) != (y[result["dst"]] < 0)
    assert np.all(crosses == (control == "require"))


def test_measure_rejects_too_few_total_pairs(city):
    *_, measure = city
    # Four sources yield 160 pairs (55 crossing, 105 same-side for this seed).
    # Both class-size checks pass, so only the total-pair guard rejects them.
    assert measure(n_sources=4, seed=1) is None


def test_measure_rejects_too_few_crossing_pairs(city, monkeypatch):
    *_, measure = city
    # A damaged side labelling with one inside node still produces many pairs,
    # but cannot provide 50 crossing pairs. Exercise the class-size guard.
    def one_inside(px, py, rx, ry):
        result = np.zeros(len(px), dtype=bool)
        result[0] = True
        return result

    monkeypatch.setattr(sv, "parity_inside", one_inside)
    assert measure() is None


def test_measure_discards_unreachable_destinations(city, monkeypatch):
    *_, measure = city
    original = sv.dijkstra

    def disconnected(*args, **kwargs):
        distances = original(*args, **kwargs)
        # Simulate a second disconnected component without changing sampling.
        distances[:, ::3] = np.inf
        return distances

    monkeypatch.setattr(sv, "dijkstra", disconnected)
    result = measure()
    assert result is not None
    assert np.all(result["dst"] % 3 != 0)
    assert np.isfinite(result["circ"]).all()


class ScriptedDraws:
    """Supply known resamples so percentile expectations can be hand checked."""
    def __init__(self, draws):
        self.draws = iter(draws)

    def choice(self, values, size, replace=True):
        assert replace is True
        draw = np.array(next(self.draws))
        assert len(draw) == size
        assert np.isin(draw, values).all()
        return draw


def test_pair_bootstrap_known_resamples(monkeypatch):
    res = {"circ": np.array([2., 8., 1., 2.]),
           "cross": np.array([True, True, False, False])}
    draws = ScriptedDraws([[2, 2], [1, 1], [8, 8], [2, 2], [2, 8], [1, 2]])
    monkeypatch.setattr(sv.np.random, "default_rng", lambda seed: draws)
    # The three ratios are 2, 4 and 10/3. Linear 2.5/97.5 percentiles:
    np.testing.assert_allclose(sv.bootstrap_ci(res, n=3), [31 / 15, 119 / 30])


def test_cluster_bootstrap_whole_sources_repeats_and_small_class_guard(monkeypatch):
    sources = np.repeat([10, 20, 30], [40, 50, 60])
    cross = np.concatenate([np.arange(40) < 5, np.arange(50) < 30, np.arange(60) < 35])
    circ = np.concatenate([np.where(cross[:40], 10., 1.),
                           np.where(cross[40:90], 2., 1.),
                           np.where(cross[90:], 6., 2.)])
    draws = ScriptedDraws([[10, 10, 10], [20, 20, 20], [30, 30, 30],
                           [10, 20, 30], [10, 10, 20]])
    monkeypatch.setattr(sv.np.random, "default_rng", lambda seed: draws)
    # The first draw has 15 crossing pairs and must be skipped. The remaining
    # cluster-median ratios are 2, 3, 6, 2, giving percentiles 2 and 5.775.
    res = {"src": sources, "circ": circ, "cross": cross}
    np.testing.assert_allclose(sv.cluster_bootstrap_ci(res, n=5), [2, 5.775])

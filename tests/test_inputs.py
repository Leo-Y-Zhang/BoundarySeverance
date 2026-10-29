# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Tiny offline Overpass responses exercise parsing, assembly and routing."""
import hashlib
import json

import numpy as np
import pytest
from scipy.sparse.csgraph import dijkstra

import cyprus
import graph
import osm
import segments
import wall


def geometry(*points):
    return [{"lat": la, "lon": lo} for la, lo in points]


@pytest.fixture
def cached_response(tmp_path, monkeypatch):
    monkeypatch.setattr(osm, "CACHE", str(tmp_path))

    def forbid_network(*args, **kwargs):
        pytest.fail("A cached response must never trigger a network request")

    monkeypatch.setattr(osm.urllib.request, "urlopen", forbid_network)

    def write(query, text, tag=""):
        key = hashlib.sha256(query.encode()).hexdigest()[:16]
        name = f"{tag}_{key}.json" if tag else f"{key}.json"
        (tmp_path / name).write_text(text)

    return write


@pytest.mark.parametrize("tag", ["", "roads"])
def test_cache_parses_exact_query_and_tag(cached_response, tag):
    cached_response("first", '{"elements": [{"id": 7}]}', tag)
    cached_response("second", '{"elements": []}', tag)
    assert osm.overpass("first", tag) == {"elements": [{"id": 7}]}
    assert osm.overpass("second", tag) == {"elements": []}


@pytest.mark.parametrize("text", ['{"elements": [', '{"elements": [Na', ''])
def test_truncated_cache_is_rejected(cached_response, text):
    cached_response("broken", text)
    with pytest.raises(json.JSONDecodeError):
        osm.overpass("broken")


def test_graph_weights_components_and_missing_node_breaks(monkeypatch):
    # The missing node must break the way, rather than inventing an edge 2--3.
    nodes = [{"type": "node", "id": i, "lat": 0, "lon": i * 0.001}
             for i in range(1, 10)]
    ways = [{"type": "way", "nodes": ids} for ids in
            ([1, 1, 2, 999, 3], [2, 4, 3], [5, 6], [7, 8])]
    monkeypatch.setattr(graph, "overpass", lambda *a, **k: {"elements": nodes + ways})
    lat, lon, g = graph.load("berlin", verbose=False)
    np.testing.assert_array_equal(lat, [0, 0, 0, 0])
    np.testing.assert_allclose(lon, [0.001, 0.002, 0.003, 0.004])
    unit = 6371008.8 * np.pi / 180 * 0.001
    np.testing.assert_allclose(g.toarray(), unit * np.array([
        [0, 1, 0, 0], [1, 0, 0, 2], [0, 0, 0, 1], [0, 2, 1, 0],
    ]))
    # 1 -> 2 -> 4 -> 3 takes four units, not the invented direct shortcut.
    assert dijkstra(g, indices=0)[2] == pytest.approx(4 * unit)


def test_member_parsers_keep_two_points_and_skip_incomplete_members(monkeypatch):
    good = geometry((0, 0), (0, 1))
    data = {"elements": [{"type": "node"}, {"type": "relation", "members": [
        {"role": "outer", "geometry": good}, {"geometry": []},
        {"geometry": geometry((9, 9))}, {},
    ]}]}
    monkeypatch.setattr(wall, "overpass", lambda *a, **k: data)
    assert wall.load_members() == [{"role": "outer", "geom": good}]
    assert cyprus._lines(data) == [[(0, 0), (0, 1)]]
    assert cyprus._lines({"elements": [{"members": None, "geometry": good}]}) == [
        [(0, 0), (0, 1)]]


def test_divide_chains_reversed_members_and_selects_longest(monkeypatch):
    data = {"elements": [{"members": [
        {"geometry": geometry((0, 1), (0, 2))},
        {"geometry": geometry((0, 1), (0, 0))},
        {"geometry": geometry((0, 3), (0, 2))},
        {"geometry": geometry((5, 5), (5, 6))},
    ]}]}
    monkeypatch.setattr(cyprus, "overpass", lambda *a, **k: data)
    line = cyprus.divide_line(verbose=False)
    expected = [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert line in (expected, expected[::-1])


def test_build_ring_filters_alternatives_and_closes_gap(monkeypatch):
    members = [{"role": "", "geom": geometry((0, 0), (0, 1), (1, 1))},
               {"role": "alternative", "geom": geometry((9, 9), (9, 10))}]
    monkeypatch.setattr(wall, "load_members", lambda: members)
    ring = wall.build_ring(verbose=False)
    assert ring[0] == ring[-1]
    assert set(ring) == {(0, 0), (0, 1), (1, 1)}
    assert len(ring) == 4


def test_classify_inner_and_outer_at_tolerance(monkeypatch):
    monkeypatch.setattr(segments, "city_boundary_points", lambda: [(0, 0)])
    delta = np.degrees(100 / 6371008.8)
    ring = [(0, 0), (delta, 0), (2 * delta, 0)]
    # Set tol to the computed distance to avoid floating point endpoint ambiguity.
    _, y = graph.project(np.array([delta]), np.array([0]), 0, 0)
    np.testing.assert_array_equal(segments.classify(ring, 0, 0, tol=y[0], verbose=False),
                                  [False, False, True])

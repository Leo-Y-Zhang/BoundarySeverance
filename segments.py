# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Split the Wall ring into its two politically distinct halves.

The 158 km loop is not one boundary. Roughly 43 km divided East from West
Berlin; the remaining ~112 km separated West Berlin from surrounding
Brandenburg and still coincides with the Berlin state boundary today. Only the
first is the inner-German urban division. We separate them exactly, by distance
to Berlin's present administrative boundary.
"""
import sys

import numpy as np
from scipy.spatial import cKDTree

from graph import project
from osm import overpass

sys.stdout.reconfigure(encoding="utf-8")

Q = """
[out:json][timeout:300];
rel["boundary"="administrative"]["admin_level"="4"]["name"="Berlin"];
out geom;
"""

CITY_LIMIT_TOL = 400.0  # metres; ring within this of the state line = outer ring


def city_boundary_points():
    d = overpass(Q, tag="berlin_admin")
    rels = [e for e in d["elements"] if e["type"] == "relation"]
    pts = []
    for r in rels:
        for m in r.get("members", []):
            for p in m.get("geometry") or []:
                pts.append((p["lat"], p["lon"]))
    return pts


def classify(ring, lat0, lon0, verbose=True, tol=CITY_LIMIT_TOL):
    """Return boolean mask over ring vertices: True = inner (East/West) Wall."""
    bpts = city_boundary_points()
    blat = np.array([p[0] for p in bpts])
    blon = np.array([p[1] for p in bpts])
    bx, by = project(blat, blon, lat0, lon0)
    tree = cKDTree(np.column_stack([bx, by]))

    rlat = np.array([p[0] for p in ring])
    rlon = np.array([p[1] for p in ring])
    rx, ry = project(rlat, rlon, lat0, lon0)
    d, _ = tree.query(np.column_stack([rx, ry]))
    inner = d > tol

    if verbose:
        from osm import haversine

        def seg_km(mask):
            tot = 0.0
            for i in range(len(ring) - 1):
                if mask[i] and mask[i + 1]:
                    tot += haversine(*ring[i], *ring[i + 1])
            return tot / 1000

        print(f"city boundary points: {len(bpts)}")
        print(f"inner (East/West Berlin) : {inner.sum():5d} vertices, {seg_km(inner):6.1f} km")
        print(f"outer (West Berlin/Brb.) : {(~inner).sum():5d} vertices, {seg_km(~inner):6.1f} km")
    return inner


if __name__ == "__main__":
    from fetch import CITIES
    from wall import build_ring
    bbox = CITIES["berlin"]["study_bbox"]
    classify(build_ring(), (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

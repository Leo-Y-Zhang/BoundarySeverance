# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Build a routable undirected road graph from the cached Overpass extract."""
import sys

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from fetch import CITIES, DRIVE
from osm import haversine, overpass

sys.stdout.reconfigure(encoding="utf-8")


def load(city, verbose=True):
    lo_lat, lo_lon, hi_lat, hi_lon = CITIES[city]["route_bbox"]
    q = f"""
    [out:json][timeout:900];
    (
      way["highway"~"{DRIVE}"]["area"!~"yes"]["access"!~"^(no|private)$"]
         ({lo_lat},{lo_lon},{hi_lat},{hi_lon});
    );
    out body;
    >;
    out skel qt;
    """
    data = overpass(q, tag=f"roads_{city}")

    coords = {}
    ways = []
    for e in data["elements"]:
        if e["type"] == "node":
            coords[e["id"]] = (e["lat"], e["lon"])
        elif e["type"] == "way":
            ways.append(e["nodes"])

    # index only nodes actually used by a kept way
    idx = {}
    for nds in ways:
        for n in nds:
            if n in coords and n not in idx:
                idx[n] = len(idx)

    n = len(idx)
    lat = np.zeros(n)
    lon = np.zeros(n)
    for osmid, i in idx.items():
        lat[i], lon[i] = coords[osmid]

    rows, cols, w = [], [], []
    for nds in ways:
        prev = None
        for osmid in nds:
            if osmid not in idx:
                prev = None
                continue
            cur = idx[osmid]
            if prev is not None and prev != cur:
                d = haversine(lat[prev], lon[prev], lat[cur], lon[cur])
                if d > 0:
                    rows.append(prev); cols.append(cur); w.append(d)
                    rows.append(cur); cols.append(prev); w.append(d)
            prev = cur

    g = csr_matrix((w, (rows, cols)), shape=(n, n))

    ncomp, labels = connected_components(g, directed=False)
    sizes = np.bincount(labels)
    keep = np.flatnonzero(labels == sizes.argmax())
    g = g[keep][:, keep]
    lat, lon = lat[keep], lon[keep]

    if verbose:
        print(f"{city}: {n} nodes, {len(w) // 2} undirected edges, "
              f"{ncomp} components; keeping largest = {len(keep)} nodes "
              f"({100 * len(keep) / n:.1f}%)")
    return lat, lon, g


def project(lat, lon, lat0, lon0):
    x = np.radians(lon - lon0) * 6371008.8 * np.cos(np.radians(lat0))
    y = np.radians(lat - lat0) * 6371008.8
    return x, y


if __name__ == "__main__":
    for c in sys.argv[1:] or ["berlin"]:
        load(c)

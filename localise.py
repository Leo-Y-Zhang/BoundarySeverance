"""Where along the inner Wall is the residual severance concentrated?"""
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from fetch import CITIES
from graph import load, project
from osm import overpass, haversine
from segments import classify
from severance import measure
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8")

BIN_M = 2000.0
MIN_PAIRS = 40

PLACES_Q = """
[out:json][timeout:300];
node["place"~"^(suburb|quarter|neighbourhood|borough)$"](52.35,13.05,52.68,13.70);
out;
"""


def place_names():
    d = overpass(PLACES_Q, tag="berlin_places")
    out = []
    for e in d["elements"]:
        n = e.get("tags", {}).get("name")
        if n:
            out.append((e["lat"], e["lon"], n))
    return out


def main():
    lat, lon, g = load("berlin")
    ring = build_ring()
    bbox = CITIES["berlin"]["study_bbox"]
    lat0 = (bbox[0] + bbox[2]) / 2
    lon0 = (bbox[1] + bbox[3]) / 2
    inner = classify(ring, lat0, lon0, verbose=False)

    res = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                  n_sources=900, seed=7, band_mask=inner)
    print(f"pairs: {res['n_cross']} crossing / {res['n_same']} same-side")

    # cumulative distance along the full ring, so contiguous arcs bin together
    cum = np.zeros(len(ring))
    for i in range(1, len(ring)):
        cum[i] = cum[i - 1] + haversine(*ring[i - 1], *ring[i])

    rlat = np.array([p[0] for p in ring])
    rlon = np.array([p[1] for p in ring])
    rx, ry = project(rlat, rlon, lat0, lon0)
    inner_idx = np.flatnonzero(inner)
    tree = cKDTree(np.column_stack([rx[inner_idx], ry[inner_idx]]))

    nx, ny = project(lat, lon, lat0, lon0)
    mx = (nx[res["src"]] + nx[res["dst"]]) / 2.0
    my = (ny[res["src"]] + ny[res["dst"]]) / 2.0
    _, nearest = tree.query(np.column_stack([mx, my]))
    vert = inner_idx[nearest]
    bins = (cum[vert] // BIN_M).astype(int)

    places = place_names()
    ptree = cKDTree(np.column_stack(project(
        np.array([p[0] for p in places]), np.array([p[1] for p in places]),
        lat0, lon0)))

    rows = []
    for b in np.unique(bins):
        m = bins == b
        c = res["circ"][m]
        x = res["cross"][m]
        if x.sum() < MIN_PAIRS or (~x).sum() < MIN_PAIRS:
            continue
        cx, cy = mx[m].mean(), my[m].mean()
        _, pi = ptree.query([cx, cy])
        vs = vert[m]
        rows.append({
            "bin": int(b),
            "ratio": float(np.median(c[x]) / np.median(c[~x])),
            "med_cross": float(np.median(c[x])),
            "med_same": float(np.median(c[~x])),
            "n_cross": int(x.sum()), "n_same": int((~x).sum()),
            "lat": float(rlat[vs].mean()), "lon": float(rlon[vs].mean()),
            "near": places[pi][2],
        })

    rows.sort(key=lambda r: -r["ratio"])
    print(f"\n{len(rows)} bins of {BIN_M/1000:.0f} km with >= {MIN_PAIRS} pairs each\n")
    print(f"{'ratio':>7} {'cross':>6} {'same':>6}  {'lat':>8} {'lon':>8}  nearest named place")
    print("-- most severed --")
    for r in rows[:10]:
        print(f"{r['ratio']:>7.3f} {r['n_cross']:>6} {r['n_same']:>6}  "
              f"{r['lat']:>8.4f} {r['lon']:>8.4f}  {r['near']}")
    print("-- least severed --")
    for r in rows[-6:]:
        print(f"{r['ratio']:>7.3f} {r['n_cross']:>6} {r['n_same']:>6}  "
              f"{r['lat']:>8.4f} {r['lon']:>8.4f}  {r['near']}")

    with open("localised.json", "w", encoding="utf-8") as fh:
        json.dump({"bin_m": BIN_M, "bins": rows,
                   "overall_ratio": res["ratio"],
                   "n_cross": res["n_cross"], "n_same": res["n_same"]}, fh, indent=1)
    print(f"\nmedian bin ratio {np.median([r['ratio'] for r in rows]):.4f}; "
          f"{sum(1 for r in rows if r['ratio'] > 1)}/{len(rows)} bins above 1.0")


if __name__ == "__main__":
    main()

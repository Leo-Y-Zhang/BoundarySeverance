"""Positive control: the UN Buffer Zone at Nicosia, a boundary still closed today.

The divide is a line, not a loop, so we close it into a ring by running the
returned line out to the edges of a generous bounding box and back along the
south. Point-in-ring then means 'north of the line', which is the side test we
want. Placebos are parallel displacements of the same line rather than
rotations, since a linear boundary has no meaningful rotation about a centroid.
"""
import sys

import numpy as np

from osm import overpass, haversine
from graph import project

sys.stdout.reconfigure(encoding="utf-8")

LINE_Q = """
[out:json][timeout:300];
rel(13562321);
out geom;
"""

ZONE_Q = """
[out:json][timeout:300];
rel(3263909);
out geom;
"""

ROUTE_BBOX = (35.00, 33.10, 35.40, 33.65)
STUDY_BBOX = (35.10, 33.25, 35.27, 33.50)

DRIVE = r"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street)(_link)?$"


def _lines(data):
    out = []
    for e in data.get("elements", []):
        for m in e.get("members", []) or []:
            g = m.get("geometry")
            if g and len(g) > 1:
                out.append([(p["lat"], p["lon"]) for p in g])
        g = e.get("geometry")
        if g and len(g) > 1:
            out.append([(p["lat"], p["lon"]) for p in g])
    return out


def divide_line(verbose=True):
    """Longest contiguous chain of the disputed-boundary linestring."""
    segs = _lines(overpass(LINE_Q, tag="cyprus_line"))
    if verbose:
        print(f"buffer-zone linestring: {len(segs)} member ways")

    def key(p, prec=5):
        return (round(p[0], prec), round(p[1], prec))

    ends = {}
    for i, s in enumerate(segs):
        ends.setdefault(key(s[0]), []).append((i, "h"))
        ends.setdefault(key(s[-1]), []).append((i, "t"))
    used = [False] * len(segs)
    chains = []
    for start in range(len(segs)):
        if used[start]:
            continue
        used[start] = True
        pts = list(segs[start])
        for d in (0, 1):
            if d:
                pts.reverse()
            while True:
                nxt = None
                for j, w in ends.get(key(pts[-1]), []):
                    if not used[j]:
                        nxt = (j, w)
                        break
                if nxt is None:
                    break
                j, w = nxt
                used[j] = True
                g = list(segs[j])
                if w == "t":
                    g.reverse()
                pts.extend(g[1:])
        chains.append(pts)
    chains.sort(key=len, reverse=True)
    line = chains[0]
    km = sum(haversine(*line[i], *line[i + 1]) for i in range(len(line) - 1)) / 1000
    if verbose:
        print(f"divide: {len(line)} pts, {km:.1f} km, "
              f"lon {min(p[1] for p in line):.3f}..{max(p[1] for p in line):.3f}")
    return line


def close_ring(line, north_lat=35.95, pad_lon=0.60):
    """Close an open west-east line into a ring covering everything north of it.

    The closure runs out past the island's north coast, so within the study
    window 'inside the ring' is exactly 'north of the buffer zone'. Points east
    of the line's eastern terminus are not classifiable and are excluded by the
    study bounding box.
    """
    line = sorted(line, key=lambda p: p[1])  # west to east
    w_lat, w_lon = line[0]
    e_lat, e_lon = line[-1]
    ring = list(line)
    ring.append((e_lat, e_lon + pad_lon))
    ring.append((north_lat, e_lon + pad_lon))
    ring.append((north_lat, w_lon - pad_lon))
    ring.append((w_lat, w_lon - pad_lon))
    ring.append((w_lat, w_lon))
    return ring


LANDMARKS_NORTH = {
    "North Nicosia (Lefkosa)": (35.1900, 33.3600),
    "Kyrenia (Girne)": (35.3400, 33.3200),
    "Gonyeli": (35.2200, 33.3200),
}
LANDMARKS_SOUTH = {
    "South Nicosia centre": (35.1650, 33.3650),
    "Strovolos": (35.1300, 33.3400),
    "Lakatamia": (35.1100, 33.3200),
    "Larnaca": (34.9200, 33.6300),
}


def validate(ring, lat0, lon0):
    from wall import point_in_ring
    ring_xy = [project(np.array([p[0]]), np.array([p[1]]), lat0, lon0) for p in ring]
    ring_xy = [(float(x[0]), float(y[0])) for x, y in ring_xy]
    fails = 0
    print("\n-- expect NORTH of the line --")
    for n, (la, lo) in LANDMARKS_NORTH.items():
        got = point_in_ring(la, lo, ring_xy, lat0, lon0)
        fails += 0 if got else 1
        print(f"  {'ok ' if got else 'FAIL'}  {n:<26} north={got}")
    print("-- expect SOUTH of the line --")
    for n, (la, lo) in LANDMARKS_SOUTH.items():
        got = point_in_ring(la, lo, ring_xy, lat0, lon0)
        fails += 0 if not got else 1
        print(f"  {'ok ' if not got else 'FAIL'}  {n:<26} north={got}")
    print("ALL PASS" if fails == 0 else f"{fails} FAILED")
    return fails == 0


if __name__ == "__main__":
    line = divide_line()
    ring = close_ring(line)
    lat0 = (STUDY_BBOX[0] + STUDY_BBOX[2]) / 2
    lon0 = (STUDY_BBOX[1] + STUDY_BBOX[3]) / 2
    validate(ring, lat0, lon0)

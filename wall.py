# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Assemble the Mauerweg member ways into a closed ring enclosing West Berlin."""
import sys

from osm import haversine, local_xy, overpass

sys.stdout.reconfigure(encoding="utf-8")

Q = """
[out:json][timeout:600];
rel(9030);
out geom;
"""


def _key(pt, prec=6):
    return (round(pt["lat"], prec), round(pt["lon"], prec))


def load_members():
    d = overpass(Q, tag="mauerweg")
    rel = [e for e in d["elements"] if e["type"] == "relation"][0]
    out = []
    for m in rel.get("members", []):
        g = m.get("geometry")
        if not g or len(g) < 2:
            continue
        out.append({"role": m.get("role", ""), "geom": g})
    return out


def chain(members, prec=6):
    """Greedily chain ways into polylines by shared endpoints."""
    ends = {}
    for i, m in enumerate(members):
        a, b = _key(m["geom"][0], prec), _key(m["geom"][-1], prec)
        ends.setdefault(a, []).append((i, "head"))
        ends.setdefault(b, []).append((i, "tail"))

    used = [False] * len(members)
    chains = []
    for start in range(len(members)):
        if used[start]:
            continue
        used[start] = True
        pts = [(p["lat"], p["lon"]) for p in members[start]["geom"]]
        # extend forwards then backwards
        for direction in (0, 1):
            if direction == 1:
                pts.reverse()
            while True:
                tail = (round(pts[-1][0], prec), round(pts[-1][1], prec))
                nxt = None
                for j, which in ends.get(tail, []):
                    if not used[j]:
                        nxt = (j, which)
                        break
                if nxt is None:
                    break
                j, which = nxt
                used[j] = True
                g = [(p["lat"], p["lon"]) for p in members[j]["geom"]]
                if which == "tail":
                    g.reverse()
                pts.extend(g[1:])
        chains.append(pts)
    chains.sort(key=len, reverse=True)
    return chains


def ring_length_km(ring):
    return sum(
        haversine(ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
        for i in range(len(ring) - 1)
    ) / 1000.0


def build_ring(prec=4, drop_alternatives=True, verbose=True):
    """Return the Wall trace as a closed ring of (lat, lon).

    prec=4 (~11 m snap) is required: a minority of member ways do not share
    exact endpoint nodes, and stricter tolerances shatter the route into 20+
    fragments. At prec=4 the main line assembles into a single 158.2 km chain
    that closes to within 13.4 m, against the relation's declared 160 km.
    """
    members = load_members()
    if drop_alternatives:
        members = [m for m in members if m["role"] != "alternative"]
    chains = chain(members, prec)
    big = chains[0]
    gap = haversine(big[0][0], big[0][1], big[-1][0], big[-1][1])
    if verbose:
        print(f"ring: {len(big)} pts, {ring_length_km(big):.1f} km, "
              f"closure gap {gap:.1f} m, {len(chains) - 1} fragments discarded")
    if gap > 1.0:
        big = big + [big[0]]
    return big


def point_in_ring(lat, lon, ring_xy, lat0, lon0):
    """Ray-casting parity test in projected coordinates."""
    x, y = local_xy(lat, lon, lat0, lon0)
    inside = False
    n = len(ring_xy)
    j = n - 1
    for i in range(n):
        xi, yi = ring_xy[i]
        xj, yj = ring_xy[j]
        if (yi > y) != (yj > y):
            xint = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xint:
                inside = not inside
        j = i
    return inside


def ring_area_km2(ring_xy):
    s = 0.0
    n = len(ring_xy)
    for i in range(n):
        x1, y1 = ring_xy[i]
        x2, y2 = ring_xy[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0 / 1e6


if __name__ == "__main__":
    build_ring()

# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Physical-barrier control: water and rail.

The inner Wall was routed along the Spree, the Landwehrkanal and several rail
corridors. Those sever a road network on their own. This module rasterises
water and rail onto a grid so pairs whose straight line crosses one can be
dropped, leaving only severance that water and rail cannot explain.
"""
import sys

import numpy as np

from graph import project
from osm import overpass

sys.stdout.reconfigure(encoding="utf-8")

CELL = 20.0  # metres

WATER_Q = """
[out:json][timeout:900];
(
  way["waterway"~"^(river|canal)$"]({bbox});
  way["natural"="water"]({bbox});
  relation["natural"="water"]({bbox});
);
out geom;
"""

RAIL_Q = """
[out:json][timeout:900];
(
  way["railway"~"^(rail|light_rail)$"]["tunnel"!~"."]({bbox});
);
out geom;
"""


def _polylines(data):
    lines = []
    for e in data.get("elements", []):
        if e.get("geometry"):
            lines.append([(p["lat"], p["lon"]) for p in e["geometry"]])
        for m in e.get("members", []) or []:
            if m.get("geometry"):
                lines.append([(p["lat"], p["lon"]) for p in m["geometry"]])
    return lines


def fetch(kind, bbox):
    q = (WATER_Q if kind == "water" else RAIL_Q).format(
        bbox=f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}")
    d = overpass(q, tag=f"{kind}_berlin")
    lines = _polylines(d)
    print(f"{kind}: {len(lines)} polylines, {sum(len(l) for l in lines)} points")
    return lines


class Grid:
    """Boolean occupancy grid; True where a barrier passes."""

    def __init__(self, lines, lat0, lon0, pad=2000.0):
        pts = [p for line in lines for p in line]
        la = np.array([p[0] for p in pts])
        lo = np.array([p[1] for p in pts])
        x, y = project(la, lo, lat0, lon0)
        self.x0, self.y0 = x.min() - pad, y.min() - pad
        self.x1, self.y1 = x.max() + pad, y.max() + pad
        self.nx = int((self.x1 - self.x0) / CELL) + 1
        self.ny = int((self.y1 - self.y0) / CELL) + 1
        self.g = np.zeros((self.nx, self.ny), dtype=bool)
        self.lat0, self.lon0 = lat0, lon0

        for line in lines:
            if len(line) < 2:
                continue
            la = np.array([p[0] for p in line])
            lo = np.array([p[1] for p in line])
            lx, ly = project(la, lo, lat0, lon0)
            for i in range(len(lx) - 1):
                self._stroke(lx[i], ly[i], lx[i + 1], ly[i + 1])

    def _stroke(self, xa, ya, xb, yb):
        d = max(abs(xb - xa), abs(yb - ya))
        n = int(d / (CELL * 0.5)) + 2
        xs = np.linspace(xa, xb, n)
        ys = np.linspace(ya, yb, n)
        ix = ((xs - self.x0) / CELL).astype(np.int64)
        iy = ((ys - self.y0) / CELL).astype(np.int64)
        ok = (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)
        self.g[ix[ok], iy[ok]] = True

    def crosses(self, xa, ya, xb, yb, skip_ends=60.0):
        """Vectorised: does each straight segment pass through a barrier cell?

        skip_ends trims the first and last stretch so that a road running along
        a quayside does not count as crossing the water it sits beside.
        """
        xa, ya, xb, yb = map(np.asarray, (xa, ya, xb, yb))
        L = np.hypot(xb - xa, yb - ya)
        n = int(max(2, np.ceil(L.max() / (CELL * 0.5))))
        t = np.linspace(0.0, 1.0, n)[None, :]
        frac = np.clip(skip_ends / np.maximum(L, 1.0), 0.0, 0.45)[:, None]
        tt = frac + t * (1.0 - 2.0 * frac)
        xs = xa[:, None] + (xb - xa)[:, None] * tt
        ys = ya[:, None] + (yb - ya)[:, None] * tt
        ix = ((xs - self.x0) / CELL).astype(np.int64)
        iy = ((ys - self.y0) / CELL).astype(np.int64)
        ok = (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)
        hit = np.zeros(xs.shape, dtype=bool)
        hit[ok] = self.g[ix[ok], iy[ok]]
        return hit.any(axis=1)

    def occupancy(self):
        return float(self.g.mean())

# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Recompute every descriptive number the paper quotes, into facts.json.

Nothing in the manuscript is typed by hand; the LaTeX is rendered from this file
plus the experiment result files, so the text cannot drift from the analysis.
"""
import json
import sys

from scipy.sparse.csgraph import connected_components

import barriers as B
import cyprus as CY
import validate_wall as VW
from fetch import CITIES
from graph import load, project
from osm import haversine, local_xy
from segments import city_boundary_points, classify
from wall import build_ring, load_members, point_in_ring, ring_area_km2

sys.stdout.reconfigure(encoding="utf-8")

F = {}

# ---- Wall geometry -----------------------------------------------------
members = load_members()
F["mauerweg_members"] = len(members)
F["mauerweg_alternatives"] = sum(1 for m in members if m["role"] == "alternative")

ring = build_ring(verbose=False)
F["ring_points"] = len(ring)
F["ring_km"] = round(sum(haversine(*ring[i], *ring[i + 1])
                         for i in range(len(ring) - 1)) / 1000, 1)
F["ring_gap_m"] = round(haversine(*ring[0], *ring[-2]), 1)

bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2
ring_xy = [local_xy(la, lo, lat0, lon0) for la, lo in ring]
F["ring_area_km2"] = round(ring_area_km2(ring_xy), 1)
F["west_berlin_area_km2"] = 480
F["area_error_pct"] = round(abs(F["ring_area_km2"] - 480) / 480 * 100, 1)

ok = 0
for la, lo in VW.WEST.values():
    ok += point_in_ring(la, lo, ring_xy, lat0, lon0)
for la, lo in VW.EAST.values():
    ok += not point_in_ring(la, lo, ring_xy, lat0, lon0)
F["landmarks_total"] = len(VW.WEST) + len(VW.EAST)
F["landmarks_passed"] = int(ok)

inner = classify(ring, lat0, lon0, verbose=False)
F["city_boundary_points"] = len(city_boundary_points())


def seg_km(mask):
    return round(sum(haversine(*ring[i], *ring[i + 1])
                     for i in range(len(ring) - 1)
                     if mask[i] and mask[i + 1]) / 1000, 1)


F["inner_km"] = seg_km(inner)
F["outer_km"] = seg_km(~inner)
F["inner_vertices"] = int(inner.sum())

# ---- Road graphs -------------------------------------------------------
for city in ("berlin", "hamburg", "nicosia"):
    lat, lon, g = load(city, verbose=False)
    ncomp, labels = connected_components(g, directed=False)
    F[f"{city}_nodes"] = int(len(lat))
    F[f"{city}_edges"] = int(g.nnz // 2)
    F[f"{city}_components"] = int(ncomp)
    if city == "berlin":
        lat_b, lon_b, g_b = lat, lon, g

# raw (pre-giant-component) counts for Berlin, for the methods section
from fetch import DRIVE
from osm import overpass

rb = CITIES["berlin"]["route_bbox"]
raw = overpass(f"""
    [out:json][timeout:900];
    (
      way["highway"~"{DRIVE}"]["area"!~"yes"]["access"!~"^(no|private)$"]
         ({rb[0]},{rb[1]},{rb[2]},{rb[3]});
    );
    out body;
    >;
    out skel qt;
    """, tag="roads_berlin")
F["berlin_raw_ways"] = sum(1 for e in raw["elements"] if e["type"] == "way")
F["berlin_raw_nodes"] = sum(1 for e in raw["elements"] if e["type"] == "node")
F["berlin_giant_pct"] = round(100 * F["berlin_nodes"] / F["berlin_raw_nodes"], 1)

# ---- Barriers ----------------------------------------------------------
wl = B.fetch("water", rb)
rl = B.fetch("rail", rb)
water = B.Grid(wl, lat0, lon0)
rail = B.Grid(rl, lat0, lon0)
F["water_polylines"] = len(wl)
F["rail_polylines"] = len(rl)
F["water_occupancy_pct"] = round(water.occupancy() * 100, 2)
F["rail_occupancy_pct"] = round(rail.occupancy() * 100, 2)
F["grid_cell_m"] = int(B.CELL)

# ---- How collinear is the Wall with water and rail? --------------------
# Measured directly: take the crossing pairs from one unrestricted run and ask
# what fraction of them also cross water (or rail). This is the number the
# collinearity argument rests on, so it is computed rather than inferred from
# differing sample sizes.
from severance import measure

_r = measure(lat_b, lon_b, g_b, ring, bbox, lat0, lon0, rotation=0.0,
             n_sources=600, seed=0, band_mask=inner)
_nx, _ny = project(lat_b, lon_b, lat0, lon0)
_x = _r["cross"]
_sx, _sy = _nx[_r["src"]][_x], _ny[_r["src"]][_x]
_tx, _ty = _nx[_r["dst"]][_x], _ny[_r["dst"]][_x]
_w = water.crosses(_sx, _sy, _tx, _ty)
_rl = rail.crosses(_sx, _sy, _tx, _ty)
F["collinearity_n_cross"] = int(_x.sum())
F["water_share"] = round(100 * float(_w.mean()), 1)
F["rail_share"] = round(100 * float(_rl.mean()), 1)
F["water_or_rail_share"] = round(100 * float((_w | _rl).mean()), 1)

# same figure for the same-side control group, for contrast
_s = ~_r["cross"]
_w2 = water.crosses(_nx[_r["src"]][_s], _ny[_r["src"]][_s],
                    _nx[_r["dst"]][_s], _ny[_r["dst"]][_s])
F["water_share_sameside"] = round(100 * float(_w2.mean()), 1)

F["n_west_landmarks"] = len(VW.WEST)
F["n_east_landmarks"] = len(VW.EAST)

# ---- Cyprus ------------------------------------------------------------
line = CY.divide_line(verbose=False)
F["cyprus_line_points"] = len(line)
F["cyprus_line_km"] = round(sum(haversine(*line[i], *line[i + 1])
                                for i in range(len(line) - 1)) / 1000, 1)
F["cyprus_landmarks"] = len(CY.LANDMARKS_NORTH) + len(CY.LANDMARKS_SOUTH)

with open("facts.json", "w", encoding="utf-8") as fh:
    json.dump(F, fh, indent=1, sort_keys=True)

for k in sorted(F):
    print(f"  {k:<26} {F[k]}")
print(f"\nwrote facts.json ({len(F)} values)")

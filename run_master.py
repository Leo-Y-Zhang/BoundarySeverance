"""Every Berlin specification at one common sample size, so rows are comparable.

The earlier runs used 150-900 origins depending on the experiment, which makes
the control table an unfair comparison and left the sensitivity sweep
under-powered. This recomputes all of it at a single setting, in one process so
the graph and barrier grids are built once.
"""
import json
import sys
import time

import numpy as np

import barriers as B
from fetch import CITIES
from graph import load
from segments import classify
from severance import measure, cluster_bootstrap_ci
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUT = "results_master.json"
N = 600
ROT_FULL = list(range(15, 360, 15))   # 23 placements for the control table
ROT_SENS = list(range(30, 360, 30))   # 11 placements per sensitivity row

master = {"meta": {"n_sources": N, "n_rot_full": len(ROT_FULL),
                   "n_rot_sens": len(ROT_SENS)}, "controls": {}, "sensitivity": []}


def save():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(master, fh, indent=1)


t0 = time.time()
lat, lon, g = load("berlin", verbose=False)
ring = build_ring(verbose=False)
bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2
inner = classify(ring, lat0, lon0, verbose=False)
rb = CITIES["berlin"]["route_bbox"]
water = B.Grid(B.fetch("water", rb), lat0, lon0)
rail = B.Grid(B.fetch("rail", rb), lat0, lon0)
print(f"setup {time.time() - t0:.0f}s")


def block(name, rotations, kw, mask):
    tr = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                 n_sources=N, seed=0, band_mask=mask, **kw)
    if tr is None:
        print(f"  {name}: no true result")
        return None
    lo, hi = cluster_bootstrap_ci(tr)
    plac = []
    for deg in rotations:
        r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                    n_sources=N, seed=100 + deg, band_mask=mask, **kw)
        if r is not None:
            plac.append(r["ratio"])
    plac = np.array(plac)
    exceed = int((plac >= tr["ratio"]).sum())
    out = {"name": name, "true": tr["ratio"], "ci_lo": lo, "ci_hi": hi,
           "n_cross": tr["n_cross"], "n_same": tr["n_same"],
           "placebo_mean": float(plac.mean()), "placebo_sd": float(plac.std(ddof=1)),
           "exceed": exceed, "n_placebo": int(len(plac)),
           "p_emp": (exceed + 1) / (len(plac) + 1),
           "z": float((tr["ratio"] - plac.mean()) / plac.std(ddof=1))}
    print(f"  {name:<22} S={out['true']:.4f} CI[{lo:.4f},{hi:.4f}] "
          f"null={out['placebo_mean']:.4f}+/-{out['placebo_sd']:.4f} "
          f"{exceed}/{len(plac)} p={out['p_emp']:.4f} z={out['z']:+.2f} "
          f"[{time.time()-t0:.0f}s]")
    return out


print("\n== control specifications (23 placements each) ==")
for name, kw in [("none", {}),
                 ("nowater", {"barriers": [water]}),
                 ("nowater_norail", {"barriers": [water, rail]}),
                 ("wateronly", {"require": [water]})]:
    r = block(name, ROT_FULL, kw, inner)
    if r:
        master["controls"][name] = r
        save()

print("\n== sensitivity (11 placements each) ==")
SETTINGS = [
    ("default",       dict(band=1500, dmin=1000, dmax=6000, exclude=150), 400),
    ("band 1000 m",   dict(band=1000, dmin=1000, dmax=6000, exclude=150), 400),
    ("band 2500 m",   dict(band=2500, dmin=1000, dmax=6000, exclude=150), 400),
    ("trips 0.5-3 km", dict(band=1500, dmin=500, dmax=3000, exclude=150), 400),
    ("trips 2-10 km", dict(band=1500, dmin=2000, dmax=10000, exclude=150), 400),
    ("exclude 300 m", dict(band=1500, dmin=1000, dmax=6000, exclude=300), 400),
    ("split tol 800 m", dict(band=1500, dmin=1000, dmax=6000, exclude=150), 800),
]
for name, kw, tol in SETTINGS:
    mask = inner if tol == 400 else classify(ring, lat0, lon0, verbose=False, tol=tol)
    r = block(name, ROT_SENS, kw, mask)
    if r:
        r["tol"] = tol
        master["sensitivity"].append(r)
        save()

save()
print(f"\ndone in {time.time() - t0:.0f}s")

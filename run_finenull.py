"""A finer permutation null: 71 placements at 5 degrees instead of 23 at 15.

With 23 placements the smallest attainable p-value is 1/24 = 0.042, which every
Berlin specification attained exactly -- the test could show the true placement
was extremal but not how extremal. At 71 placements the floor drops to
1/72 = 0.014. Per-placement ratios are retained this time so figures can show
the actual null rather than its moments.
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

OUT = "results_finenull.json"
N = 600
ROTATIONS = [d for d in range(5, 360, 5)]  # 71 placements

res = {"meta": {"n_sources": N, "n_placements": len(ROTATIONS), "step_deg": 5},
       "controls": {}}


def save():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)


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
print(f"setup {time.time() - t0:.0f}s; {len(ROTATIONS)} placements per spec")

SPECS = [("none", {}),
         ("nowater_norail", {"barriers": [water, rail]}),
         ("nowater", {"barriers": [water]}),
         ("wateronly", {"require": [water]})]

for name, kw in SPECS:
    tr = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                 n_sources=N, seed=0, band_mask=inner, **kw)
    if tr is None:
        print(f"{name}: no true result")
        continue
    lo, hi = cluster_bootstrap_ci(tr)
    plac, degs = [], []
    for deg in ROTATIONS:
        r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                    n_sources=N, seed=1000 + deg, band_mask=inner, **kw)
        if r is not None:
            plac.append(r["ratio"])
            degs.append(deg)
    p = np.array(plac)
    exceed = int((p >= tr["ratio"]).sum())
    res["controls"][name] = {
        "name": name, "true": tr["ratio"], "ci_lo": lo, "ci_hi": hi,
        "n_cross": tr["n_cross"], "n_same": tr["n_same"],
        "placebo_mean": float(p.mean()), "placebo_sd": float(p.std(ddof=1)),
        "placebo_min": float(p.min()), "placebo_max": float(p.max()),
        "exceed": exceed, "n_placebo": int(len(p)),
        "p_emp": (exceed + 1) / (len(p) + 1),
        "z": float((tr["ratio"] - p.mean()) / p.std(ddof=1)),
        "placebos": [float(x) for x in p], "degrees": degs}
    save()
    c = res["controls"][name]
    print(f"  {name:<16} S={c['true']:.4f} CI[{lo:.4f},{hi:.4f}] "
          f"null={c['placebo_mean']:.4f}+/-{c['placebo_sd']:.4f} "
          f"range[{c['placebo_min']:.4f},{c['placebo_max']:.4f}] "
          f"{exceed}/{len(p)} p={c['p_emp']:.4f} z={c['z']:+.2f} "
          f"[{time.time()-t0:.0f}s]")

save()
print(f"\ndone in {time.time() - t0:.0f}s")

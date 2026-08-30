# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Point-estimate stability across sampling parameters, at the main sample size.

Recomputing a full 23-placement null for every specification is expensive. Here
we recompute only the true placement at the main sample size, with cluster
intervals, to show how far the estimate itself moves. The full null-recomputation
at lower sampling lives in results_sensitivity.json and is reported alongside.
"""
import json
import sys
import time

import numpy as np

from fetch import CITIES
from graph import load
from segments import classify
from severance import cluster_bootstrap_ci, measure
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

N = 600
SETTINGS = [
    ("default",        dict(band=1500, dmin=1000, dmax=6000, exclude=150), 400),
    ("band 1000 m",    dict(band=1000, dmin=1000, dmax=6000, exclude=150), 400),
    ("band 2500 m",    dict(band=2500, dmin=1000, dmax=6000, exclude=150), 400),
    ("trips 0.5-3 km", dict(band=1500, dmin=500, dmax=3000, exclude=150), 400),
    ("trips 2-10 km",  dict(band=1500, dmin=2000, dmax=10000, exclude=150), 400),
    ("exclude 300 m",  dict(band=1500, dmin=1000, dmax=6000, exclude=300), 400),
    ("split tol 800 m", dict(band=1500, dmin=1000, dmax=6000, exclude=150), 800),
]

t0 = time.time()
lat, lon, g = load("berlin", verbose=False)
ring = build_ring(verbose=False)
bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2
inner = classify(ring, lat0, lon0, verbose=False)

out = []
for name, kw, tol in SETTINGS:
    mask = inner if tol == 400 else classify(ring, lat0, lon0, verbose=False, tol=tol)
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                n_sources=N, seed=0, band_mask=mask, **kw)
    if r is None:
        continue
    lo, hi = cluster_bootstrap_ci(r)
    out.append({"name": name, "true": r["ratio"], "ci_lo": lo, "ci_hi": hi,
                "n_cross": r["n_cross"], "n_same": r["n_same"], "tol": tol, **kw})
    print(f"  {name:<18} S={r['ratio']:.4f} CI[{lo:.4f},{hi:.4f}] "
          f"n={r['n_cross']}/{r['n_same']} [{time.time()-t0:.0f}s]")

with open("results_sens_true.json", "w", encoding="utf-8") as fh:
    json.dump({"meta": {"n_sources": N}, "settings": out}, fh, indent=1)
v = np.array([o["true"] for o in out])
print(f"\nrange {v.min():.4f} to {v.max():.4f}; done in {time.time()-t0:.0f}s")

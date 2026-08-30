# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Quick single-run check on the true Wall line before committing to the full suite."""
import sys
import time

from fetch import CITIES
from graph import load
from severance import bootstrap_ci, measure
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8")

t0 = time.time()
lat, lon, g = load("berlin")
ring = build_ring()
bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2

res = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
              n_sources=120, seed=0)
if res is None:
    print("no result")
    sys.exit(1)

lo, hi = bootstrap_ci(res)
print("\nBERLIN, true Wall line")
print(f"  pairs: {res['n_cross']} crossing / {res['n_same']} same-side")
print(f"  median circuity crossing : {res['med_cross']:.4f}")
print(f"  median circuity same-side: {res['med_same']:.4f}")
print(f"  severance ratio          : {res['ratio']:.4f}  95% CI [{lo:.4f}, {hi:.4f}]")
print(f"  Mann-Whitney p (greater) : {res['p']:.3e}")
print(f"  elapsed {time.time() - t0:.0f}s")

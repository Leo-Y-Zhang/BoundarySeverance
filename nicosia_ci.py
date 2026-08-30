# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Cluster-bootstrap interval for the Nicosia positive control."""
import json
import sys

import numpy as np

import cyprus as CY
from fetch import CITIES
from graph import load
from severance import bootstrap_ci, cluster_bootstrap_ci, measure

sys.stdout.reconfigure(encoding="utf-8")

lat, lon, g = load("nicosia", verbose=False)
line = CY.divide_line(verbose=False)
ring = CY.close_ring(line)
band = np.array([True] * len(line) + [False] * (len(ring) - len(line)))
bb = CITIES["nicosia"]["study_bbox"]
lat0, lon0 = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2

seeds = {}
for s in (0, 1, 2, 3):
    r = measure(lat, lon, g, ring, bb, lat0, lon0, n_sources=600, seed=s,
                band_mask=band)
    seeds[s] = r["ratio"]
    if s == 0:
        lo, hi = cluster_bootstrap_ci(r)
        nlo, nhi = bootstrap_ci(r)
        out = {"true": r["ratio"], "ci_lo": lo, "ci_hi": hi,
               "naive_lo": nlo, "naive_hi": nhi,
               "n_cross": r["n_cross"], "n_same": r["n_same"],
               "med_cross": r["med_cross"], "med_same": r["med_same"]}
        print(f"true {r['ratio']:.4f}  cluster CI[{lo:.4f},{hi:.4f}]  "
              f"naive CI[{nlo:.4f},{nhi:.4f}]  n={r['n_cross']}/{r['n_same']}")

vals = np.array(list(seeds.values()))
out["seed_mean"] = float(vals.mean())
out["seed_sd"] = float(vals.std(ddof=1))
out["n_seeds"] = len(vals)
print(f"across {len(vals)} seeds: {vals.mean():.4f} +/- {vals.std(ddof=1):.4f}")

with open("nicosia_ci.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)
print("wrote nicosia_ci.json")

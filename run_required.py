# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Hold the confound constant instead of removing it.

Restricting to pairs that ALL cross water, we ask whether crossing the former
Wall costs extra on top of crossing the river. Both groups pay the water
penalty, so any remaining gap is not hydrography.
"""
import json
import sys
import time

import numpy as np

import barriers as B
from fetch import CITIES
from graph import load
from segments import classify
from severance import bootstrap_ci, measure
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUT = "results_required.json"
N_SOURCES = 900
ROTATIONS = list(range(15, 360, 15))

results = {"meta": {"n_sources": N_SOURCES}, "runs": []}


def save():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)


def record(label, res, extra):
    if res is None:
        print(f"  {label:<26} insufficient pairs")
        results["runs"].append({"label": label, "ok": False, **extra})
        save()
        return
    lo, hi = bootstrap_ci(res)
    results["runs"].append({
        "label": label, "ok": True, "n_cross": res["n_cross"], "n_same": res["n_same"],
        "med_cross": res["med_cross"], "med_same": res["med_same"],
        "ratio": res["ratio"], "ci_lo": lo, "ci_hi": hi, "p_mw": res["p"], **extra})
    save()
    print(f"  {label:<26} ratio={res['ratio']:.4f} CI[{lo:.4f},{hi:.4f}] "
          f"n={res['n_cross']}/{res['n_same']}")


t0 = time.time()
lat, lon, g = load("berlin")
ring = build_ring()
bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2
inner = classify(ring, lat0, lon0, verbose=False)

rb = CITIES["berlin"]["route_bbox"]
water = B.Grid(B.fetch("water", rb), lat0, lon0)

print("\n== all pairs cross water; does crossing the Wall cost extra? ==")
r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
            n_sources=N_SOURCES, seed=0, band_mask=inner, require=[water])
record("water_only/true", r, {"kind": "true", "rotation": 0})
for deg in ROTATIONS:
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                n_sources=N_SOURCES, seed=100 + deg, band_mask=inner, require=[water])
    record(f"water_only/rot{deg:03d}", r, {"kind": "placebo", "rotation": deg})

rs = [r for r in results["runs"] if r.get("ok")]
true = [r for r in rs if r["kind"] == "true"]
plac = np.array([r["ratio"] for r in rs if r["kind"] == "placebo"])
if true and len(plac) >= 5:
    t = true[0]["ratio"]
    p = (int((plac >= t).sum()) + 1) / (len(plac) + 1)
    z = (t - plac.mean()) / plac.std(ddof=1)
    print(f"\n  true {t:.4f}  placebo {plac.mean():.4f}+/-{plac.std(ddof=1):.4f}  "
          f"exceed {int((plac >= t).sum())}/{len(plac)}  p={p:.4f}  z={z:+.2f}")
    results["meta"]["summary"] = {
        "true": t, "placebo_mean": float(plac.mean()),
        "placebo_sd": float(plac.std(ddof=1)), "exceed": int((plac >= t).sum()),
        "n_placebo": int(len(plac)), "p_emp": p, "z": float(z)}
save()
print(f"\ndone in {time.time() - t0:.0f}s")

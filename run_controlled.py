# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Re-run Berlin inner Wall with physical-barrier controls, true vs placebos."""
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

OUT = "results_controlled.json"
N_SOURCES = 400
ROTATIONS = list(range(15, 360, 15))

results = {"meta": {"n_sources": N_SOURCES}, "runs": []}


def save():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)


def record(label, res, extra):
    if res is None:
        print(f"  {label}: insufficient pairs")
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
rail = B.Grid(B.fetch("rail", rb), lat0, lon0)
print(f"water grid {water.g.shape} occupancy {water.occupancy() * 100:.2f}%")
print(f"rail  grid {rail.g.shape} occupancy {rail.occupancy() * 100:.2f}%")

SETS = {
    "nowater": [water],
    "nowater_norail": [water, rail],
}

for setname, bars in SETS.items():
    print(f"\n== control: {setname} ==")
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                n_sources=N_SOURCES, seed=0, band_mask=inner, barriers=bars)
    record(f"{setname}/true", r, {"control": setname, "kind": "true", "rotation": 0})
    for deg in ROTATIONS:
        r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                    n_sources=N_SOURCES, seed=100 + deg, band_mask=inner, barriers=bars)
        record(f"{setname}/rot{deg:03d}", r,
               {"control": setname, "kind": "placebo", "rotation": deg})
    print(f"  [{time.time() - t0:.0f}s]")

print("\n== summary ==")
for setname in SETS:
    rs = [r for r in results["runs"] if r.get("ok") and r["control"] == setname]
    true = [r for r in rs if r["kind"] == "true"]
    plac = np.array([r["ratio"] for r in rs if r["kind"] == "placebo"])
    if not true or len(plac) < 5:
        continue
    t = true[0]["ratio"]
    p = (int((plac >= t).sum()) + 1) / (len(plac) + 1)
    z = (t - plac.mean()) / plac.std(ddof=1)
    print(f"  {setname:<16} true {t:.4f}  placebo {plac.mean():.4f}+/-{plac.std(ddof=1):.4f}  "
          f"exceed {int((plac >= t).sum())}/{len(plac)}  p={p:.4f}  z={z:+.2f}")
    results["meta"][setname] = {"true": t, "placebo_mean": float(plac.mean()),
                                "placebo_sd": float(plac.std(ddof=1)),
                                "exceed": int((plac >= t).sum()),
                                "n_placebo": int(len(plac)), "p_emp": p, "z": float(z)}
save()
print(f"\ndone in {time.time() - t0:.0f}s")

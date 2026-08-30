"""Full experiment. Writes results.json incrementally so progress is inspectable."""
import json
import sys
import time

import numpy as np

from fetch import CITIES
from graph import load, project
from segments import classify
from severance import measure, bootstrap_ci
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUT = "results.json"
N_SOURCES = 250
ROTATIONS = list(range(15, 360, 15))  # 23 placebo placements

results = {"meta": {"n_sources": N_SOURCES, "rotations": ROTATIONS}, "runs": []}


def save():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)


def record(label, res, extra=None):
    if res is None:
        print(f"  {label}: insufficient pairs")
        results["runs"].append({"label": label, "ok": False, **(extra or {})})
        save()
        return
    lo, hi = bootstrap_ci(res)
    row = {
        "label": label, "ok": True,
        "n_cross": res["n_cross"], "n_same": res["n_same"],
        "med_cross": res["med_cross"], "med_same": res["med_same"],
        "mean_cross": res["mean_cross"], "mean_same": res["mean_same"],
        "ratio": res["ratio"], "ci_lo": lo, "ci_hi": hi, "p_mw": res["p"],
        **(extra or {}),
    }
    results["runs"].append(row)
    save()
    print(f"  {label:<28} ratio={res['ratio']:.4f} "
          f"CI[{lo:.4f},{hi:.4f}] n={res['n_cross']}/{res['n_same']} p={res['p']:.2e}")


t0 = time.time()
print("loading berlin")
lat, lon, g = load("berlin")
ring = build_ring()
bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2
inner = classify(ring, lat0, lon0)

MASKS = {"inner": inner, "outer": ~inner, "full": None}

print("\n== Berlin, true Wall placement ==")
for name, mask in MASKS.items():
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                n_sources=N_SOURCES, seed=0, band_mask=mask)
    record(f"berlin/{name}/true", r, {"city": "berlin", "segment": name,
                                      "kind": "true", "rotation": 0})

print("\n== Berlin, rotation placebos (inner segment) ==")
for deg in ROTATIONS:
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                n_sources=N_SOURCES, seed=100 + deg, band_mask=inner)
    record(f"berlin/inner/rot{deg:03d}", r, {"city": "berlin", "segment": "inner",
                                             "kind": "placebo", "rotation": deg})
    print(f"    [{time.time() - t0:.0f}s]")

print("\n== Hamburg placebo (never partitioned) ==")
hlat, hlon, hg = load("hamburg")
hb = CITIES["hamburg"]["study_bbox"]
hlat0 = (hb[0] + hb[2]) / 2
hlon0 = (hb[1] + hb[3]) / 2

rlat = np.array([p[0] for p in ring])
rlon = np.array([p[1] for p in ring])
rx, ry = project(rlat, rlon, hlat0, hlon0)
shift = (-float(rx.mean()), -float(ry.mean()))

for deg in [0] + ROTATIONS:
    r = measure(hlat, hlon, hg, ring, hb, hlat0, hlon0, rotation=float(deg),
                translate=shift, n_sources=N_SOURCES, seed=200 + deg,
                band_mask=inner)
    record(f"hamburg/inner/rot{deg:03d}", r, {"city": "hamburg", "segment": "inner",
                                              "kind": "placebo", "rotation": deg})

print(f"\ndone in {time.time() - t0:.0f}s")
save()

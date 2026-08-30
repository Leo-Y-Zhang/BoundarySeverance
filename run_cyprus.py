"""Positive control at Nicosia: does the method detect a boundary that is still closed?

Placebos are perpendicular displacements of the same divide line, from 2 to 12 km
either side. A linear boundary has no meaningful rotation, so displacement is the
natural way to preserve shape while changing placement.
"""
import json
import sys
import time

import numpy as np
from scipy.sparse.csgraph import connected_components

import cyprus as CY
from fetch import CITIES
from graph import load
from severance import measure, bootstrap_ci

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUT = "results_cyprus.json"
N_SOURCES = 400
SHIFTS_KM = [s for k in range(2, 13) for s in (k, -k)]  # 22 placebos

results = {"meta": {"n_sources": N_SOURCES, "shifts_km": SHIFTS_KM}, "runs": []}


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
lat, lon, g = load("nicosia")

# Is the drivable network actually connected across the buffer zone?
ncomp, labels = connected_components(g, directed=False)
sizes = np.bincount(labels)
print(f"components in the Nicosia extract: {ncomp}; largest {sizes.max()} nodes")

line = CY.divide_line(verbose=True)
ring = CY.close_ring(line)
band = np.array([True] * len(line) + [False] * (len(ring) - len(line)))

bbox = CITIES["nicosia"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2
if not CY.validate(ring, lat0, lon0):
    sys.exit("geometry validation failed")

print("\n== Nicosia: true buffer zone ==")
r = measure(lat, lon, g, ring, bbox, lat0, lon0, n_sources=N_SOURCES, seed=0,
            band_mask=band)
record("nicosia/true", r, {"kind": "true", "shift_km": 0})

print("\n== Nicosia: displaced placebos ==")
for km in SHIFTS_KM:
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, n_sources=N_SOURCES,
                seed=300 + abs(km) * (1 if km > 0 else 7),
                translate=(0.0, km * 1000.0), band_mask=band)
    record(f"nicosia/shift{km:+03d}km", r, {"kind": "placebo", "shift_km": km})

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
        "n_placebo": int(len(plac)), "p_emp": p, "z": float(z),
        "n_components": int(ncomp), "largest_component": int(sizes.max())}
save()
print(f"\ndone in {time.time() - t0:.0f}s")

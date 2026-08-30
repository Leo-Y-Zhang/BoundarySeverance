# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Definitive run: large source sample, cluster bootstrap, seed-stability check."""
import json
import sys
import time

import numpy as np

import cyprus as CY
from fetch import CITIES
from graph import load
from segments import classify
from severance import bootstrap_ci, cluster_bootstrap_ci, measure
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUT = "results_final.json"
N_SOURCES = 2000
ROTATIONS = list(range(15, 360, 15))
STABILITY_SEEDS = [1, 2, 3]

res_all = {"meta": {"n_sources": N_SOURCES}, "berlin": [], "nicosia": []}


def save():
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res_all, fh, indent=1)


def row(res, **extra):
    lo, hi = cluster_bootstrap_ci(res)
    plo, phi = bootstrap_ci(res)
    return {"ratio": res["ratio"], "n_cross": res["n_cross"], "n_same": res["n_same"],
            "med_cross": res["med_cross"], "med_same": res["med_same"],
            "ci_lo": lo, "ci_hi": hi, "naive_lo": plo, "naive_hi": phi,
            "n_sources_used": int(len(np.unique(res["src"]))), **extra}


t0 = time.time()

# ---------------- Berlin ----------------
lat, lon, g = load("berlin", verbose=False)
ring = build_ring(verbose=False)
bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2
inner = classify(ring, lat0, lon0, verbose=False)

print("== Berlin inner Wall, definitive ==")
r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
            n_sources=N_SOURCES, seed=0, band_mask=inner)
d = row(r, kind="true", rotation=0, seed=0)
res_all["berlin"].append(d); save()
print(f"  true            ratio={d['ratio']:.4f}  cluster CI[{d['ci_lo']:.4f},{d['ci_hi']:.4f}]"
      f"  naive CI[{d['naive_lo']:.4f},{d['naive_hi']:.4f}]  n={d['n_cross']}/{d['n_same']}")

for s in STABILITY_SEEDS:
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                n_sources=N_SOURCES, seed=s, band_mask=inner)
    d = row(r, kind="true_seed", rotation=0, seed=s)
    res_all["berlin"].append(d); save()
    print(f"  true seed={s}     ratio={d['ratio']:.4f}")

for deg in ROTATIONS:
    r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                n_sources=N_SOURCES, seed=100 + deg, band_mask=inner)
    if r is None:
        continue
    d = row(r, kind="placebo", rotation=deg, seed=100 + deg)
    res_all["berlin"].append(d); save()
    print(f"  rot{deg:03d}          ratio={d['ratio']:.4f}  [{time.time()-t0:.0f}s]")

# ---------------- Nicosia ----------------
print("\n== Nicosia positive control, definitive ==")
nlat, nlon, ng = load("nicosia", verbose=False)
line = CY.divide_line(verbose=False)
cring = CY.close_ring(line)
band = np.array([True] * len(line) + [False] * (len(cring) - len(line)))
nb = CITIES["nicosia"]["study_bbox"]
nlat0 = (nb[0] + nb[2]) / 2
nlon0 = (nb[1] + nb[3]) / 2

r = measure(nlat, nlon, ng, cring, nb, nlat0, nlon0, n_sources=N_SOURCES, seed=0,
            band_mask=band)
d = row(r, kind="true", shift_km=0, seed=0)
res_all["nicosia"].append(d); save()
print(f"  true            ratio={d['ratio']:.4f}  cluster CI[{d['ci_lo']:.4f},{d['ci_hi']:.4f}]"
      f"  n={d['n_cross']}/{d['n_same']}")
for s in STABILITY_SEEDS:
    r = measure(nlat, nlon, ng, cring, nb, nlat0, nlon0, n_sources=N_SOURCES,
                seed=s, band_mask=band)
    d = row(r, kind="true_seed", shift_km=0, seed=s)
    res_all["nicosia"].append(d); save()
    print(f"  true seed={s}     ratio={d['ratio']:.4f}")

# ---------------- summary ----------------
def summarise(key, label):
    rs = res_all[key]
    true = [x for x in rs if x["kind"] == "true"][0]
    seeds = [x["ratio"] for x in rs if x["kind"] in ("true", "true_seed")]
    plac = np.array([x["ratio"] for x in rs if x["kind"] == "placebo"])
    out = {"true": true["ratio"], "ci_lo": true["ci_lo"], "ci_hi": true["ci_hi"],
           "naive_lo": true["naive_lo"], "naive_hi": true["naive_hi"],
           "n_cross": true["n_cross"], "n_same": true["n_same"],
           "seed_mean": float(np.mean(seeds)), "seed_sd": float(np.std(seeds, ddof=1)),
           "n_seeds": len(seeds)}
    if len(plac) >= 5:
        exceed = int((plac >= true["ratio"]).sum())
        out.update({"placebo_mean": float(plac.mean()),
                    "placebo_sd": float(plac.std(ddof=1)),
                    "exceed": exceed, "n_placebo": int(len(plac)),
                    "p_emp": (exceed + 1) / (len(plac) + 1),
                    "z": float((true["ratio"] - plac.mean()) / plac.std(ddof=1))})
    res_all["meta"][key] = out
    print(f"\n{label}")
    print(f"  true {out['true']:.4f}  cluster CI [{out['ci_lo']:.4f}, {out['ci_hi']:.4f}]"
          f"  (naive CI [{out['naive_lo']:.4f}, {out['naive_hi']:.4f}])")
    print(f"  across {out['n_seeds']} seeds: {out['seed_mean']:.4f} +/- {out['seed_sd']:.4f}")
    if "z" in out:
        print(f"  placebo {out['placebo_mean']:.4f} +/- {out['placebo_sd']:.4f}; "
              f"exceed {out['exceed']}/{out['n_placebo']}; p={out['p_emp']:.4f}; z={out['z']:+.2f}")


summarise("berlin", "BERLIN inner Wall")
summarise("nicosia", "NICOSIA buffer zone")
save()
print(f"\ndone in {time.time() - t0:.0f}s")

"""Is the Berlin result an artefact of the sampling parameters?

Every design choice here is arbitrary within reason: how close a pair's midpoint
must sit to the boundary, how long a trip may be, how far from the line a node
must be to have an unambiguous side, and the tolerance separating the inner Wall
from the outer ring. Each is varied one at a time and the full 23-placement null
is recomputed, so the reported z is directly comparable across settings.
"""
import json
import sys
import time

import numpy as np

from fetch import CITIES
from graph import load
from segments import classify
from severance import measure
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUT = "results_sensitivity.json"
N_SOURCES = 150
ROTATIONS = list(range(15, 360, 15))

SETTINGS = [
    ("default",        dict(band=1500, dmin=1000, dmax=6000, exclude=150), 400),
    ("band=1000",      dict(band=1000, dmin=1000, dmax=6000, exclude=150), 400),
    ("band=2500",      dict(band=2500, dmin=1000, dmax=6000, exclude=150), 400),
    ("trips 0.5-3km",  dict(band=1500, dmin=500, dmax=3000, exclude=150), 400),
    ("trips 2-10km",   dict(band=1500, dmin=2000, dmax=10000, exclude=150), 400),
    ("exclude=300",    dict(band=1500, dmin=1000, dmax=6000, exclude=300), 400),
    ("split tol=800",  dict(band=1500, dmin=1000, dmax=6000, exclude=150), 800),
]

t0 = time.time()
lat, lon, g = load("berlin")
ring = build_ring(verbose=False)
bbox = CITIES["berlin"]["study_bbox"]
lat0 = (bbox[0] + bbox[2]) / 2
lon0 = (bbox[1] + bbox[3]) / 2

out = {"meta": {"n_sources": N_SOURCES}, "settings": []}
print(f"{'setting':<16} {'true':>8} {'null mean':>10} {'null sd':>8} {'exceed':>8} "
      f"{'p':>7} {'z':>7}")

for name, kw, tol in SETTINGS:
    inner = classify(ring, lat0, lon0, verbose=False, tol=tol)
    tr = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                 n_sources=N_SOURCES, seed=0, band_mask=inner, **kw)
    if tr is None:
        print(f"{name:<16}  no result")
        continue
    plac = []
    for deg in ROTATIONS:
        r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                    n_sources=N_SOURCES, seed=100 + deg, band_mask=inner, **kw)
        if r is not None:
            plac.append(r["ratio"])
    plac = np.array(plac)
    exceed = int((plac >= tr["ratio"]).sum())
    p = (exceed + 1) / (len(plac) + 1)
    z = (tr["ratio"] - plac.mean()) / plac.std(ddof=1)
    print(f"{name:<16} {tr['ratio']:>8.4f} {plac.mean():>10.4f} {plac.std(ddof=1):>8.4f} "
          f"{exceed:>4}/{len(plac):<3} {p:>7.4f} {z:>+7.2f}")
    out["settings"].append({
        "name": name, "tol": tol, **kw,
        "true": tr["ratio"], "n_cross": tr["n_cross"], "n_same": tr["n_same"],
        "null_mean": float(plac.mean()), "null_sd": float(plac.std(ddof=1)),
        "exceed": exceed, "n_placebo": int(len(plac)), "p_emp": p, "z": float(z)})
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

print(f"\ndone in {time.time() - t0:.0f}s")

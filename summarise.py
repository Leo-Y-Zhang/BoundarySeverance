# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Summarise the true-vs-placebo comparison from results.json."""
import json
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

R = json.load(open("results.json", encoding="utf-8"))
runs = [r for r in R["runs"] if r.get("ok")]


def get(city, seg, kind):
    return [r for r in runs if r["city"] == city and r["segment"] == seg and r["kind"] == kind]


for city in ("berlin", "hamburg"):
    for seg in ("inner", "outer", "full"):
        true = get(city, seg, "true")
        plac = get(city, seg, "placebo")
        if not true and not plac:
            continue
        print(f"\n=== {city} / {seg} ===")
        if true:
            t = true[0]
            print(f"  true      ratio {t['ratio']:.4f}  95% CI [{t['ci_lo']:.4f}, {t['ci_hi']:.4f}]"
                  f"  n={t['n_cross']}/{t['n_same']}")
        if plac:
            v = np.array([r["ratio"] for r in plac])
            print(f"  placebo   n={len(v)}  mean {v.mean():.4f}  sd {v.std(ddof=1):.4f}  "
                  f"min {v.min():.4f}  max {v.max():.4f}")
            if true:
                t = true[0]["ratio"]
                exceed = int((v >= t).sum())
                p = (exceed + 1) / (len(v) + 1)
                z = (t - v.mean()) / v.std(ddof=1)
                print(f"  placebos >= true: {exceed}/{len(v)}   empirical p = {p:.4f}   z = {z:+.2f}")


# Hamburg has no 'true' run (the ring is transplanted), rot000 is just placement 0
h = [r for r in runs if r["city"] == "hamburg"]
if h:
    v = np.array([r["ratio"] for r in h])
    print(f"\n=== hamburg, all {len(v)} placements of the transplanted ring ===")
    print(f"  mean {v.mean():.4f}  sd {v.std(ddof=1):.4f}  min {v.min():.4f}  max {v.max():.4f}")
    print(f"  placements above 1.05: {(v > 1.05).sum()};  above 1.20: {(v > 1.20).sum()}")

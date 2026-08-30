"""Render paper_template.tex into paper.tex with every number injected, then build.

Fails loudly if any placeholder is left unfilled, so the manuscript cannot ship
with a stale or missing value.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np

import severance as SV

sys.stdout.reconfigure(encoding="utf-8")

# Set TECTONIC to point at a tectonic binary, or leave it on PATH.
TECTONIC = os.environ.get("TECTONIC") or shutil.which("tectonic")
DATE = os.environ.get("PAPER_DATE", "30 August 2026")


def load(p):
    return json.load(open(p, encoding="utf-8"))


facts = load("facts.json")
master = load("results_master.json")
fin = load("results_final.json")
ncy = load("nicosia_ci.json")
cyp = load("results_cyprus.json")
base = load("results.json")
loc = load("localised.json")

V = dict(facts)
V["date"] = DATE
V["n_west"] = facts["n_west_landmarks"]
V["n_east"] = facts["n_east_landmarks"]

# ---- sampling parameters, read from the code that ran ------------------
V["dmin_km"] = f"{SV.DMIN / 1000:g}"
V["dmax_km"] = f"{SV.DMAX / 1000:g}"
V["band_m"] = int(SV.BAND)
V["exclude_m"] = int(SV.EXCLUDE)
V["max_targets"] = int(SV.MAX_TARGETS)

# ---- Berlin headline: master 'none' spec -------------------------------
C = master["controls"]
n = C["none"]
V["be_true"] = f"{n['true']:.4f}"
V["be_pct"] = f"{(n['true'] - 1) * 100:.1f}"
V["be_exceed"] = n["exceed"]
V["be_nplacebo"] = n["n_placebo"]
V["be_p"] = f"{n['p_emp']:.3f}"
V["be_z"] = f"{n['z']:+.2f}"
V["be_placebo_mean"] = f"{n['placebo_mean']:.4f}"

for key, tag in [("none", "none"), ("nowater", "nw"),
                 ("nowater_norail", "nwr"), ("wateronly", "wo")]:
    c = C[key]
    V[f"c_{tag}_true"] = f"{c['true']:.4f}"
    V[f"c_{tag}_mean"] = f"{c['placebo_mean']:.4f}"
    V[f"c_{tag}_sd"] = f"{c['placebo_sd']:.4f}"
    V[f"c_{tag}_exceed"] = f"{c['exceed']}/{c['n_placebo']}"
    V[f"c_{tag}_lo"] = f"{c['ci_lo']:.4f}"
    V[f"c_{tag}_hi"] = f"{c['ci_hi']:.4f}"
    V[f"c_{tag}_pct"] = f"{(c['true'] - 1) * 100:.1f}"
V["z_none"] = f"{C['none']['z']:+.2f}"
V["z_nowater"] = f"{C['nowater']['z']:+.2f}"
V["z_norail"] = f"{C['nowater_norail']['z']:+.2f}"
V["z_wateronly"] = f"{C['wateronly']['z']:+.2f}"

# ---- Berlin stability at 2000 origins ----------------------------------
btrue = [r for r in fin["berlin"] if r["kind"] == "true"][0]
bseeds = [r["ratio"] for r in fin["berlin"] if r["kind"] in ("true", "true_seed")]
V["be_ci_lo"] = f"{btrue['ci_lo']:.4f}"
V["be_ci_hi"] = f"{btrue['ci_hi']:.4f}"
V["be_naive_lo"] = f"{btrue['naive_lo']:.4f}"
V["be_naive_hi"] = f"{btrue['naive_hi']:.4f}"
V["be_big_true"] = f"{btrue['ratio']:.4f}"
V["be_big_n"] = btrue["n_cross"]
V["be_seed_mean"] = f"{np.mean(bseeds):.4f}"
V["be_seed_sd"] = f"{np.std(bseeds, ddof=1):.4f}"
V["be_nseeds"] = len(bseeds)
V["be_ci_width_ratio"] = f"{(btrue['ci_hi'] - btrue['ci_lo']) / (btrue['naive_hi'] - btrue['naive_lo']):.1f}"

# ---- Cyprus ------------------------------------------------------------
cs = cyp["meta"]["summary"]
V["cy_true"] = f"{ncy['true']:.4f}"
V["cy_pct"] = f"{(ncy['true'] - 1) * 100:.1f}"
V["cy_ci_lo"] = f"{ncy['ci_lo']:.4f}"
V["cy_ci_hi"] = f"{ncy['ci_hi']:.4f}"
V["cy_ncross"] = ncy["n_cross"]
V["cy_nsame"] = ncy["n_same"]
V["cy_seed_mean"] = f"{ncy['seed_mean']:.4f}"
V["cy_seed_sd"] = f"{ncy['seed_sd']:.4f}"
# Score the value we actually report against the placebo placements, rather
# than reusing a z computed for a different run's point estimate.
cy_plac = np.array([r["ratio"] for r in cyp["runs"]
                    if r.get("ok") and r["kind"] == "placebo"])
cy_exceed = int((cy_plac >= ncy["true"]).sum())
V["cy_placebo_mean"] = f"{cy_plac.mean():.4f}"
V["cy_placebo_sd"] = f"{cy_plac.std(ddof=1):.4f}"
V["cy_exceed"] = cy_exceed
V["cy_nplacebo"] = len(cy_plac)
V["cy_p"] = f"{(cy_exceed + 1) / (len(cy_plac) + 1):.3f}"
V["cy_z"] = f"{(ncy['true'] - cy_plac.mean()) / cy_plac.std(ddof=1):+.2f}"

# ---- sensitivity: point estimates at the main sample size --------------
st = load("results_sens_true.json")
rows = []
for s in st["settings"]:
    rows.append(f"{s['name']} & {s['true']:.4f} & "
                f"$[{s['ci_lo']:.4f},\\ {s['ci_hi']:.4f}]$ & {s['n_cross']} \\\\")
V["sens_rows"] = "\n".join(rows)
V["sens_true_n"] = st["meta"]["n_sources"]
sv = np.array([s["true"] for s in st["settings"]])

# full-null sweep at lower sampling, reported alongside
sens_null = load("results_sensitivity.json")
S = sens_null["settings"]
V["sens_null_n"] = sens_null["meta"]["n_sources"]
sz = np.array([s["z"] for s in S])
sp = np.array([s["p_emp"] for s in S])
V["sens_min"] = f"{sv.min():.4f}"
V["sens_max"] = f"{sv.max():.4f}"
V["sens_zmin"] = f"{sz.min():+.2f}"
V["sens_zmax"] = f"{sz.max():+.2f}"
V["sens_pmin"] = f"{sp.min():.3f}"
V["sens_pmax"] = f"{sp.max():.3f}"
V["sens_nsig"] = int((sp < 0.05).sum())
V["sens_n"] = len(S)

# ---- localisation ------------------------------------------------------
bins = sorted(loc["bins"], key=lambda b: -b["ratio"])
V["loc_nbins"] = len(bins)
V["loc_above"] = sum(1 for b in bins if b["ratio"] > 1)
V["loc_median"] = f"{np.median([b['ratio'] for b in bins]):.4f}"
for i in range(3):
    V[f"loc_top{i+1}"] = f"{bins[i]['ratio']:.3f}"
    V[f"loc_top{i+1}_name"] = bins[i]["near"]
for i in range(2):
    V[f"loc_bot{i+1}"] = f"{bins[-(i+1)]['ratio']:.3f}"
    V[f"loc_bot{i+1}_name"] = bins[-(i+1)]["near"]

# ---- Hamburg transplant ------------------------------------------------
ham = [r["ratio"] for r in base["runs"] if r.get("ok") and r.get("city") == "hamburg"]
V["ham_n"] = len(ham)
V["ham_min"] = f"{min(ham):.4f}"
V["ham_max"] = f"{max(ham):.4f}"
V["ham_above"] = sum(1 for h in ham if h > 1.05)

# ---- derived comparisons ----------------------------------------------
V["be_nplacebo_plus"] = n["n_placebo"] + 1
V["severity_ratio"] = f"{(ncy['true'] - 1) / (n['true'] - 1):.0f}"
V["sens_min_ci_lo"] = f"{min(s['ci_lo'] for s in st['settings']):.4f}"

# ---- render ------------------------------------------------------------
tpl = open("paper_template.tex", encoding="utf-8").read()


def sub(m):
    k = m.group(1)
    if k not in V:
        raise KeyError(f"template needs '{k}' but it was not computed")
    return str(V[k])


tex = re.sub(r"<<(\w+)>>", sub, tpl)
leftover = re.findall(r"<<[^>]*>>", tex)
if leftover:
    sys.exit(f"unfilled placeholders: {leftover}")

open("paper.tex", "w", encoding="utf-8").write(tex)
print(f"wrote paper.tex ({len(tex)} chars, {len(V)} values injected)")

if TECTONIC and os.path.exists(TECTONIC):
    r = subprocess.run([TECTONIC, "paper.tex", "--outdir", "."],
                       capture_output=True, text=True, timeout=900)
    tail = (r.stderr or r.stdout).strip().splitlines()[-12:]
    print("\n".join(tail))
    if r.returncode != 0:
        sys.exit(f"tectonic failed ({r.returncode})")
    print(f"\nPDF: {os.path.abspath('paper.pdf')} "
          f"({os.path.getsize('paper.pdf')} bytes)")
else:
    print("tectonic not found; set TECTONIC or put it on PATH. "
          "paper.tex was written and is ready to build.")

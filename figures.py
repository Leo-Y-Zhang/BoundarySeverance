"""Generate every figure in the paper from the result JSONs. No hand-typed values."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from barriers import fetch as fetch_barrier
from fetch import CITIES
from segments import classify
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8")

plt.rcParams.update({
    "font.size": 9, "figure.dpi": 160, "savefig.dpi": 160,
    "axes.spines.top": False, "axes.spines.right": False,
})

INK = "#1a1a1a"
ACCENT = "#b3202c"
MUTED = "#8a8f98"
WATER = "#7fa8c9"


def load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def fig_map():
    ring = build_ring(verbose=False)
    bbox = CITIES["berlin"]["study_bbox"]
    lat0 = (bbox[0] + bbox[2]) / 2
    lon0 = (bbox[1] + bbox[3]) / 2
    inner = classify(ring, lat0, lon0, verbose=False)

    fig, ax = plt.subplots(figsize=(6.4, 5.6))

    for line in fetch_barrier("water", CITIES["berlin"]["route_bbox"]):
        if len(line) > 1:
            ax.plot([p[1] for p in line], [p[0] for p in line],
                    color=WATER, lw=0.45, alpha=0.75, zorder=1)

    rlat = np.array([p[0] for p in ring])
    rlon = np.array([p[1] for p in ring])
    seg_o = np.where(inner, np.nan, 1.0)
    seg_i = np.where(inner, 1.0, np.nan)
    ax.plot(rlon * seg_o, rlat * seg_o, color=MUTED, lw=1.5, zorder=3,
            label="outer ring (West Berlin / Brandenburg)")
    ax.plot(rlon * seg_i, rlat * seg_i, color=ACCENT, lw=2.0, zorder=4,
            label="inner Wall (East / West Berlin)")

    loc = load("localised.json")
    if loc:
        b = loc["bins"]
        r = np.array([x["ratio"] for x in b])
        sc = ax.scatter([x["lon"] for x in b], [x["lat"] for x in b],
                        c=r, cmap="RdYlBu_r", vmin=0.95, vmax=1.05,
                        s=26, edgecolor="white", linewidth=0.4, zorder=5)
        cb = fig.colorbar(sc, ax=ax, shrink=0.62, pad=0.02)
        cb.set_label("local severance ratio", fontsize=8)
        cb.ax.tick_params(labelsize=7)

    ax.add_patch(plt.Rectangle((bbox[1], bbox[0]), bbox[3] - bbox[1], bbox[2] - bbox[0],
                               fill=False, ec=INK, ls=(0, (4, 3)), lw=0.8, zorder=2))
    ax.set_aspect(1 / np.cos(np.radians(lat0)))
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.set_title("The Berlin Wall trace, its two political halves, and where\n"
                 "residual severance sits (dashed box = sampling window)", fontsize=9)
    ax.legend(fontsize=7, loc="lower left", frameon=False)
    fig.tight_layout()
    fig.savefig("fig1_map.png")
    print("wrote fig1_map.png")


def _panel(ax, c, title):
    """Null shown as mean with +/-1 and +/-2 sd bands (the recorded moments),
    true placement as a line. No per-placement values are simulated."""
    mu, sd = c["placebo_mean"], c["placebo_sd"]
    ax.axvline(1.0, color=MUTED, lw=0.8, ls=(0, (3, 3)), zorder=1)
    ax.axvspan(mu - 2 * sd, mu + 2 * sd, color=MUTED, alpha=0.18, zorder=2,
               label=r"null $\pm2$ sd")
    ax.axvspan(mu - sd, mu + sd, color=MUTED, alpha=0.34, zorder=3,
               label=r"null $\pm1$ sd")
    ax.plot([mu], [0], marker="o", ms=4.5, color="#4a4f57", zorder=4,
            label="null mean")
    ax.errorbar([c["true"]], [0], xerr=[[c["true"] - c["ci_lo"]],
                                        [c["ci_hi"] - c["true"]]],
                fmt="none", ecolor=ACCENT, elinewidth=1.4, capsize=3, zorder=5)
    ax.axvline(c["true"], color=ACCENT, lw=1.8, zorder=6, label="true placement")
    ax.text(c["true"] + 0.0015, 0.26,
            f"{c['true']:.4f}   {c['exceed']}/{c['n_placebo']} placebos $\\geq$   "
            f"$z={c['z']:+.2f}$",
            color=ACCENT, fontsize=7.4, va="center", ha="left")
    ax.set_yticks([]); ax.set_ylim(-0.42, 0.42)
    ax.set_title(title, fontsize=8.5, loc="left")
    ax.set_xlim(0.930, 1.085)
    return ax


def fig_nulls():
    """Panels come from run_master.py, where every specification shares one
    sample size, so the four panels are directly comparable."""
    m = load("results_master.json")
    if not m:
        raise SystemExit("results_master.json missing; run run_master.py first")
    labels = [("none", "A  no control"),
              ("nowater", "B  water-crossing pairs removed"),
              ("nowater_norail", "C  water and rail crossings removed"),
              ("wateronly", "D  all pairs cross water (held constant)")]
    panels = [(m["controls"][k], lab) for k, lab in labels if k in m["controls"]]

    fig, axes = plt.subplots(len(panels), 1, figsize=(6.2, 1.36 * len(panels)),
                             sharex=True)
    if len(panels) == 1:
        axes = [axes]
    for i, (ax, (c, lab)) in enumerate(zip(axes, panels)):
        _panel(ax, c, lab)
    axes[-1].set_xlabel("severance ratio  (median circuity crossing / same side)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=7, frameon=False, ncol=4, loc="lower center",
               bbox_to_anchor=(0.5, -0.015), handlelength=1.5, columnspacing=1.4)
    fig.suptitle("The Wall against rotated placements of the same curve",
                 fontsize=9.5, y=0.995)
    fig.tight_layout(rect=(0, 0.055, 1, 0.97))
    fig.savefig("fig2_nulls.png")
    print(f"wrote fig2_nulls.png ({len(panels)} panels)")


def fig_finenull():
    """The 71-placement null, drawn from the actual per-placement values."""
    f = load("results_finenull.json")
    if not f or "none" not in f.get("controls", {}):
        print("skipping fig3: results_finenull.json not ready")
        return
    c = f["controls"]["none"]
    p = np.array(c["placebos"])

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(6.2, 3.9), sharex=True,
        gridspec_kw={"height_ratios": [2.1, 1.0], "hspace": 0.12})

    ax.hist(p, bins=18, color=MUTED, alpha=0.55, edgecolor="white", linewidth=0.6)
    ax.axvline(c["true"], color=ACCENT, lw=1.9, zorder=5)
    ax.text(c["true"], ax.get_ylim()[1] * 0.94,
            f"  true {c['true']:.4f}", color=ACCENT, fontsize=8.5,
            va="top", ha="left")
    ax.set_ylabel("placements")
    ax.set_title(f"All {c['n_placebo']} rotated placements versus the true position "
                 f"(p = {c['p_emp']:.4f})", fontsize=9, loc="left")

    ax2.scatter(p, np.zeros_like(p), s=15, color=MUTED, alpha=0.75,
                edgecolor="none", zorder=2, label="placebo placements")
    ax2.axvline(c["true"], color=ACCENT, lw=1.9, zorder=5, label="true placement")
    ax2.annotate("", xy=(c["true"], -0.22), xytext=(max(p), -0.22),
                 arrowprops=dict(arrowstyle="<->", color=INK, lw=0.8))
    ax2.text((c["true"] + max(p)) / 2, -0.34,
             f"no placement reaches it\n(max {max(p):.4f})",
             fontsize=7, ha="center", va="top", color=INK)
    ax2.set_yticks([]); ax2.set_ylim(-0.62, 0.30)
    ax2.set_xlabel("severance ratio  (median circuity crossing / same side)")
    ax2.legend(fontsize=7, frameon=False, loc="upper left", ncol=2)
    fig.tight_layout()
    fig.savefig("fig3_finenull.png")
    print(f"wrote fig3_finenull.png ({c['n_placebo']} placements, "
          f"max {max(p):.4f} vs true {c['true']:.4f})")


if __name__ == "__main__":
    fig_nulls()
    fig_finenull()
    fig_map()

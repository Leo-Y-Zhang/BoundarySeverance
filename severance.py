"""Measure circuity severance across a boundary ring, with rotation placebos.

Design
------
For a closed boundary R we compare two sets of origin-destination pairs drawn
from the same neighbourhood of R:

  CROSS  - exactly one endpoint inside R
  SAME   - both endpoints on the same side of R

Both sets are constrained to identical crow-flies distance bands and both are
required to have their midpoint within `band` metres of R, so the two groups
occupy the same strip of city. Circuity is network distance / crow-flies
distance. The severance ratio is median(CROSS) / median(SAME).

The rotation placebo re-runs the identical procedure on the same ring rotated
about its own centroid. Shape, length and enclosed area are preserved; only the
placement changes. A real boundary effect must stand outside that distribution.
"""
import sys
import numpy as np
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from scipy import stats

from graph import load, project
from fetch import CITIES
from wall import build_ring

sys.stdout.reconfigure(encoding="utf-8")

DMIN, DMAX = 1000.0, 6000.0   # crow-flies band for a sampled trip, metres
BAND = 1500.0                 # pair midpoint must be this close to the boundary
EXCLUDE = 150.0               # nodes this close to the line are side-ambiguous
MAX_TARGETS = 40              # cap per source, keeps sources evenly weighted


def parity_inside(px, py, rx, ry):
    """Vectorised ray-casting: is each (px,py) inside the closed ring (rx,ry)?"""
    inside = np.zeros(len(px), dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        for i in range(len(rx) - 1):
            y1, y2 = ry[i], ry[i + 1]
            if y1 == y2:
                continue
            cond = (y1 > py) != (y2 > py)
            if not cond.any():
                continue
            xint = rx[i] + (py - y1) * (rx[i + 1] - rx[i]) / (y2 - y1)
            inside ^= cond & (px < xint)
    return inside


def rotate(rx, ry, deg):
    if deg == 0:
        return rx, ry
    cx, cy = rx.mean(), ry.mean()
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    dx, dy = rx - cx, ry - cy
    return cx + c * dx - s * dy, cy + s * dx + c * dy


def measure(lat, lon, g, ring_ll, study_bbox, lat0, lon0,
            rotation=0.0, translate=(0.0, 0.0), n_sources=120, seed=0,
            band_mask=None, barriers=None, require=None, verbose=False,
            band=BAND, dmin=DMIN, dmax=DMAX, exclude=EXCLUDE):
    """band_mask selects which ring vertices define the boundary under test.

    Parity (which side a node is on) always uses the full closed ring, since a
    partial arc has no interior. Proximity and midpoint tests use only the
    masked arc, so we can study the inner-city division separately from the
    outer border without breaking inside/outside.
    """
    rng = np.random.default_rng(seed)

    nx, ny = project(lat, lon, lat0, lon0)
    r_lat = np.array([p[0] for p in ring_ll])
    r_lon = np.array([p[1] for p in ring_ll])
    rx, ry = project(r_lat, r_lon, lat0, lon0)
    rx, ry = rotate(rx, ry, rotation)
    rx, ry = rx + translate[0], ry + translate[1]

    if band_mask is None:
        bx, by = rx, ry
    else:
        bx, by = rx[band_mask], ry[band_mask]
        if len(bx) < 50:
            return None

    # distance to boundary via nearest ring vertex (~30 m vertex spacing)
    tree = cKDTree(np.column_stack([bx, by]))
    d_ring, _ = tree.query(np.column_stack([nx, ny]))

    lo_lat, lo_lon, hi_lat, hi_lon = study_bbox
    in_study = (lat >= lo_lat) & (lat <= hi_lat) & (lon >= lo_lon) & (lon <= hi_lon)
    cand = np.flatnonzero(in_study & (d_ring < band + dmax / 2) & (d_ring > exclude))
    if len(cand) < 500:
        return None

    dec = slice(None, None, 3)  # decimate ring for the parity test
    inside = np.zeros(len(lat), dtype=bool)
    inside[cand] = parity_inside(nx[cand], ny[cand], rx[dec], ry[dec])

    src = rng.choice(cand, size=min(n_sources, len(cand)), replace=False)

    rows = []
    for i in range(0, len(src), 40):
        batch = src[i:i + 40]
        D = dijkstra(g, directed=False, indices=batch, limit=dmax * 5)
        for k, s in enumerate(batch):
            net = D[k]
            crow = np.hypot(nx[cand] - nx[s], ny[cand] - ny[s])
            ok = (crow >= dmin) & (crow <= dmax) & np.isfinite(net[cand])
            hits = cand[ok]
            if len(hits) == 0:
                continue
            mx = (nx[hits] + nx[s]) / 2.0
            my = (ny[hits] + ny[s]) / 2.0
            dmid, _ = tree.query(np.column_stack([mx, my]))
            keep = dmid <= band
            hits = hits[keep]
            if len(hits) == 0:
                continue
            if len(hits) > MAX_TARGETS:
                hits = rng.choice(hits, size=MAX_TARGETS, replace=False)
            if barriers or require:
                # cap first, then filter: cheaper, and the subsample is random
                # so dropping barrier-crossing pairs stays unbiased
                xa = np.full(len(hits), nx[s])
                ya = np.full(len(hits), ny[s])
                alive = np.ones(len(hits), dtype=bool)
                for b in barriers or []:
                    alive &= ~b.crosses(xa, ya, nx[hits], ny[hits])
                for b in require or []:
                    alive &= b.crosses(xa, ya, nx[hits], ny[hits])
                hits = hits[alive]
                if len(hits) == 0:
                    continue
            cr = np.hypot(nx[hits] - nx[s], ny[hits] - ny[s])
            circ = net[hits] / cr
            for t, c, cd in zip(hits, circ, cr):
                rows.append((s, t, c, cd, inside[s] != inside[t]))

    if len(rows) < 200:
        return None

    circ = np.array([r[2] for r in rows])
    cross = np.array([r[4] for r in rows])
    a, b = circ[cross], circ[~cross]
    if len(a) < 50 or len(b) < 50:
        return None

    ratio = float(np.median(a) / np.median(b))
    try:
        u = stats.mannwhitneyu(a, b, alternative="greater")
        p = float(u.pvalue)
    except ValueError:
        p = float("nan")

    return {
        "n_cross": int(len(a)), "n_same": int(len(b)),
        "med_cross": float(np.median(a)), "med_same": float(np.median(b)),
        "mean_cross": float(a.mean()), "mean_same": float(b.mean()),
        "ratio": ratio, "p": p,
        "circ": circ, "cross": cross,
        "src": np.array([r[0] for r in rows]),
        "dst": np.array([r[1] for r in rows]),
        "crow": np.array([r[3] for r in rows]),
    }


def bootstrap_ci(res, n=2000, seed=1):
    """Naive pair-level bootstrap. Reported only for comparison: it treats pairs
    as independent when up to MAX_TARGETS of them share an origin node, so it is
    anticonservative. Use cluster_bootstrap_ci for inference."""
    rng = np.random.default_rng(seed)
    a = res["circ"][res["cross"]]
    b = res["circ"][~res["cross"]]
    out = np.empty(n)
    for i in range(n):
        out[i] = (np.median(rng.choice(a, len(a))) /
                  np.median(rng.choice(b, len(b))))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def cluster_bootstrap_ci(res, n=2000, seed=1):
    """Resample source nodes, not pairs.

    Every pair sharing an origin is drawn from one Dijkstra tree and one
    neighbourhood, so pairs are clustered by source. Resampling whole clusters
    is the honest interval.
    """
    rng = np.random.default_rng(seed)
    src = res["src"]
    circ = res["circ"]
    cross = res["cross"]
    uniq = np.unique(src)
    idx_by_src = {s: np.flatnonzero(src == s) for s in uniq}
    out = []
    for _ in range(n):
        pick = rng.choice(uniq, len(uniq), replace=True)
        idx = np.concatenate([idx_by_src[s] for s in pick])
        c, x = circ[idx], cross[idx]
        if x.sum() < 20 or (~x).sum() < 20:
            continue
        out.append(np.median(c[x]) / np.median(c[~x]))
    out = np.array(out)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))

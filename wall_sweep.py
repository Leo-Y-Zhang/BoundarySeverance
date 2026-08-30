# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Find the role-filter / tolerance combination that yields a clean closed ring."""
import sys

from osm import haversine
from wall import chain, load_members, ring_length_km

sys.stdout.reconfigure(encoding="utf-8")

members = load_members()

FILTERS = {
    "all": lambda r: True,
    "no-alt": lambda r: r != "alternative",
    "no-alt-no-back": lambda r: r not in ("alternative", "backward"),
    "main-only": lambda r: r == "",
}

print(f"{'filter':>16} {'prec':>5} {'ways':>6} {'chains':>7} {'largest_km':>11} {'gap_m':>10}")
best = None
for name, fn in FILTERS.items():
    subset = [m for m in members if fn(m["role"])]
    for prec in (7, 6, 5, 4):
        chains = chain(subset, prec)
        big = chains[0]
        gap = haversine(big[0][0], big[0][1], big[-1][0], big[-1][1])
        km = ring_length_km(big)
        print(f"{name:>16} {prec:>5} {len(subset):>6} {len(chains):>7} {km:>11.1f} {gap:>10.1f}")
        score = (km, -gap)
        if gap < 3000 and (best is None or km > best[0]):
            best = (km, name, prec, gap)

print("\nbest:", best)

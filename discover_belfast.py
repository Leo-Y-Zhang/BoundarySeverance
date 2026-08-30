# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Is there usable peace-line geometry in OSM for Belfast?

Belfast is the interesting middle case: many peace lines still stand, some have
gates that close nightly, and a few have been removed. If the geometry exists,
it sits between Nicosia (closed) and Berlin (removed) on the same scale.
"""
import collections
import sys

from osm import overpass

sys.stdout.reconfigure(encoding="utf-8")

BBOX = "54.53,-6.06,54.68,-5.80"

Q = f"""
[out:json][timeout:300];
(
  way["barrier"]["name"~"[Pp]eace",i]({BBOX});
  way["barrier"="wall"]["wall"="peace_line"]({BBOX});
  way["barrier"]["description"~"[Pp]eace",i]({BBOX});
  way["man_made"="wall"]({BBOX});
  way["barrier"="wall"]({BBOX});
  way["barrier"="fence"]["height"]({BBOX});
);
out tags;
"""

d = overpass(Q, tag="belfast_discover")
els = d.get("elements", [])
print(f"elements: {len(els)}\n")

sig = collections.Counter()
names = collections.Counter()
for e in els:
    t = e.get("tags", {})
    sig[(t.get("barrier"), t.get("wall"), t.get("man_made"))] += 1
    n = t.get("name") or t.get("description")
    if n:
        names[n] += 1

print("-- (barrier, wall, man_made) --")
for k, v in sig.most_common(12):
    print(f"  {v:5d}  {k}")
print("\n-- named features --")
for k, v in names.most_common(25):
    print(f"  {v:4d}  {k[:70]}")

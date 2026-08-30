"""Find out what Berlin Wall geometry actually exists in OSM before relying on it."""
import collections
from osm import overpass

BBOX = "52.33,13.08,52.70,13.77"

Q = f"""
[out:json][timeout:300];
(
  way["historic"="citywall"]({BBOX});
  way["barrier"="wall"]["name"~"Mauer",i]({BBOX});
  way["historic"="berlin_wall"]({BBOX});
  relation["name"~"Mauerweg",i]({BBOX});
  relation["name"~"Berliner Mauer",i]({BBOX});
);
out tags;
"""

data = overpass(Q, tag="discover_wall")
els = data.get("elements", [])
print(f"elements returned: {len(els)}")

by_kind = collections.Counter()
names = collections.Counter()
for e in els:
    t = e.get("tags", {})
    kind = (e["type"], t.get("historic"), t.get("barrier"), t.get("route"), t.get("type"))
    by_kind[kind] += 1
    if t.get("name"):
        names[t["name"]] += 1

print("\n-- signature (type, historic, barrier, route, reltype) --")
for k, n in by_kind.most_common(20):
    print(f"  {n:5d}  {k}")

print("\n-- most common names --")
for k, n in names.most_common(15):
    print(f"  {n:5d}  {k}")

print("\n-- sample relations --")
for e in els:
    if e["type"] == "relation":
        print(" ", e["id"], e.get("tags", {}))

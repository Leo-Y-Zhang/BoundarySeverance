# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Find usable geometry for the UN Buffer Zone in Cyprus - the positive control.

Berlin's boundary was removed in 1989. If the method finds nothing there, that
could mean the Wall left no trace, or that the method cannot detect anything.
A boundary that is still closed today distinguishes those two possibilities.
"""
import sys

from osm import overpass

sys.stdout.reconfigure(encoding="utf-8")

BBOX = "34.95,32.70,35.45,33.95"

Q = f"""
[out:json][timeout:300];
(
  rel["name"~"Buffer Zone",i]({BBOX});
  rel["name"~"Green Line",i]({BBOX});
  way["barrier"~"^(wall|fence)$"]["name"~"Buffer|Green",i]({BBOX});
  rel["boundary"="administrative"]["admin_level"="2"]({BBOX});
  rel["boundary"="military"]({BBOX});
);
out tags;
"""

d = overpass(Q, tag="cyprus_discover")
els = d.get("elements", [])
print(f"elements: {len(els)}\n")

for e in els:
    t = e.get("tags", {})
    name = t.get("name") or t.get("name:en") or "(unnamed)"
    keys = {k: v for k, v in t.items()
            if k in ("boundary", "admin_level", "type", "barrier", "place",
                     "border_type", "name:en", "wikidata")}
    print(f"{e['type']:>8} {e['id']:>12}  {name[:44]:<46} {keys}")

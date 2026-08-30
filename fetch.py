"""Fetch the two inputs: the Wall trace and the drivable road network."""
import sys
from osm import overpass

sys.stdout.reconfigure(encoding="utf-8")

DRIVE = r"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street)(_link)?$"

# Sampling happens inside STUDY; routing uses ROUTE, a buffer ~8-10 km wider so
# that a legitimate detour is never truncated by the edge of the extract.
CITIES = {
    "berlin": {
        "route_bbox": (52.33, 13.05, 52.68, 13.70),
        "study_bbox": (52.42, 13.18, 52.60, 13.55),
    },
    "hamburg": {  # placebo: comparable size and flatness, never partitioned
        "route_bbox": (53.40, 9.75, 53.70, 10.25),
        "study_bbox": (53.49, 9.88, 53.63, 10.12),
    },
    "nicosia": {  # positive control: a boundary still closed today
        "route_bbox": (35.00, 33.10, 35.40, 33.65),
        "study_bbox": (35.10, 33.25, 35.27, 33.50),
    },
}


def fetch_wall():
    q = """
    [out:json][timeout:600];
    rel(9030);
    out geom;
    """
    d = overpass(q, tag="mauerweg")
    els = d["elements"]
    members = [m for e in els for m in e.get("members", []) if m.get("geometry")]
    pts = sum(len(m["geometry"]) for m in members)
    print(f"mauerweg: {len(members)} member ways with geometry, {pts} points")
    return d


def fetch_roads(city):
    lo_lat, lo_lon, hi_lat, hi_lon = CITIES[city]["route_bbox"]
    q = f"""
    [out:json][timeout:900];
    (
      way["highway"~"{DRIVE}"]["area"!~"yes"]["access"!~"^(no|private)$"]
         ({lo_lat},{lo_lon},{hi_lat},{hi_lon});
    );
    out body;
    >;
    out skel qt;
    """
    d = overpass(q, tag=f"roads_{city}")
    ways = sum(1 for e in d["elements"] if e["type"] == "way")
    nodes = sum(1 for e in d["elements"] if e["type"] == "node")
    print(f"{city}: {ways} ways, {nodes} nodes")
    return d


if __name__ == "__main__":
    fetch_wall()
    for c in sys.argv[1:] or ["berlin"]:
        fetch_roads(c)

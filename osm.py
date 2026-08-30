# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Overpass client with on-disk caching, plus geometry helpers.

Deliberately stdlib-only apart from numpy so the pipeline is reproducible
without a geospatial stack.
"""
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def overpass(query, tag=""):
    """Run an Overpass QL query, caching the result by query hash."""
    key = hashlib.sha256(query.encode()).hexdigest()[:16]
    path = os.path.join(CACHE, f"{tag}_{key}.json" if tag else f"{key}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    last = None
    for attempt in range(6):
        endpoint = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(
                endpoint,
                data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": "severance-study/0.1 (research; contact via repo)"},
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            return data
        except Exception as exc:  # noqa: BLE001 - report and back off
            last = exc
            wait = 15 * (attempt + 1)
            print(f"  overpass attempt {attempt + 1} failed ({exc}); sleeping {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Overpass failed after retries: {last}")


R_EARTH = 6371008.8  # mean Earth radius, metres


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def local_xy(lat, lon, lat0, lon0):
    """Equirectangular projection about (lat0, lon0). Metres.

    Adequate for city-scale work: distortion over a ~40 km span at 50-55N is
    well below the precision this study claims.
    """
    x = math.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * R_EARTH
    return x, y


def seg_intersect(p1, p2, p3, p4):
    """True if segment p1-p2 properly intersects segment p3-p4 (planar xy)."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1 = cross(p3, p4, p1)
    d2 = cross(p3, p4, p2)
    d3 = cross(p1, p2, p3)
    d4 = cross(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

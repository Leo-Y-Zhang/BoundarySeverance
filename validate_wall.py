# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Validate the assembled ring against ground truth before anything is built on it.

If this file does not print ALL PASS, no downstream result is trustworthy.
"""
import sys

from osm import local_xy
from wall import build_ring, point_in_ring, ring_area_km2

sys.stdout.reconfigure(encoding="utf-8")

LAT0, LON0 = 52.51, 13.40

# West Berlin: enclosed by the Wall, so inside the ring.
WEST = {
    "Charlottenburg Palace": (52.5209, 13.2957),
    "Tempelhofer Feld": (52.4730, 13.4036),
    "Wannsee": (52.4213, 13.1789),
    "Zoologischer Garten": (52.5073, 13.3324),
    "Spandau Rathaus": (52.5353, 13.1997),
    "Goerlitzer Park (Kreuzberg)": (52.4972, 13.4400),
    "Leopoldplatz (Wedding)": (52.5486, 13.3597),
    "Tegel": (52.5597, 13.2877),
}

# East Berlin and surrounding Brandenburg: outside the ring.
EAST = {
    "Alexanderplatz": (52.5219, 13.4132),
    "Frankfurter Tor": (52.5157, 13.4543),
    "Kollwitzplatz (Prenzlauer Berg)": (52.5359, 13.4184),
    "Lichtenberg": (52.5099, 13.4966),
    "Koepenick": (52.4553, 13.5760),
    "Pankow Rathaus": (52.5690, 13.4020),
    "Treptower Park": (52.4880, 13.4690),
    "Marzahn": (52.5450, 13.5620),
    "Teltow (Brandenburg)": (52.4020, 13.2730),
    "Hennigsdorf (Brandenburg)": (52.6350, 13.2030),
}

def main():
    ring = build_ring()
    ring_xy = [local_xy(la, lo, LAT0, LON0) for la, lo in ring]
    area = ring_area_km2(ring_xy)

    print(f"\nenclosed area: {area:.1f} km2   (West Berlin was 480 km2)")

    fails = 0
    print("\n-- expect INSIDE (West Berlin) --")
    for name, (la, lo) in WEST.items():
        got = point_in_ring(la, lo, ring_xy, LAT0, LON0)
        ok = "ok " if got else "FAIL"
        fails += 0 if got else 1
        print(f"  {ok}  {name:<32} inside={got}")

    print("\n-- expect OUTSIDE (East Berlin / Brandenburg) --")
    for name, (la, lo) in EAST.items():
        got = point_in_ring(la, lo, ring_xy, LAT0, LON0)
        ok = "ok " if not got else "FAIL"
        fails += 0 if not got else 1
        print(f"  {ok}  {name:<32} inside={got}")

    area_ok = 400 <= area <= 560
    print(f"\narea within 400-560 km2: {'ok' if area_ok else 'FAIL'}")
    fails += 0 if area_ok else 1

    print("\n" + ("ALL PASS" if fails == 0 else f"{fails} CHECKS FAILED"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""BoundarySeverance CLI.

  boundaryseverance validate
      Check the reconstructed geometry against independent ground truth before
      anything is measured: the assembled Wall ring must enclose the right area
      and put 18 known landmarks on the correct sides. If this fails, nothing
      downstream is worth reading, so every other command depends on it.

  boundaryseverance fetch [--city berlin,hamburg,nicosia]
      Download and cache the road networks. Roughly 130 MB on a cold run;
      afterwards everything is offline and deterministic.

  boundaryseverance measure [--city berlin] [--sources 600]
      Run the severance measurement for one boundary against its rotation null
      and print the ratio, the interval and the placebo comparison.

  boundaryseverance paper
      Regenerate every figure and rebuild the manuscript, injecting all values
      from the result files. Fails if any value is missing, so the text cannot
      drift from the analysis.

  boundaryseverance verify
      Offline unit and mutation checks. The mutation pass deliberately breaks
      the geometry and fails if the tests do not notice.

The layout here is flat rather than a src/ package on purpose: this is a
research pipeline, and one module per stage of the method section is easier to
follow against the paper than a nested package would be.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def cmd_validate(args) -> int:
    import validate_wall
    try:
        validate_wall.main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def cmd_fetch(args) -> int:
    import fetch
    fetch.fetch_wall()
    for city in args.city.split(","):
        fetch.fetch_roads(city.strip())
    return 0


def cmd_measure(args) -> int:
    from fetch import CITIES
    from graph import load
    from segments import classify
    from severance import bootstrap_ci, measure
    from wall import build_ring

    if args.city != "berlin":
        print("only the Berlin ring is wired into this command; "
              "run run_cyprus.py for Nicosia", file=sys.stderr)
        return 2

    lat, lon, g = load("berlin", verbose=False)
    ring = build_ring(verbose=False)
    bbox = CITIES["berlin"]["study_bbox"]
    lat0, lon0 = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    inner = classify(ring, lat0, lon0, verbose=False)

    true = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=0.0,
                   n_sources=args.sources, seed=0, band_mask=inner)
    if true is None:
        print("insufficient pairs", file=sys.stderr)
        return 1
    lo, hi = bootstrap_ci(true)
    print(f"true placement   S = {true['ratio']:.4f}  95% CI [{lo:.4f}, {hi:.4f}]")
    print(f"                 {true['n_cross']} crossing / {true['n_same']} same-side pairs")

    placebos = []
    for deg in range(args.step, 360, args.step):
        r = measure(lat, lon, g, ring, bbox, lat0, lon0, rotation=float(deg),
                    n_sources=args.sources, seed=100 + deg, band_mask=inner)
        if r:
            placebos.append(r["ratio"])
            print(f"  rotation {deg:3d} deg   {r['ratio']:.4f}")
    if placebos:
        import numpy as np
        arr = np.array(placebos)
        exceed = int((arr >= true["ratio"]).sum())
        print(f"\nplacebo mean {arr.mean():.4f} +/- {arr.std(ddof=1):.4f}"
              f"   max {arr.max():.4f}")
        print(f"placebos reaching the true placement: {exceed}/{len(arr)}"
              f"   empirical p = {(exceed + 1) / (len(arr) + 1):.4f}")
    return 0


def cmd_paper(args) -> int:
    for step in (["python", "figures.py"], ["python", "make_paper.py"]):
        r = subprocess.run(step)
        if r.returncode != 0:
            return r.returncode
    return 0


def cmd_verify(args) -> int:
    import unittest
    suite = unittest.TestLoader().discover("tests")
    ok = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    if not ok.wasSuccessful():
        return 1
    if args.mutation:
        return subprocess.run([sys.executable, "tests/mutation_check.py"]).returncode
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="boundaryseverance", description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="command")

    sub.add_parser("validate", help="geometry ground-truth checks").set_defaults(
        func=cmd_validate)

    f = sub.add_parser("fetch", help="download and cache road networks")
    f.add_argument("--city", default="berlin,hamburg")
    f.set_defaults(func=cmd_fetch)

    m = sub.add_parser("measure", help="severance against the rotation null")
    m.add_argument("--city", default="berlin")
    m.add_argument("--sources", type=int, default=600)
    m.add_argument("--step", type=int, default=45,
                   help="rotation step in degrees for the placebo set")
    m.set_defaults(func=cmd_measure)

    sub.add_parser("paper", help="rebuild figures and the manuscript").set_defaults(
        func=cmd_paper)

    v = sub.add_parser("verify", help="unit tests and the mutation check")
    v.add_argument("--verbose", action="store_true")
    v.add_argument("--mutation", action="store_true",
                   help="also run the mutation check (slower)")
    v.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

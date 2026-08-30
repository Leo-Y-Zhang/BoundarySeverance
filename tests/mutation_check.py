"""Prove the unit tests actually fail when the code is wrong.

A suite that has never been observed failing is decoration. This applies a
series of single-line mutations to the geometric primitives, runs the suite
against each, and asserts that every mutation is caught. It restores the
original files whether or not it succeeds.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

# (file, find, replace, description). Entries marked EQUIVALENT are expected to
# survive: they are refactorings, not defects, and are kept as documentation of
# why. Everything else must be caught.
EQUIVALENT = {
    "parity: ray cast in the other direction",
    "parity: drop the horizontal-edge fast path",
}

MUTATIONS = [
    ("severance.py",
     "return cx + c * dx - s * dy, cy + s * dx + c * dy",
     "return cx + c * dx + s * dy, cy + s * dx + c * dy",
     "rotate: sign flip breaks the rotation matrix"),
    ("severance.py",
     "inside ^= cond & (px < xint)",
     "inside ^= cond & (px > xint)",
     "parity: ray cast in the other direction"),
    ("severance.py",
     "inside ^= cond & (px < xint)",
     "inside |= cond & (px < xint)",
     "parity: OR instead of XOR, so concave shapes break"),
    ("severance.py",
     "if y1 == y2:\n                continue",
     "if False:\n                continue",
     "parity: drop the horizontal-edge fast path"),
    ("osm.py",
     "return 2 * R_EARTH * math.asin(math.sqrt(a))",
     "return 2 * R_EARTH * math.sqrt(a)",
     "haversine: drop the arcsine"),
    ("osm.py",
     "x = math.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0))",
     "x = math.radians(lon - lon0) * R_EARTH",
     "projection: forget the latitude compression"),
    ("wall.py",
     "return abs(s) / 2.0 / 1e6",
     "return s / 2.0 / 1e6",
     "ring area: drop abs, so orientation changes the sign"),
    ("wall.py",
     "if x < xint:\n                inside = not inside",
     "if x < xint:\n                inside = inside",
     "point_in_ring: never toggle, so everything reads outside"),
    ("barriers.py",
     "return hit.any(axis=1)",
     "return np.zeros(len(xa), dtype=bool)",
     "barrier grid: never report a crossing"),
    ("barriers.py",
     "def crosses(self, xa, ya, xb, yb, skip_ends=60.0):",
     "def crosses(self, xa, ya, xb, yb, skip_ends=0.0):",
     "barrier grid: stop trimming ends, so quayside roads count as crossings"),
    ("wall.py",
     "ends.setdefault(a, []).append((i, \"head\"))",
     "ends.setdefault(a, []).append((i, \"tail\"))",
     "chain: mislabel a head as a tail"),
]


def purge_bytecode():
    """Essential, not tidiness.

    CPython validates a .pyc against the source's mtime (whole seconds) and
    size. A mutation like '^=' -> '|=' changes neither, and the mutate-run-
    restore cycle completes inside one second, so the stale bytecode is reused
    and the mutation never runs. The harness then reports the mutation as
    survived when it was never applied -- a false negative that makes the whole
    check worthless. This was observed, not theorised.
    """
    for dirpath, dirnames, _ in os.walk(ROOT):
        for d in list(dirnames):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)
                dirnames.remove(d)


def run_suite():
    purge_bytecode()
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                       cwd=ROOT, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return r.returncode


def main():
    backup = tempfile.mkdtemp(prefix="mutation-backup-")
    touched = {m[0] for m in MUTATIONS}
    for f in touched:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(backup, f))

    try:
        base = run_suite()
        if base != 0:
            print("BASELINE SUITE IS ALREADY FAILING - fix that first")
            return 1
        print(f"baseline: suite passes\n")

        survived = []
        for i, (fname, find, repl, desc) in enumerate(MUTATIONS, 1):
            path = os.path.join(ROOT, fname)
            original = open(path, encoding="utf-8").read()
            if find not in original:
                print(f"{i:2d}. SKIP  {desc}\n      (pattern not found in {fname})")
                survived.append(desc + " [pattern missing]")
                continue
            open(path, "w", encoding="utf-8").write(original.replace(find, repl, 1))
            rc = run_suite()
            open(path, "w", encoding="utf-8").write(original)
            equiv = desc in EQUIVALENT
            if rc == 0 and not equiv:
                print(f"{i:2d}. SURVIVED  {desc}")
                survived.append(desc)
            elif rc == 0 and equiv:
                print(f"{i:2d}. equivalent (expected to survive)  {desc}")
            elif equiv:
                print(f"{i:2d}. UNEXPECTED: an equivalent mutation was caught -- "
                      f"the test asserts an implementation detail: {desc}")
                survived.append("over-specified test: " + desc)
            else:
                print(f"{i:2d}. caught    {desc}")

        print()
        if survived:
            print(f"{len(survived)} of {len(MUTATIONS)} mutations SURVIVED:")
            for s in survived:
                print(f"  - {s}")
            return 1
        print(f"all {len(MUTATIONS) - len(EQUIVALENT)} real mutations caught; "
              f"{len(EQUIVALENT)} equivalent mutations survived as expected")
        return 0
    finally:
        for f in touched:
            shutil.copy2(os.path.join(backup, f), os.path.join(ROOT, f))
        shutil.rmtree(backup, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

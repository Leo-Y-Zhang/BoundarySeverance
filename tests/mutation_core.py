# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Reproducible, isolated single-fault experiment (not part of pytest collection).

Run with --suite before or --suite after. 'before' copies only the two original
unittest/mutation files, then runs the original unit, CLI and manuscript CI checks. 'after'
adds pytest first. No production file in the checkout is ever modified. Results
include the failing command and its output, and are written as JSON.
"""
import argparse
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Exact replacements intentionally keep every mutant syntactically valid.
MUTATIONS = [
    ("validate_wall.py", "0 if got else 1", "0", "ignore an inside landmark failure"),
    ("validate_wall.py", "0 if not got else 1", "0", "ignore an outside landmark failure"),
    ("validate_wall.py", "400 <= area <= 560", "True", "skip area check"),
    ("validate_wall.py", "400 <= area <= 560", "400 < area <= 560", "reject lower area endpoint"),
    ("validate_wall.py", "400 <= area <= 560", "400 <= area < 560", "reject upper area endpoint"),
    ("validate_wall.py", "0 if area_ok else 1", "0", "do not count invalid area"),
    ("validate_wall.py", "1 if fails else 0", "0", "always return successful exit status"),
    ("cyprus.py", "0 if got else 1", "0", "ignore a north landmark failure"),
    ("cyprus.py", "0 if not got else 1", "0", "ignore a south landmark failure"),
    ("cyprus.py", "return fails == 0", "return fails >= 0", "accept every ring"),
    ("cyprus.py", '            if g and len(g) > 1:', '            if g and len(g) > 2:', "drop two-point geometry"),
    ("cyprus.py", 'if w == "t":', 'if w != "t":', "reverse the wrong chain endpoint"),
    ("cyprus.py", 'chains.sort(key=len, reverse=True)', 'chains.sort(key=len, reverse=False)', "choose shortest divide chain"),
    ("graph.py", 'if prev is not None and prev != cur:', 'if prev is not None and prev == cur:', "drop distinct-node edges"),
    ("graph.py", '                prev = None\n                continue', '                continue', "bridge a missing road node"),
    ("graph.py", 'rows.append(cur); cols.append(prev); w.append(d)', 'rows.append(prev); cols.append(cur); w.append(d)', "lose reverse edges and double forward weights"),
    ("graph.py", 'labels == sizes.argmax()', 'labels != sizes.argmax()', "keep smaller components"),
    ("graph.py", 'if d > 0:', 'if d < 0:', "discard positive road lengths"),
    ("osm.py", 'if os.path.exists(path):', 'if not os.path.exists(path):', "ignore cached response"),
    ("osm.py", 'return json.load(fh)', 'return {}', "accept cache without parsing JSON"),
    ("wall.py", 'm["role"] != "alternative"', 'm["role"] == "alternative"', "keep only alternative route"),
    ("wall.py", 'if gap > 1.0:', 'if gap < 1.0:', "leave open ring unclosed"),
    ("wall.py", 'if not g or len(g) < 2:', 'if not g or len(g) <= 2:', "drop valid two-point member"),
    ("segments.py", 'inner = d > tol', 'inner = d < tol', "invert inner versus outer classification"),
    ("severance.py", 'net[hits] / cr', 'cr / net[hits]', "invert circuity"),
    ("severance.py", 'np.median(a) / np.median(b)', 'np.median(b) / np.median(a)', "invert severance ratio"),
    ("severance.py", 'alive &= ~b.crosses', 'alive &= b.crosses', "retain forbidden barrier crossings"),
    ("severance.py", 'alive &= b.crosses', 'alive &= ~b.crosses', "discard required barrier crossings"),
    ("severance.py", 'if barriers or require:', 'if barriers and require:', "skip a lone barrier control"),
    ("severance.py", '(crow >= dmin) & (crow <= dmax) & np.isfinite(net[cand])', '(crow >= dmin) & (crow <= dmax)', "include unreachable trips"),
    ("severance.py", 'keep = dmid <= band', 'keep = dmid >= band', "keep midpoints outside boundary band"),
    ("severance.py", 'if len(rows) < 200:', 'if len(rows) < 0:', "accept insufficient total pairs"),
    ("severance.py", 'if len(a) < 50 or len(b) < 50:', 'if len(a) < 50 and len(b) < 50:', "accept insufficient pairs on one side"),
    ("severance.py", 'np.median(rng.choice(a, len(a))) /', 'np.median(rng.choice(a, len(a))) *', "multiply bootstrap medians"),
    ("severance.py", 'src == s', 'src != s', "resample all other source clusters"),
    ("severance.py", 'if x.sum() < 20 or (~x).sum() < 20:', 'if x.sum() < 20 and (~x).sum() < 20:', "retain undersized bootstrap class"),
    ("make_paper.py", "raise KeyError(f\"template needs '{k}' but it was not computed\")", 'return ""', "silently omit missing template value"),
    ("make_paper.py", 'if leftover:', 'if False:', "allow unfilled placeholders"),
]


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            timeout=60, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                             "TECTONIC": "/nonexistent/tectonic"})
    return {"command": command[1:], "returncode": result.returncode,
            "output": result.stdout + result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("before", "after"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    existing = runpy.run_path(str(ROOT / "tests/mutation_check.py"))
    mutants = list(MUTATIONS) + [m for m in existing["MUTATIONS"]
                                if m[3] not in existing["EQUIVALENT"]]
    commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                [sys.executable, "cli.py", "--help"],
                [sys.executable, "make_paper.py"]]
    if args.suite == "after":
        commands.insert(0, [sys.executable, "-m", "pytest", "-q", "-x"])
    (ROOT / "cache").mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="core-mutations-", dir=ROOT / "cache") as tmp:
        sandbox = Path(tmp)
        for pattern in ("*.py", "*.json", "*.tex", "pyproject.toml"):
            for source in ROOT.glob(pattern):
                shutil.copy2(source, sandbox / source.name)
        (sandbox / "tests").mkdir()
        names = ([p.name for p in (ROOT / "tests").glob("*.py")]
                 if args.suite == "after" else ["test_geometry.py", "mutation_check.py"])
        for name in names:
            shutil.copy2(ROOT / "tests" / name, sandbox / "tests" / name)
        # Avoid importing this checkout through the editable installation.
        baseline = [run(command, sandbox) for command in commands]
        if any(r["returncode"] for r in baseline):
            raise RuntimeError(f"Unmutated gate failed: {baseline}")
        for number, (module, old, new, description) in enumerate(mutants, 1):
            path = sandbox / module
            original = path.read_bytes()
            source = original.decode().replace("\r\n", "\n")
            if source.count(old) != 1:
                raise RuntimeError(f"Ambiguous or missing mutation: {module}: {old!r}")
            try:
                mutated = source.replace(old, new, 1)
                compile(mutated, module, "exec")
                path.write_text(mutated)
                checks = []
                for command in commands:
                    checks.append(run(command, sandbox))
                    if checks[-1]["returncode"]:
                        break
                killed = bool(checks[-1]["returncode"])
                result = dict(module=module, mutation=description, old=old, new=new,
                              killed=killed, checks=checks)
                results.append(result)
                print(f"{number:02}/{len(mutants)} {'KILLED' if killed else 'SURVIVED'} "
                      f"{module}: {description}", flush=True)
            finally:
                path.write_bytes(original)
    args.output.write_text(json.dumps({"suite": args.suite, "baseline": baseline,
                                      "results": results}, indent=2) + "\n")
    totals = defaultdict(lambda: [0, 0])
    for result in results:
        counts = totals[result["module"]]
        counts[0] += 1
        counts[1] += result["killed"]
    for module, (tried, killed) in sorted(totals.items()):
        print(f"{module}: {killed}/{tried} killed")
    if args.suite == "after" and any(not result["killed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

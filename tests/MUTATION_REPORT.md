# Mutation-guided unit tests

Added 44 pytest cases across four new test files. Production code is unchanged;
no import seam or runtime dependency was needed. CI installs `pytest==8.4.2`
and runs one `pytest -q` step. `pytest.ini` limits discovery to `tests/`, keeping
isolated mutation copies under `cache/` out of normal test collection.

## Measured mutations

The primary validity decisions here are the two landmark/area validators and
the manuscript completeness guard; this repository has no SAT certificate
format. The other targeted modules parse, assemble and classify geometry,
build routable graphs, and calculate the severance statistic and intervals.

These are 49 selected, syntactically valid, single-fault mutations, not an
exhaustive mutation score for these modules. All 37 meaningful survivors of the
original checks are now killed. The two equivalent mutations already documented
by the original harness are excluded from this table; both still survive as
expected when that harness runs.

| Module | Mutants tried | Killed before | Killed after |
|---|---:|---:|---:|
| `barriers.py` | 2 | 2 | 2 |
| `cyprus.py` | 6 | 0 | 6 |
| `graph.py` | 5 | 0 | 5 |
| `make_paper.py` | 2 | 0 | 2 |
| `osm.py` | 4 | 2 | 4 |
| `segments.py` | 1 | 0 | 1 |
| `severance.py` | 16 | 5 | 16 |
| `validate_wall.py` | 7 | 0 | 7 |
| `wall.py` | 6 | 3 | 6 |
| **Total** | **49** | **12** | **49** |

Before: each mutant ran the original `python -m unittest discover -s tests -v`,
`python cli.py --help`, and `python make_paper.py`, stopping on the first failure.
Only the original two test/harness files were copied into that baseline. After:
the same checks, with `python -m pytest -q -x` first and the expanded suite.
Static checks and the original mutation harness were checked separately as
shown below, rather than rerunning nested mutation experiments per candidate.
Every killed mutant in the after run failed a pytest test, not a static check.

`mutation_core.py` copies inputs into an isolated temporary directory under
`cache/`, applies one exact replacement, runs fresh subprocesses with bytecode
writes disabled, and restores source bytes in `finally`. Missing/ambiguous
patterns, syntax errors, baseline failures, and timeouts abort the experiment.
The after run exits nonzero if any candidate survives. No mutation modifies
production files in the working tree.

Reproduce from the repository root after installing the project, pytest and ruff:

```sh
python tests/mutation_core.py --suite before --output cache/mutation-before.json
python tests/mutation_core.py --suite after --output cache/mutation-after.json
pytest -q --durations=5
```

[mutation_results.json](mutation_results.json) records every exact replacement,
its source line, before/after status and the first failing pytest test.

## New tests and faults they catch

| File | Coverage and at least one killed mutant |
|---|---|
| `test_validation.py` | Both landmark validators accept valid rings and reject changed landmark sides, displaced/changed vertices, removed corners, truncated/empty rings and invalid area. Kills `validate_wall.main`: `fails += 0 if got else 1` changed to `fails += 0`; also `cyprus.validate`: `return fails == 0` changed to `return fails >= 0`. |
| `test_inputs.py` | Offline cached JSON, two-point geometry, reversed/disconnected chains, alternative routes, graph weights/connectivity and boundary classification. Kills `graph.load`: remove `prev = None` when a node is missing, inventing a shortcut; kills `osm.overpass`: return `{}` without parsing a truncated cache. |
| `test_severance.py` | Real sparse shortest paths on a 961-node grid, a costly boundary, counts/distances, barrier exclusions/requirements, unreachable trips, pair-count guards, and hand-calculated bootstrap resamples. Kills `measure`: reverse `median(cross) / median(same)`; kills `cluster_bootstrap_ci`: `src == s` changed to `src != s`. |
| `test_paper_validation.py` | Accepts a small valid template and rejects missing values, malformed placeholders, missing result keys and truncated JSON before writing output. Kills `make_paper.py`: `if leftover:` changed to `if False:`; also replaces the missing-value `KeyError` with `return ""`. |

Mutation feedback exposed two weak cases that were strengthened: projection
rounding hid the exact upper area endpoint, and a symmetric grid gave the same
crossing/same-side median, hiding ratio inversion. Exact endpoint checks and a
boundary with an extra 1,000 m routing cost make those faults observable.

## Commands and results

Commands used the local `.venv` Python 3.11 environment. Dependency setup:
`.venv/bin/python -m pip install -e . pytest==8.4.2 ruff` succeeded.
Both mutation commands above completed successfully: 12/49 killed before,
49/49 killed after. The full pytest output from
`PATH=/work/.venv/bin:$PATH pytest -q --durations=5` was:

```text
........................................................................ [ 82%]
...............                                                          [100%]
============================= slowest 5 durations ==============================
0.07s call     tests/test_geometry.py::TestMeasureSides::test_closed_ring_keeps_its_closing_edge
0.05s call     tests/test_severance.py::test_measure_enforces_each_barrier_control[barriers]
0.05s call     tests/test_severance.py::test_measure_enforces_each_barrier_control[require]
0.05s setup    tests/test_paper_validation.py::test_manuscript_rejects_corrupt_result_file[truncated]
0.04s call     tests/test_geometry.py::TestMeasureSides::test_open_line_closed_into_a_ring
87 passed in 6.91s
```

The entire suite took less than 60 seconds; every reported test call/setup was
under 2 seconds. All new inputs are tiny synthetic data or committed result
JSON; no test performs network access, SAT solving, or experiment regeneration.

Existing CI gate commands, all successful in a writable isolated copy:

| Command | Result |
|---|---|
| `python scripts/check_spdx.py` | All 39 source files carry the identifier. |
| `ruff check .` | All checks passed. |
| `python -m unittest discover -s tests -v` | 43 tests, OK; also rerun in the working tree after the final test change. |
| `python cli.py --help` | Exit 0. |
| `python tests/mutation_check.py` | 11 real mutants caught; 2 equivalent mutants survive as expected; exit 0. |
| `python make_paper.py` | Exit 0; 151 values injected, no unfilled placeholders. |

The original mutation command first caught all its real mutants in the mounted
checkout, then failed while restoring timestamps (`PermissionError` from
`shutil.copy2`). Original source bytes were restored and that command, plus the
other gate checks, passed in a writable copy. No production diff remains.
Optional PDF compilation was skipped because Tectonic is unavailable. Python
3.13 and live-data workflows were not run locally. No implementation fixes are
left pending; the measurement is limited to the selected mutations above.

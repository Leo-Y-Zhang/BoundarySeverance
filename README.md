# Boundary severance in road networks

A method for asking whether a political boundary bends a city's road network,
and whether that bend is the boundary's doing or the river it was drawn along.

The core idea is a **geometric permutation test**. Excess circuity across a
boundary is easy to find and easy to over-read, because city geometry is not
neutral. So instead of testing against 1.0, the same boundary curve is rigidly
re-placed within the same city — rotated about its own centroid, or displaced
perpendicular to itself — which preserves its shape, length and enclosed area
while destroying its historical position. The true placement is then scored
against that empirical null.

## Results

**Positive control — the UN Buffer Zone at Nicosia**, a boundary still closed
today. Crossing it costs about 46% additional network distance, and none of 20
displaced placebos comes near it (z ≈ +11). The method detects a live boundary
comfortably.

**The former inner Berlin Wall**, removed in 1989. Crossing it still costs about
1% more distance, and across 71 rotated placements of the same curve — every
5° around the city — not one severs Berlin as much as the position the Wall
actually occupied (p = 0.014).

The interesting part is the confound. Around 90% of trips crossing the inner
Wall also cross water, because the Wall was routed along the Spree and the
canals, so the obvious worry is that the river is doing the work. It is not:
removing water and rail crossings *raises* the effect to about 4%. Berlin is a
watery city, so the same-side comparison trips cross rivers too (71% of them). A
confound shared by both groups is not a rival explanation — it is attenuation,
and it was hiding the boundary rather than creating it.

Thirty-seven years on, a faint but measurable trace of the Wall survives in
Berlin's road network, roughly one part in fifty of the cost of a boundary that
is still shut.

## Running it

Requires Python 3 with `numpy` and `scipy`. Nothing else — no geospatial stack.

```
python fetch.py berlin hamburg     # download and cache road networks
python validate_wall.py            # geometry checks; must print ALL PASS
python run_master.py               # all Berlin specifications with nulls
python run_cyprus.py               # Nicosia positive control
python figures.py                  # figures
python make_paper.py               # render and build the PDF
```

Overpass responses are cached under `cache/`, so re-runs are offline and
deterministic. The first fetch downloads roughly 130 MB.

## Validation

No result is computed until the reconstructed geometry has been checked against
independent ground truth, and the pipeline halts if a check fails.

- The Wall ring assembled from OSM relation 9030 encloses 473.3 km² against West
  Berlin's actual 480 km², an error of 1.4%.
- All 18 landmark tests pass: 8 West Berlin locations inside the ring, 10 East
  Berlin and Brandenburg locations outside.
- All 7 Cyprus landmark tests pass either side of the buffer zone.
- The Nicosia road network is a single connected component, so measured detours
  are real routes through the crossing points rather than an artefact of a
  severed graph.

## Layout

| file | purpose |
|---|---|
| `osm.py` | Overpass client with on-disk caching, geometry helpers |
| `fetch.py` | study areas and network download |
| `graph.py` | routable sparse graph, largest connected component |
| `wall.py` | assembles OSM relation 9030 into a closed ring |
| `segments.py` | splits the ring into inner and outer boundary |
| `cyprus.py` | buffer-zone line, closed into a ring for side tests |
| `barriers.py` | rasterised water and rail, constant-time crossing queries |
| `severance.py` | the statistic, sampling design and bootstraps |
| `run_master.py` | all Berlin specifications, each with its own null |
| `run_cyprus.py` | Nicosia positive control |
| `localise.py` | where along the boundary the residual sits |
| `facts.py` | recomputes every descriptive number into `facts.json` |
| `make_paper.py` | injects all values into the manuscript and builds it |

## StoryMap

`make_storymap.py` generates a public-facing version of the same work for the
Royal Geographical Society's Young Geographer of the Year (Key Stage 5), whose
2026 theme is *From Source to Sea* and whose brief lists conflict among the
river themes. It writes `storymap.html`, a readable preview, and `storymap.md`,
the section-by-section text for pasting into ArcGIS StoryMaps. Its figures are
injected from the same result files as the paper.

## A note on the numbers

Nothing in the paper is transcribed. `facts.py` recomputes the descriptive
values, the experiments write their own result files, and `make_paper.py`
injects them into the LaTeX, failing loudly if any placeholder is left unfilled.
The text therefore cannot drift away from the analysis that produced it.

## Data

OpenStreetMap via the Overpass API, © OpenStreetMap contributors, available
under the Open Database Licence.

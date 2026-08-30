# Architecture

A straight line from OpenStreetMap to a manuscript, with a validation
gate early enough that nothing downstream can quietly depend on bad
geometry.

## Module map

| module | responsibility |
|---|---|
| `osm.py` | Overpass client with on-disk caching, geometry helpers |
| `fetch.py` | study areas and network download |
| `graph.py` | routable sparse graph, largest connected component |
| `wall.py` | assembles OSM relation 9030 into a closed ring |
| `segments.py` | splits the ring into inner and outer boundary |
| `cyprus.py` | buffer-zone line, closed into a ring for side tests |
| `barriers.py` | rasterised water and rail, constant-time queries |
| `severance.py` | the statistic, sampling design, bootstraps |
| `make_paper.py` | injects every value into the manuscript |
| `cli.py` | CLI |


## Why it is shaped this way

**Validation runs before measurement.** The assembled ring encloses
473.3 km2 against West Berlin's actual 480, and 18 landmarks must fall on
the correct sides. A reconstruction that fails those is not worth
measuring.

**The null is built by moving the boundary, not by assuming one.** City
geometry is not neutral, so 1.0 is the wrong reference point -- the
placebo placements average 0.983.

**Barriers are a raster, not a polyline comparison.** Testing a segment
against an occupancy grid is a constant-time lookup per sample rather
than a comparison against every waterway in the city.

## What would break it

- The Mauerweg is a proxy for the Wall: as a rideable path it deviates
  where the original strip is built over.
- OSM completeness varies sharply with development level, which limits
  generalisation rather than these results.
- Distance, not travel time. One-way restrictions and turn costs are
  ignored.


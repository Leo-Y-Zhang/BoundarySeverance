# Changelog

Notable changes to this project, in the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

The project has never been tagged for release, so there are no version headings
yet, only *Unreleased*. Back-filling release notes for work that shipped without
them would be writing history after the fact, which is the thing this
repository's documents are meant not to do.

## [Unreleased]

### Added

- **CLI** (`boundaryseverance validate|fetch|measure|paper|verify`), with the
  geometry ground-truth check as a first-class command because every other
  result depends on it.
- **Finer permutation null** at 71 placements, lowering the attainable p-value
  floor from 0.042 to 0.014. The true placement remained extremal: the highest
  of all 71 alternatives still falls below it.

### Notes

- The headline finding reversed during development. Controlling for water and
  rail was expected to explain the effect away; it strengthened it, because the
  same-side control trips cross the same rivers. A confound shared by treatment
  and control attenuates an effect rather than creating one.


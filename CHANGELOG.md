# Changelog

## [0.5.8] - 2026-06-18

- docs: add CITATION.cff for Zenodo DOI integration

## [0.5.7] - 2026-05-30

- Revised plugin icon

## [0.5.6] - 2026-05-26

- Maintenance release: compatibility validation for QGIS 3.40+/4 and packaging refresh.

## [0.5.5] - 2026-05-26

- Maintenance release: refreshed Plugin Hub package after QGIS 3 and QGIS 4 compatibility validation.

All notable changes to **PlanX Settlement Planning Toolset** are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · versioning: [SemVer](https://semver.org/).

## [0.5.3] - 2026-05-19

### Fixed
- **helper_generate_ramps** and **helper_generate_stairs**: multi-line input was silently skipped (`asPolyline()` on `MultiLineString` returns `[]` → feature dropped). Now takes the first part for direction/start point, matching the documented single-feature-per-input behavior.

## [0.5.2] - 2026

- Released the current local workflow updates, Step 3 footprint variants, parking-axis helpers, standardized Plugin Hub metadata, and refreshed the stable release package.

## [0.5.1]

- Renumbered the workflow as 3.1 FAR, 3.2 Detached, 3.3 Block, 3.4 Attached, 4.1 Macroform, 4.2 DynamicForm, 5 Data Check, and 6–9 remaining stages.
- Step 4.1 Macroform: `TEMPLATE_FILE` replaced by `TEMPLATE_LAYER` (open layer selector) + `SELECTED_ONLY` checkbox.
- Each Step 3.x variant now has a distinct icon.

## [0.5.0]

- Revised the coverage footprint workflow into separate detached, attached, block, and FAR generators with block-based grouping.
- Step 1 now stores block and parcel identifiers for downstream grouping logic.
- Added separate attached and block coverage algorithms and rebuilt FAR generation around block groups.

## [0.1.0]

- Initial 9-stage settlement plan production pipeline.

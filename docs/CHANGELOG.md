# Changelog

## v0.5.2 (2026-05-15)
- **Release refresh:** Local workflow updates are packaged for Plugin Hub with standardized author/email metadata and stable release flags.
- **Step 3 workflow:** Detached, attached, block, and FAR footprint variants are published with their dedicated icons and provider ordering.
- **Parking helpers:** Axis-layer and axis-based parking generation helpers are included in the released Processing provider.

## v0.5.0 (2026-04-11)
- **Block ID persistence:** Step 1 now carries `ada_id` and `parcel_id` derived identifiers into downstream workflow steps.
- **Separated Step 3 workflows:** Detached, attached, block, and FAR coverage footprint generation were split into dedicated algorithms.
- **Attached / block grouping:** Side-neighbor parcels within the same block are grouped for continuous attached layouts and paired/triple block footprints.
- **Block-based FAR revision:** FAR solving now works on block groups with min/max building area and inter-building spacing calculations.

## v0.4.0 (2026-04-11)
- **CoverageFootprint with layout type support:** Step 3 reads selectable `nizam` values (`A / B / BL`) and applies different setback logic for detached, attached, and block layouts.
- **New FAR footprint step:** `step_3_coverage_footprint_far.py` adds parametric footprint generation from FAR and maximum-height inputs.
- **Block-based placement rules:** FAR solving applies fixed approach distances around each block, floor-count-based side-yard logic, and minimum spacing between buildings.

## v0.3.0 (2026-04-04)
- **Strengthened ParcelFlux algorithm:** Added row-width asymmetry for independent north/south parcel spacing and refined minimum-area calculations.
- **Dynamic procedural macroform:** Removed template dependency and introduced a procedural massing engine with 12 urban parcel typologies such as I, L, U, and E forms with minimum wing depths above 7 m.
- **Smarter parking engine:** Added road-network input support, OBB-based alignment improvements, road-aware rotation, and parking entrance line generation.
- **QGIS 3.40 compatibility:** Stabilized hard-surface workflow issues caused by core API changes through inline buffer handling.
- **Bug fixes:** Resolved Urban Furniture SVG symbol-limit errors and increased supported capacities.

## v0.2.0 (2026-04-03)
- Integrated developer identity and PlanX Geospatial Advanced Tools branding into the interface.
- Updated buffer geometry methodology for QGIS API changes and improved OBB handling in the parking generator.

## v0.1.0 (2026-04-02)
- Initial 9-stage settlement plan production pipeline.
- Added the first ParcelFlux, FacadeDetector, and CoverageFootprint workflows.

# PlanX Settlement Planning Toolset

**A 9-stage parametric settlement plan generation pipeline for QGIS — part of the PlanX suite**

PlanX Settlement Planning Toolset automates the full production of a settlement plan. Starting from basic block subdivision, it runs through parcel generation, building footprint placement, parking layout design, and landscape generation — all in a sequential, parameter-driven pipeline.

---

## 9-Stage Workflow

| # | Tool | Description |
|---|---|---|
| 1 | **ParcelFlux** | Subdivides blocks into parcels with width variation and row asymmetry |
| 2 | **FacadeDetector** | Detects and classifies parcel facades (front / side / rear setbacks) |
| 3 | **CoverageFootprint** | Generates maximum buildable area using edge-based setbacks and floor area ratio (TAKS) |
| 3B | **Building Macroform** | Places basic building masses on parcels |
| 3C | **Dynamic Macroform** | Procedurally derives 12 realistic architectural form typologies (I, L, U, T, etc.) |
| 4 | **BuildingOptimizer** | Validates building-parcel fit and resolves geometric conflicts |
| 5 | **Hard Surface** | Calculates hard surface and pedestrian circulation areas |
| 6 | **ParkingGenerator** | Road-network-aware parametric parking engine (90° / 60° / 45° configurations) |
| 7 | **LandscapeGenerator** | Places trees and vegetation adapted to parcel geometry |
| 8 | **SettlementFinalizer** | Population projection, statistics summary, and reporting |

## Key Capabilities

- **Real-time Parcel Asymmetry** — ParcelFlux distributes widths with organic variation across opposing block rows
- **Procedural Architectural Forms** — 12 mass typologies with minimum 7 m wing depths, matched to parcel structure
- **Road-guided Parking** — Engine analyzes road network and connects parking entry lines to nearest road alignment
- **QGIS 3.40+ Compatible** — Core geometry engine updated for API revisions in recent LTR versions

## Installation

1. Download the latest `.zip` from [Releases](https://github.com/YusufEminoglu/PlanX-Settlement/releases).
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Activate **PlanX Settlement Planning Toolset** from the plugin list.
4. Find the tools under **Processing Toolbox → PlanX Settlement Planning Toolset**.

## Compatibility

| Requirement | Value |
|---|---|
| QGIS minimum | 3.28 |
| QGIS recommended | 3.40 LTR or 3.44 LTR |
| License | GPL-3.0 |
| Status | Experimental |

## Changelog

- **0.1.0** — Initial version: 9-stage settlement plan production pipeline

## Author

**Yusuf Eminoglu** — Dokuz Eylül University, Department of City and Regional Planning  
[GitHub](https://github.com/YusufEminoglu) | geospacephilo@gmail.com

Part of the **[PlanX](https://github.com/YusufEminoglu/PlanX)** urban planning plugin suite.

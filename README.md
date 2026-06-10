<div align="center">

<img src="icons/icon_main.svg" width="96" alt="PlanX Settlement Planning Toolset icon"/>

# PlanX Settlement Planning Toolset

**9-stage parametric settlement-plan pipeline for QGIS — blocks, parcels, building footprints, parking and landscape (Processing).**

[![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-93b023?logo=qgis&logoColor=white)](https://plugins.qgis.org/plugins/planx_yerlesim_plani_arac_seti/)
[![Version](https://img.shields.io/github/v/tag/YusufEminoglu/PlanX-Settlement?label=version&color=blue)](https://github.com/YusufEminoglu/PlanX-Settlement/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0-orange)](LICENSE)
[![QGIS Plugin Hub](https://img.shields.io/badge/QGIS%20Hub-install-589632?logo=qgis&logoColor=white)](https://plugins.qgis.org/plugins/planx_yerlesim_plani_arac_seti/)

</div>

---

## Why this toolset?

Producing a complete settlement plan by hand — subdividing blocks, placing footprints, fitting parking, adding landscape — takes days of repetitive geometry work. This toolset automates the full production line as a sequential, parameter-driven Processing pipeline: start from zoning blocks, end with a populated, reported settlement plan.

## ✨ Features

- **Real-time parcel asymmetry** — ParcelFlux distributes widths with organic variation across opposing block rows.
- **Four footprint strategies** — detached, attached, twin/triple block, and island-scale FAR-driven generation.
- **Procedural architectural forms** — 12 mass typologies (I, L, U, T, …) with minimum 7 m wing depths, matched to parcel structure.
- **Road-guided parking** — the engine analyzes the road network and connects parking entry lines to the nearest road alignment (90°/60°/45°).
- **Landscape & reporting** — vegetation adapted to parcel geometry, plus population projection and statistics summary.
- **QGIS 3.40+ LTR compatible** — core geometry engine updated for recent API revisions.

## 🚀 Installation

**From the QGIS Plugin Hub (recommended):** `Plugins → Manage and Install Plugins…` → search for **"PlanX Settlement"** → *Install*.

**From a release zip:** download the latest zip from [Releases](https://github.com/YusufEminoglu/PlanX-Settlement/releases) → `Plugins → Install from ZIP`.

Requires QGIS 3.28 or newer (3.40/3.44 LTR recommended). No external Python dependencies.

## 📖 Quick start

1. Install and activate the plugin — tools appear under **Processing Toolbox → PlanX Settlement Planning Toolset**.
2. Load a zoning block polygon layer.
3. Run **1 — ParcelFlux** to subdivide blocks into parcels.
4. Continue down the pipeline: facades → footprints → optimizer → parking → landscape → finalizer.

## ⚙️ The 9-stage workflow

| # | Tool | What it does |
|---|------|--------------|
| 1 | **ParcelFlux** | Subdivides blocks into parcels with width variation and row asymmetry |
| 2 | **FacadeDetector** | Detects and classifies parcel facades (front / side / rear setbacks) |
| 3A | **CoverageFootprint Detached** | Parcel footprints for detached layout using edge-based setbacks and TAKS |
| 3B | **CoverageFootprint Attached** | Attached-layout row footprints by grouping side-neighbor parcels in the same block |
| 3C | **CoverageFootprint Block** | Twin / triple block-layout footprints by grouping parcels with shared block IDs |
| 3D | **CoverageFootprint FAR** | Island-scale footprints from emsal and yençok values with fixed approach distances |
| 3B | **Building Macroform** | Places basic building masses on parcels |
| 3C | **Dynamic Macroform** | Procedurally derives 12 realistic architectural form typologies (I, L, U, T, …) |
| 4 | **BuildingOptimizer** | Validates building-parcel fit and resolves geometric conflicts |
| 5 | **Hard Surface** | Calculates hard surface and pedestrian circulation areas |
| 6 | **ParkingGenerator** | Road-network-aware parametric parking engine (90° / 60° / 45°) |
| 7 | **LandscapeGenerator** | Places trees and vegetation adapted to parcel geometry |
| 8 | **SettlementFinalizer** | Population projection, statistics summary, and reporting |

Full version history: [CHANGELOG.md](CHANGELOG.md)

## 🧩 Part of the PlanX ecosystem

This plugin is one of 15 open-source QGIS plugins for urban planning by the same author:

| Planning & analysis | CAD & production | 3D & visualization |
|---|---|---|
| [PlanX](https://github.com/YusufEminoglu/PlanX) — spatial-planning suite | [PlanX CAD Toolset](https://github.com/YusufEminoglu/PlanX-CAD) — drafting-grade CAD | [PlanX 3D City](https://github.com/YusufEminoglu/planx_3d_city) — Three.js city viewer |
| [GeoStats Lab](https://github.com/YusufEminoglu/planx_geostats) — spatial statistics | [EasyFillet](https://github.com/YusufEminoglu/EasyFillet) — tangent-arc fillet | [3D OSM Model](https://github.com/YusufEminoglu/osm_3d_model) — OSM → 3D city in browser |
| [Suitability Lab](https://github.com/YusufEminoglu/planx_suitability_lab) — raster MCDA | [Settlement Toolset](https://github.com/YusufEminoglu/PlanX-Settlement) — 9-stage settlement plans | [OSM Quick 3D](https://github.com/YusufEminoglu/osm_quick_3d) — OSM → native QGIS 3D |
| [DataCube Lab](https://github.com/YusufEminoglu/planx_datacube) — spatiotemporal cubes | [UIP Toolset](https://github.com/YusufEminoglu/PlanX-UIP) — Turkish master-plan automation | [Urban Procedural 3D](https://github.com/YusufEminoglu/planx_urban_procedural_3d) — parametric zoning lab |
| [Urban Resilience](https://github.com/YusufEminoglu/planx_urban_resilience) — 28 resilience tools | [ParcelFlux](https://github.com/YusufEminoglu/parcelflux) — parcel subdivision | [CartoLab](https://github.com/YusufEminoglu/planx_cartolab) — publication cartography |

## 📜 License & author

GPL-3.0 © [Yusuf Eminoğlu](https://github.com/YusufEminoglu) — Dokuz Eylül University, Department of City and Regional Planning. Bug reports and feature requests welcome in [Issues](https://github.com/YusufEminoglu/PlanX-Settlement/issues).

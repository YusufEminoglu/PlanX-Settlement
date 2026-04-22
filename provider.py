# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Processing Provider — 9 aşamalı sıralı iş akışı algoritmaları

Algoritma yükleme mekanizması planx_uip_arac_seti ile aynı pattern:
importlib ile her algorithm dosyasını yükler ve SVG ikonlarını atar.
"""

import os
import importlib.util
import sys

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider


def _load_module(module_name, file_path):
    """Bir Python dosyasını modül olarak güvenli şekilde yükler."""
    if not os.path.exists(file_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[planX-Yerleşim] HATA: {os.path.basename(file_path)} yüklenemedi → {e}")
        return None


# ── Algoritma tanımları: (dosya_adı, sınıf_adı, ikon_dosyası) ──────────────
_ALGORITHMS = [
    ("step_1_parcel_flux", "ParcelFluxAlgorithm", "icon_step_1.svg"),
    ("step_2_facade_detector", "FacadeDetectorAlgorithm", "icon_step_2.svg"),
    ("step_3_coverage_footprint", "CoverageFootprintAlgorithm", "icon_step_3.svg"),
    ("step_3b_building_macroform", "BuildingMacroformAlgorithm", "icon_step_3b.svg"),
    ("step_3c_dynamic_macroform", "DynamicMacroformAlgorithm", "icon_step_3b.svg"),
    ("step_4_building_optimizer", "BuildingOptimizerAlgorithm", "icon_step_4.svg"),
    ("step_5_hard_surface", "HardSurfaceAlgorithm", "icon_step_5.svg"),
    ("step_6_parking_generator", "ParkingGeneratorAlgorithm", "icon_step_6.svg"),
    ("step_7_landscape_generator", "LandscapeGeneratorAlgorithm", "icon_step_7.svg"),
    ("step_8_settlement_finalizer", "SettlementFinalizerAlgorithm", "icon_step_8.svg"),
    ("urban_furniture_creator", "UrbanFurnitureAlgorithm", "icon_urban_furniture.svg"),
    ("helper_generate_stairs", "GenerateStairsAlgorithm", "icon_helper_stair.svg"),
    ("helper_generate_ramps", "GenerateRampsAlgorithm", "icon_helper_ramp.svg"),
    (
        "helper_pedestrian_crossing",
        "PedestrianCrossingAlgorithm",
        "icon_helper_pedestrian.svg",
    ),
]


class PlanXYerlesimProvider(QgsProcessingProvider):
    """Processing provider that loads all settlement plan algorithms."""

    def __init__(self):
        super().__init__()

    def loadAlgorithms(self):
        plugin_dir = os.path.dirname(__file__)
        alg_dir = os.path.join(plugin_dir, "algorithms")
        icon_dir = os.path.join(plugin_dir, "icons")

        for file_stem, class_name, icon_file in _ALGORITHMS:
            file_path = os.path.join(alg_dir, f"{file_stem}.py")
            mod = _load_module(f"planx_yerlesim_{file_stem}", file_path)

            if mod is None or not hasattr(mod, class_name):
                print(
                    f"[planX-Yerleşim] Atlandı: {file_stem} ({class_name} bulunamadı)"
                )
                continue

            # Dinamik olarak ikon atanmış alt sınıf oluştur
            base_cls = getattr(mod, class_name)
            icon_path = os.path.join(icon_dir, icon_file)

            # Closure ile icon_path yakala
            def _make_cls(base, ipath):
                class _Wrapped(base):
                    def icon(self):
                        return QIcon(ipath) if os.path.exists(ipath) else QIcon()

                return _Wrapped

            wrapped = _make_cls(base_cls, icon_path)
            try:
                self.addAlgorithm(wrapped())
            except Exception as e:
                print(f"[planX-Yerleşim] Algoritma eklenemedi: {class_name} → {e}")

    # ── Provider kimliği ─────────────────────────────────────────────────
    def id(self):
        return "planx_yerlesim"

    def name(self):
        return "planX — Yerleşim Planı Araç Seti"

    def longName(self):
        return "planX — Yerleşim Planı Araç Seti (Ada→Parsel→Bina→Peyzaj)"

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon_main.svg")
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

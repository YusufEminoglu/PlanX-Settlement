# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
QGIS Processing Plugin

Ada → Parsel → Bina (Makroform) → Sert Zemin → Otopark → Peyzaj
sıralı iş akışı ile yerleşim planı üretimi.

Author: Arş. Gör. Yusuf Eminoğlu
"""


def classFactory(iface):
    from .main_plugin import PlanXYerlesimPlugin

    return PlanXYerlesimPlugin(iface)

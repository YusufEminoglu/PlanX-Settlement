# -*- coding: utf-8 -*-
"""
planX — Hard Surface Engine
Sert zemin (yürüme alanı) üretim motoru.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
from qgis.core import QgsGeometry


def generate_hard_surface(building_geom, parcel_geom, buffer_distance=3.0):
    """
    Sert zemin hesaplama: buffer(bina, dist) ∩ parsel − bina

    Args:
        building_geom: Bina taban alanı poligonu
        parcel_geom: Parsel sınır poligonu
        buffer_distance: Buffer mesafesi (m)

    Returns:
        QgsGeometry: Sert zemin poligonu
    """
    if building_geom.isEmpty() or parcel_geom.isEmpty():
        return QgsGeometry()

    try:
        # Yalnızca distance — QGIS 3.40 uyumlu en güvenli form
        buffered = building_geom.buffer(float(buffer_distance), 16)
    except TypeError:
        # Fallback: tek argüman
        try:
            buffered = building_geom.buffer(float(buffer_distance), int(16))
        except TypeError:
            return QgsGeometry()

    if buffered is None or buffered.isEmpty():
        return QgsGeometry()

    clipped = buffered.intersection(parcel_geom)
    if clipped is None or clipped.isEmpty():
        return QgsGeometry()

    hard_surface = clipped.difference(building_geom)
    if hard_surface is None or hard_surface.isEmpty():
        return QgsGeometry()
    return hard_surface


def calculate_hard_surface_ratio(hard_surface_geom, parcel_geom):
    """Sert zemin / parsel oranı."""
    if hard_surface_geom.isEmpty() or parcel_geom.isEmpty():
        return 0.0
    return hard_surface_geom.area() / parcel_geom.area()

# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Setback Calculator — Kenar bazlı yapı yaklaşma sınırı hesaplama motoru

M-value tabanlı setback sistemi: Her parsel kenarı için cephe tipine göre
farklı setback mesafesi uygular ve yapılaşabilir alan (buildable area) hesaplar.
"""

import math
from qgis.core import QgsGeometry, QgsPointXY

from .geometry_engine import get_polygon_edges, negative_buffer_per_edge


def calculate_edge_setbacks(
    facade_classification, setback_front, setback_side, setback_back
):
    """
    Cephe sınıflandırmasından kenar bazlı setback listesi üretir.

    Args:
        facade_classification: dict — classify_all_edges() çıktısı
        setback_front: float — ön bahçe mesafesi (m)
        setback_side: float — yan bahçe mesafesi (m)
        setback_back: float — arka bahçe mesafesi (m)

    Returns:
        dict: { edge_index: setback_value }
    """
    setbacks = {}

    for idx in facade_classification.get("front", []):
        setbacks[idx] = setback_front

    for idx in facade_classification.get("side", []):
        setbacks[idx] = setback_side

    for idx in facade_classification.get("back", []):
        setbacks[idx] = setback_back

    return setbacks


def compute_buildable_area(
    parcel_geom, facade_classification, setback_front, setback_side, setback_back
):
    """
    Parsel geometrisi ve cephe bilgilerinden yapılaşabilir alanı hesaplar.

    Her kenar için cephe tipine göre farklı setback uygulayarak
    kenar bazlı negatif buffer yapar.

    Args:
        parcel_geom: QgsGeometry — parsel poligonu
        facade_classification: dict — classify_all_edges() çıktısı
        setback_front: float — ön bahçe mesafesi (m)
        setback_side: float — yan bahçe mesafesi (m)
        setback_back: float — arka bahçe mesafesi (m)

    Returns:
        QgsGeometry: Yapılaşabilir alan poligonu
    """
    edges = get_polygon_edges(parcel_geom)
    n_edges = len(edges)

    # Her kenar için setback değeri
    edge_setback_map = calculate_edge_setbacks(
        facade_classification, setback_front, setback_side, setback_back
    )

    # Sıralı setback listesi
    edge_setbacks = []
    for i in range(n_edges):
        if i in edge_setback_map:
            edge_setbacks.append(edge_setback_map[i])
        else:
            # Sınıflandırılmamış kenar → yan bahçe olarak kabul et
            edge_setbacks.append(setback_side)

    return negative_buffer_per_edge(parcel_geom, edge_setbacks)


def apply_taks_constraint(buildable_geom, parcel_area, taks_ratio):
    """
    Yapılaşabilir alana TAKS kısıtı uygular.

    Eğer buildable_area > parcel_area × TAKS ise,
    buildable_area centroid etrafında küçültülür.

    Args:
        buildable_geom: QgsGeometry — yapılaşabilir alan
        parcel_area: float — parsel toplam alanı (m²)
        taks_ratio: float — Taban Alanı Katsayısı (ör. 0.40)

    Returns:
        QgsGeometry: TAKS sınırına uygun bina footprint
    """
    if buildable_geom.isEmpty():
        return buildable_geom

    max_building_area = parcel_area * taks_ratio
    current_area = buildable_geom.area()

    if current_area <= max_building_area:
        return buildable_geom

    # Alanı küçültmek için ölçek faktörü
    scale_factor = math.sqrt(max_building_area / current_area)
    centroid = buildable_geom.centroid().asPoint()

    if buildable_geom.isMultipart():
        polys = buildable_geom.asMultiPolygon()
        scaled = []
        for poly in polys:
            s_poly = []
            for ring in poly:
                s_ring = [
                    QgsPointXY(
                        centroid.x() + scale_factor * (pt.x() - centroid.x()),
                        centroid.y() + scale_factor * (pt.y() - centroid.y()),
                    )
                    for pt in ring
                ]
                s_poly.append(s_ring)
            scaled.append(s_poly)
        return QgsGeometry.fromMultiPolygonXY(scaled)
    else:
        poly = buildable_geom.asPolygon()
        s_poly = []
        for ring in poly:
            s_ring = [
                QgsPointXY(
                    centroid.x() + scale_factor * (pt.x() - centroid.x()),
                    centroid.y() + scale_factor * (pt.y() - centroid.y()),
                )
                for pt in ring
            ]
            s_poly.append(s_ring)
        return QgsGeometry.fromPolygonXY(s_poly)


def validate_setbacks(
    building_geom,
    parcel_geom,
    facade_classification,
    setback_front,
    setback_side,
    setback_back,
    tolerance=0.1,
):
    """
    Bina geometrisinin setback kurallarına uygunluğunu doğrular.

    Returns:
        dict: {
            'valid': bool,
            'violations': list[dict] — ihlal detayları
        }
    """
    edges = get_polygon_edges(parcel_geom)
    edge_setback_map = calculate_edge_setbacks(
        facade_classification, setback_front, setback_side, setback_back
    )

    violations = []

    for i, (p1, p2) in enumerate(edges):
        required = edge_setback_map.get(i, setback_side)
        edge_geom = QgsGeometry.fromPolylineXY([p1, p2])

        actual_dist = building_geom.distance(edge_geom)
        if actual_dist < required - tolerance:
            violations.append(
                {
                    "edge_index": i,
                    "required": required,
                    "actual": round(actual_dist, 2),
                    "deficit": round(required - actual_dist, 2),
                }
            )

    return {"valid": len(violations) == 0, "violations": violations}

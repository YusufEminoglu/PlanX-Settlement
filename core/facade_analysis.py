# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Facade Analysis — Network tabanlı cephe analiz motoru

Parsel kenarlarını yol ağına olan uzaklıklarına göre sınıflandırır:
- Ön cephe: Yola en yakın kenarlar
- Yan cephe: Komşu parsele dokunan kenarlar
- Arka cephe: Yoldan en uzak kenarlar

Planlı Alanlar İmar Yönetmeliği kuralları uygulanır.
"""

import math
from qgis.core import QgsGeometry, QgsPointXY

from .geometry_engine import (
    get_polygon_edges,
    edge_midpoint,
    edge_direction_angle,
    compass_direction,
)


def detect_front_facades(parcel_geom, road_layer, threshold=None):
    """
    Parsel kenarlarından hangilerinin ön cephe (yola bakan) olduğunu tespit eder.

    Algoritma:
    1. Parsel kenarlarını (edges) çıkar
    2. Her kenarın orta noktasından (midpoint) en yakın yola shortest line hesapla
    3. threshold'dan kısa olan kenarlar "ön cephe"

    Args:
        parcel_geom: QgsGeometry — parsel poligonu
        road_layer: QgsVectorLayer — yol çizgi katmanı
        threshold: float|None — mesafe eşiği (None ise otomatik hesapla)

    Returns:
        list[int]: Ön cephe kenar indeksleri (0-tabanlı)
    """
    edges = get_polygon_edges(parcel_geom)
    if not edges:
        return []

    # Otomatik eşik: parsel derinliğinin %60'ı
    if threshold is None:
        obb = parcel_geom.orientedMinimumBoundingBox()
        if obb and len(obb) >= 5:
            short_side = min(obb[3], obb[4])
            threshold = short_side * 0.6
        else:
            threshold = math.sqrt(parcel_geom.area()) * 0.5

    # Her kenarın orta noktası → yola olan mesafe
    front_indices = []
    edge_distances = []

    for i, (p1, p2) in enumerate(edges):
        mid = edge_midpoint(p1, p2)
        mid_geom = QgsGeometry.fromPointXY(mid)

        # En yakın yol feature'ına mesafe
        min_dist = float("inf")
        for road_feat in road_layer.getFeatures():
            road_geom = road_feat.geometry()
            dist = mid_geom.distance(road_geom)
            if dist < min_dist:
                min_dist = dist

        edge_distances.append(min_dist)

        if min_dist < threshold:
            front_indices.append(i)

    return front_indices


def classify_all_edges(parcel_geom, front_indices, parcel_layer=None, parcel_fid=None):
    """
    Parsel kenarlarını ön/yan/arka olarak sınıflandırır.

    Kurallar:
    - front_indices → "front" (ön cephe — yola bakan)
    - Komşu parsele dokunan kenarlar → "side" (yan cephe)
    - Geri kalanlar → "back" (arka cephe)

    Planlı Alanlar İmar Yönetmeliği:
    - 2 ön cephe (köşe parsel) → 0 yan, 2 arka
    - arka bahçe = yan bahçe kuralı

    Returns:
        dict: {
            'front': list[int],  # ön cephe kenar indeksleri
            'side': list[int],   # yan cephe kenar indeksleri
            'back': list[int],   # arka cephe kenar indeksleri
            'facade_count': int, # ön cephe sayısı
            'is_corner': bool,   # köşe parseli mi
            'front_direction': str  # ön cephe yönü
        }
    """
    edges = get_polygon_edges(parcel_geom)
    n_edges = len(edges)
    n_front = len(front_indices)

    # Basit sınıflandırma
    all_indices = set(range(n_edges))
    front_set = set(front_indices)
    remaining = all_indices - front_set

    # Köşe parseli tespiti
    is_corner = n_front >= 2

    if is_corner:
        # Köşe parsellerinde yan bahçe yok, kalan her şey arka
        side_indices = []
        back_indices = sorted(remaining)
    else:
        # Normal parsellerde ön cephe dışındakiler:
        # ön cephenin karşısındaki kenar → arka
        # diğerleri → yan
        if front_indices:
            front_midpoints = [edge_midpoint(*edges[i]) for i in front_indices]
            avg_front = QgsPointXY(
                sum(m.x() for m in front_midpoints) / len(front_midpoints),
                sum(m.y() for m in front_midpoints) / len(front_midpoints),
            )

            # Ön cephe ortalama noktasından en uzak kenar = arka cephe
            max_dist = 0
            back_idx = None
            for idx in remaining:
                mid = edge_midpoint(*edges[idx])
                dist = avg_front.distance(mid)
                if dist > max_dist:
                    max_dist = dist
                    back_idx = idx

            back_indices = [back_idx] if back_idx is not None else []
            side_indices = sorted(remaining - set(back_indices))
        else:
            side_indices = []
            back_indices = sorted(remaining)

    # Ön cephe yönü
    if front_indices:
        directions = []
        for idx in front_indices:
            p1, p2 = edges[idx]
            # Kenarın dışa bakan yönü (kenar normal)
            angle = edge_direction_angle(p1, p2)
            # Normal yön = kenar yönüne dik
            normal_angle = (angle + 90) % 360
            directions.append(compass_direction(normal_angle))

        if len(set(directions)) == 1:
            front_direction = directions[0]
        else:
            front_direction = "coklu"
    else:
        front_direction = "belirsiz"

    return {
        "front": sorted(front_indices),
        "side": side_indices,
        "back": back_indices,
        "facade_count": n_front,
        "is_corner": is_corner,
        "front_direction": front_direction,
    }

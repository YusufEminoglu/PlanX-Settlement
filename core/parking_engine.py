# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Parking Engine — Parametrik otopark düzeni hesaplama motoru

Poligon alanları içinde stall grid (2.5×5m) + aisle (6m) düzeni üretir.
Desteklenen açılar: 90°, 60°, 45°.
"""

import math
from qgis.core import QgsGeometry, QgsPointXY


# ── Standart otopark boyutları ──────────────────────────────────────────
PARKING_PRESETS = {
    90: {"stall_width": 2.5, "stall_depth": 5.0, "aisle_width": 6.0},
    60: {"stall_width": 2.5, "stall_depth": 5.5, "aisle_width": 4.5},
    45: {"stall_width": 2.5, "stall_depth": 6.0, "aisle_width": 3.6},
}


def compute_parking_axis(polygon_geom):
    """
    Poligonun ana eksenini (uzun kenarın yönü) hesaplar.

    Returns:
        dict: {
            'angle': float (radyan),
            'angle_deg': float (derece),
            'length': float (uzun kenar),
            'width': float (kısa kenar),
            'center': QgsPointXY,
            'obb_geom': QgsGeometry
        }
    """
    obb = polygon_geom.orientedMinimumBoundingBox()
    if not obb or len(obb) < 5:
        bbox = polygon_geom.boundingBox()
        return {
            "angle": 0.0,
            "angle_deg": 0.0,
            "length": bbox.width(),
            "width": bbox.height(),
            "center": QgsPointXY(bbox.center()),
            "obb_geom": polygon_geom,
        }

    obb_geom, area, angle, width, height = obb
    length = max(width, height)
    short = min(width, height)

    return {
        "angle": math.radians(angle),
        "angle_deg": angle,
        "length": length,
        "width": short,
        "center": obb_geom.centroid().asPoint(),
        "obb_geom": obb_geom,
    }


def _create_stall_rect(cx, cy, stall_w, stall_d, rotation_rad):
    """Tek bir otopark stall dikdörtgeni oluşturur (merkez tabanlı)."""
    hw = stall_w / 2.0
    hd = stall_d / 2.0

    # Döndürülmemiş köşeler (merkez orijin)
    corners = [
        (-hw, -hd),
        (hw, -hd),
        (hw, hd),
        (-hw, hd),
    ]

    cos_a = math.cos(rotation_rad)
    sin_a = math.sin(rotation_rad)

    rotated = []
    for x, y in corners:
        rx = x * cos_a - y * sin_a + cx
        ry = x * sin_a + y * cos_a + cy
        rotated.append(QgsPointXY(rx, ry))

    rotated.append(rotated[0])  # Kapat
    return QgsGeometry.fromPolygonXY([rotated])


def generate_parking_layout(
    polygon_geom,
    stall_width=2.5,
    stall_depth=5.0,
    aisle_width=6.0,
    parking_angle=90,
    stall_gap=0.1,
    edge_margin=0.5,
):
    """
    Poligon içinde parametrik otopark stall düzeni üretir.

    Algoritma:
    1. Poligonun OBB'sini ve ana eksenini hesapla
    2. Modül genişliği: stall_depth × 2 + aisle_width (çift sıra)
    3. Ana eksen boyunca stall_width aralıklarla doldur
    4. Stall'ı parking_angle'a göre döndür
    5. Poligon dışına taşanları kırp/sil

    Args:
        polygon_geom: QgsGeometry — otopark alanı poligonu
        stall_width: float — stall genişliği (m)
        stall_depth: float — stall derinliği (m)
        aisle_width: float — araç yolu genişliği (m)
        parking_angle: int — 90, 60, veya 45 derece
        stall_gap: float — stall arası boşluk (m)
        edge_margin: float — poligon kenarından minimum mesafe (m)

    Returns:
        dict: {
            'stalls': list[QgsGeometry],  # otopark yeri poligonları
            'aisles': list[QgsGeometry],  # araç yolu çizgileri
            'total_stalls': int,
            'efficiency': float  # stall_alan / toplam_alan
        }
    """
    # Edge margin uygula
    if edge_margin > 0:
        working_geom = polygon_geom.buffer(-edge_margin, 8)
        if working_geom.isEmpty():
            return {"stalls": [], "aisles": [], "total_stalls": 0, "efficiency": 0}
    else:
        working_geom = polygon_geom

    # Ana eksen bilgileri
    axis = compute_parking_axis(working_geom)
    rotation = axis["angle"]

    # Parking angle → stall döndürme
    parking_rad = math.radians(parking_angle)

    # Modül boyutları
    # 1 modül = stall_sırası + aisle + stall_sırası
    module_width = 2 * stall_depth + aisle_width

    # OBB'nin uzun ve kısa kenarları
    long_side = axis["length"]
    short_side = axis["width"]
    center = axis["center"]

    # Kaç modül sığar (kısa kenar boyunca)
    n_modules = int(short_side / module_width)
    if n_modules < 1:
        # Tek sıra dene
        n_modules = 0
        single_row = True
    else:
        single_row = False

    # Kaç stall sığar (uzun kenar boyunca)
    effective_stall_width = stall_width + stall_gap
    n_stalls_per_row = int(long_side / effective_stall_width)

    stalls = []
    aisle_lines = []

    # Uzun kenar yönünde birim vektör
    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    # Kısa kenar yönünde (perpendicular) birim vektör
    cos_rp = math.cos(rotation + math.pi / 2)
    sin_rp = math.sin(rotation + math.pi / 2)

    # Başlangıç pozisyonu: merkezden hesapla
    total_module_width = n_modules * module_width if n_modules > 0 else stall_depth
    start_offset = -total_module_width / 2.0

    for m in range(max(1, n_modules)):
        # Modül merkezinin pozisyonu (kısa kenar boyunca)
        if single_row:
            module_center_offset = 0
        else:
            module_center_offset = start_offset + m * module_width + module_width / 2.0

        mcx = center.x() + module_center_offset * cos_rp
        mcy = center.y() + module_center_offset * sin_rp

        # İki sıra stall + ortada aisle
        for row in range(2 if not single_row else 1):
            if row == 0:
                row_offset = -(aisle_width / 2.0 + stall_depth / 2.0)
            else:
                row_offset = aisle_width / 2.0 + stall_depth / 2.0

            row_cx = mcx + row_offset * cos_rp
            row_cy = mcy + row_offset * sin_rp

            # Stall'lar uzun kenar boyunca
            start_stall = -long_side / 2.0 + effective_stall_width / 2.0

            for s in range(n_stalls_per_row):
                stall_along = start_stall + s * effective_stall_width
                sx = row_cx + stall_along * cos_r
                sy = row_cy + stall_along * sin_r

                stall_geom = _create_stall_rect(
                    sx,
                    sy,
                    stall_width,
                    stall_depth,
                    rotation
                    + (math.pi / 2 - parking_rad if parking_angle != 90 else 0),
                )

                # Poligon içinde mi?
                if working_geom.contains(stall_geom):
                    stalls.append(stall_geom)
                else:
                    intersection = stall_geom.intersection(working_geom)
                    # En az %80 alanı kalıyorsa kabul et
                    if (
                        not intersection.isEmpty()
                        and intersection.area() > stall_geom.area() * 0.8
                    ):
                        stalls.append(stall_geom)

        # Aisle center line
        aisle_start = QgsPointXY(
            mcx - (long_side / 2.0) * cos_r, mcy - (long_side / 2.0) * sin_r
        )
        aisle_end = QgsPointXY(
            mcx + (long_side / 2.0) * cos_r, mcy + (long_side / 2.0) * sin_r
        )
        aisle_line = QgsGeometry.fromPolylineXY([aisle_start, aisle_end])
        aisle_clipped = aisle_line.intersection(working_geom)
        if not aisle_clipped.isEmpty():
            aisle_lines.append(aisle_clipped)

    total_stall_area = sum(s.area() for s in stalls)
    total_area = polygon_geom.area()
    efficiency = total_stall_area / total_area if total_area > 0 else 0

    return {
        "stalls": stalls,
        "aisles": aisle_lines,
        "total_stalls": len(stalls),
        "efficiency": round(efficiency, 3),
    }

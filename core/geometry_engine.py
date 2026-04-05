# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Geometry Engine — Ortak geometri yardımcı fonksiyonları

Tüm algoritmalar ve motorlar tarafından kullanılan temel geometri işlemleri.
"""

import math
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsLineString, QgsWkbTypes,
    QgsRectangle, QgsVector
)


def get_polygon_edges(geom):
    """
    Poligon geometrisinin kenar segmentlerini döner.

    Returns:
        list[tuple[QgsPointXY, QgsPointXY]]: Kenar başlangıç-bitiş noktaları
    """
    if geom.isMultipart():
        polygons = geom.asMultiPolygon()
    else:
        polygons = [geom.asPolygon()]

    edges = []
    for polygon in polygons:
        ring = polygon[0]  # Dış halka
        for i in range(len(ring) - 1):
            edges.append((QgsPointXY(ring[i]), QgsPointXY(ring[i + 1])))
    return edges


def edge_length(p1, p2):
    """İki nokta arasındaki mesafe."""
    return p1.distance(p2)


def edge_midpoint(p1, p2):
    """İki nokta arasındaki orta nokta."""
    return QgsPointXY((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)


def edge_direction_angle(p1, p2):
    """
    İki nokta arasındaki yön açısı (derece, 0=Kuzey, saat yönünde).

    Returns:
        float: 0-360 derece arası açı
    """
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    angle_rad = math.atan2(dx, dy)  # Kuzey referanslı
    angle_deg = math.degrees(angle_rad)
    return angle_deg % 360


def compass_direction(angle):
    """
    Derece cinsinden açıyı pusula yönüne çevirir.

    Args:
        angle: 0-360 arası derece (0=N, 90=E)
    Returns:
        str: "N", "NE", "E", "SE", "S", "SW", "W", "NW"
    """
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(angle / 45) % 8
    return dirs[idx]


def edge_normal_outward(p1, p2, polygon_centroid):
    """
    Kenar için dışa bakan normal birim vektör hesaplar.

    Args:
        p1, p2: Kenar uç noktaları
        polygon_centroid: Poligon ağırlık merkezi
    Returns:
        tuple[float, float]: (nx, ny) birim normal vektör
    """
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return (0.0, 0.0)

    # İki olası normal
    n1 = (-dy / length, dx / length)
    n2 = (dy / length, -dx / length)

    # Orta noktadan centroid'e olan yön ile karşılaştır
    mid = edge_midpoint(p1, p2)
    to_center_x = polygon_centroid.x() - mid.x()
    to_center_y = polygon_centroid.y() - mid.y()

    # Centroid'den uzaklaşan normal dışa bakar
    dot1 = n1[0] * to_center_x + n1[1] * to_center_y
    if dot1 < 0:
        return n1  # n1 dışa bakıyor
    else:
        return n2  # n2 dışa bakıyor


def negative_buffer_per_edge(geom, edge_setbacks):
    """
    Her kenar için farklı setback değeri uygulayarak yapılaşabilir alan hesaplar.

    Mantık: Her kenar için, kenardan içe doğru setback kadar düzlem oluştur.
    Tüm düzlemlerin kesişimi = yapılaşabilir alan.

    Args:
        geom: QgsGeometry (polygon)
        edge_setbacks: list[float] — her kenar için setback mesafesi

    Returns:
        QgsGeometry: Yapılaşabilir alan poligonu (veya boş)
    """
    edges = get_polygon_edges(geom)
    if len(edges) != len(edge_setbacks):
        # Fallback: standart negatif buffer
        avg_setback = sum(edge_setbacks) / len(edge_setbacks) if edge_setbacks else 0
        return geom.buffer(-avg_setback, 8)

    centroid = geom.centroid().asPoint()
    result = geom

    for (p1, p2), setback in zip(edges, edge_setbacks):
        if setback <= 0:
            continue

        # Kenarın dışa bakan normal vektörü
        nx, ny = edge_normal_outward(p1, p2, centroid)

        # Kenarı içe doğru setback kadar kaydır (normal yönünün tersi)
        offset_p1 = QgsPointXY(p1.x() - nx * setback, p1.y() - ny * setback)
        offset_p2 = QgsPointXY(p2.x() - nx * setback, p2.y() - ny * setback)

        # Bu kaydırılmış kenardan oluşan yarı-düzlem (halfplane)
        # Yeterince büyük dikdörtgen oluştur
        extend = 10000  # Büyük genişletme mesafesi
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length < 1e-12:
            continue
        ux, uy = dx / length, dy / length

        # Yarı-düzlem poligonu: kaydırılmış kenar + içe doğru genişletme
        hp = [
            QgsPointXY(offset_p1.x() - ux * extend, offset_p1.y() - uy * extend),
            QgsPointXY(offset_p2.x() + ux * extend, offset_p2.y() + uy * extend),
            QgsPointXY(offset_p2.x() + ux * extend - nx * extend,
                        offset_p2.y() + uy * extend - ny * extend),
            QgsPointXY(offset_p1.x() - ux * extend - nx * extend,
                        offset_p1.y() - uy * extend - ny * extend),
        ]
        halfplane = QgsGeometry.fromPolygonXY([hp])
        result = result.intersection(halfplane)

        if result.isEmpty():
            return QgsGeometry()

    return result


def oriented_minimum_bounding_box(geom):
    """
    Poligonun Oriented Minimum Bounding Box bilgilerini döner.

    Returns:
        dict: {
            'geometry': QgsGeometry,
            'width': float,
            'height': float,
            'angle': float (derece),
            'center': QgsPointXY
        }
    """
    obb = geom.orientedMinimumBoundingBox()
    # obb -> (QgsGeometry, area, angle, width, height)
    if obb and len(obb) >= 5:
        return {
            'geometry': obb[0],
            'area': obb[1],
            'angle': obb[2],
            'width': obb[3],
            'height': obb[4],
            'center': obb[0].centroid().asPoint() if not obb[0].isEmpty() else None
        }
    return None


def polygon_aspect_ratio(geom):
    """Poligonun en/boy oranını hesaplar (OBB kullanarak)."""
    obb = oriented_minimum_bounding_box(geom)
    if obb and obb['width'] > 0 and obb['height'] > 0:
        w, h = sorted([obb['width'], obb['height']])
        return h / w  # Her zaman >= 1
    return 1.0


def polygon_compactness(geom):
    """
    Poligonun kompaktlık değerini hesaplar.
    1.0 = mükemmel daire, daha düşük = daha karmaşık form.
    Formula: 4π × area / perimeter²
    """
    area = geom.area()
    perimeter = geom.length()
    if perimeter <= 0:
        return 0.0
    return (4.0 * math.pi * area) / (perimeter * perimeter)


def scale_geometry_to_area(geom, target_area):
    """
    Geometriyi hedef alana göre centroid etrafında ölçekler.
    Orijinal geometriyi değiştirmez, yeni geometri döner.
    """
    current_area = geom.area()
    if current_area <= 0:
        return geom

    scale_factor = math.sqrt(target_area / current_area)
    centroid = geom.centroid().asPoint()

    if geom.isMultipart():
        polys = geom.asMultiPolygon()
        scaled = []
        for poly in polys:
            scaled_poly = []
            for ring in poly:
                scaled_ring = [
                    QgsPointXY(
                        centroid.x() + scale_factor * (pt.x() - centroid.x()),
                        centroid.y() + scale_factor * (pt.y() - centroid.y())
                    ) for pt in ring
                ]
                scaled_poly.append(scaled_ring)
            scaled.append(scaled_poly)
        return QgsGeometry.fromMultiPolygonXY(scaled)
    else:
        poly = geom.asPolygon()
        scaled_poly = []
        for ring in poly:
            scaled_ring = [
                QgsPointXY(
                    centroid.x() + scale_factor * (pt.x() - centroid.x()),
                    centroid.y() + scale_factor * (pt.y() - centroid.y())
                ) for pt in ring
            ]
            scaled_poly.append(scaled_ring)
        return QgsGeometry.fromPolygonXY(scaled_poly)


def rotate_geometry(geom, angle_deg, center=None):
    """
    Geometriyi bir merkez etrafında döndürür.

    Args:
        geom: QgsGeometry
        angle_deg: Dönüş açısı (derece, saat yönü)
        center: QgsPointXY — dönüş merkezi (None ise centroid)
    Returns:
        QgsGeometry
    """
    rotated = QgsGeometry(geom)
    if center is None:
        center = geom.centroid().asPoint()
    rotated.rotate(angle_deg, center)
    return rotated


def translate_geometry(geom, dx, dy):
    """Geometriyi (dx, dy) kadar öteleme yapar."""
    translated = QgsGeometry(geom)
    translated.translate(dx, dy)
    return translated

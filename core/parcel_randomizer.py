# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Parcel Randomizer — Fishbone-style organik parsel sınır offset motoru

Parsel bölme çizgilerinde balık kılçığı benzeri organik kayma sağlar.
Sol ve sağ taraftaki bölme çizgileri birbirinden bağımsız offset alır.
"""

import random
import math
from qgis.core import QgsGeometry, QgsPointXY


def apply_fishbone_offset(
    perpendicular_points, center_line_geom, randomness_pct, lot_width, seed=None
):
    """
    Perpendicular bölme noktalarına fishbone offset uygular.

    Adayı enden ikiye ayıran orta çizgi üzerindeki bölme noktaları,
    sağa ve sola bağımsız olarak küçük bir kayma alır. Bu sayede
    parseller mükemmel ayna (mirror) olmaz — organik bir yerleşim
    planı görünümü elde edilir.

    Args:
        perpendicular_points: list[QgsPointXY] — orta çizgi üzerindeki bölme noktaları
        center_line_geom: QgsGeometry — ada orta çizgisi
        randomness_pct: float — 0-15 arası yüzde değeri
        lot_width: float — parsel genişliği (metre)
        seed: int|None — tekrarlanabilirlik için rastgele tohum

    Returns:
        list[tuple[QgsPointXY, QgsPointXY]]: Her bölme noktası için
            (sol_offset_nokta, sag_offset_nokta) çifti.
            Offset = 0 ise her iki nokta da orijinal noktaya eşittir.
    """
    if randomness_pct <= 0:
        return [(pt, pt) for pt in perpendicular_points]

    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    max_offset = lot_width * (randomness_pct / 100.0)
    result = []

    for pt in perpendicular_points:
        # Sol taraf offset (orta çizgi boyunca)
        left_offset = rng.uniform(-max_offset, max_offset)
        # Sağ taraf offset (bağımsız)
        right_offset = rng.uniform(-max_offset, max_offset)

        result.append((left_offset, right_offset))

    return result


def offset_perpendicular_line(
    base_point, perp_angle, half_width, left_offset, right_offset
):
    """
    Bir bölme noktasından perpendicular çizgi oluşturur,
    sol ve sağ tarafta bağımsız offset uygulayarak.

    Args:
        base_point: QgsPointXY — orta çizgi üzerindeki bölme noktası
        perp_angle: float — perpendicular yön açısı (radyan)
        half_width: float — ada yarı genişliği
        left_offset: float — sol taraftaki kayma (orta çizgi boyunca, metre)
        right_offset: float — sağ taraftaki kayma

    Returns:
        tuple[QgsGeometry, QgsGeometry]: (sol_yarı_çizgi, sag_yarı_çizgi)
    """
    # Orta çizgi yönü (perpendicular'a dik = paralel)
    parallel_angle = perp_angle + math.pi / 2

    # Sol uç noktası (offset uygulanmış)
    left_base_x = base_point.x() + left_offset * math.cos(parallel_angle)
    left_base_y = base_point.y() + left_offset * math.sin(parallel_angle)
    left_end_x = left_base_x + half_width * math.cos(perp_angle + math.pi)
    left_end_y = left_base_y + half_width * math.sin(perp_angle + math.pi)

    # Sağ uç noktası (offset uygulanmış)
    right_base_x = base_point.x() + right_offset * math.cos(parallel_angle)
    right_base_y = base_point.y() + right_offset * math.sin(parallel_angle)
    right_end_x = right_base_x + half_width * math.cos(perp_angle)
    right_end_y = right_base_y + half_width * math.sin(perp_angle)


    # Birleştirilmiş tek çizgi oluştur (sol uç → merkez kayık → sağ uç)
    full_line = QgsGeometry.fromPolylineXY(
        [
            QgsPointXY(left_end_x, left_end_y),
            QgsPointXY(
                (left_base_x + right_base_x) / 2, (left_base_y + right_base_y) / 2
            ),
            QgsPointXY(right_end_x, right_end_y),
        ]
    )

    return full_line

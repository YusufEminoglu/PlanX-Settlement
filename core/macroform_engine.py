# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Macroform Engine — Bina formu eşleştirme ve ölçekleme motoru

Template bina formlarını (L, U, T, I, kare vb.) buildable bbox'a
sığdırarak tasarımsal bina yerleştirmesi yapar.
"""

import math
import random
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsVectorLayer, QgsFeature,
    QgsWkbTypes, QgsRectangle
)

from .geometry_engine import (
    polygon_aspect_ratio, polygon_compactness,
    oriented_minimum_bounding_box, rotate_geometry,
    translate_geometry, scale_geometry_to_area
)


class TemplateBuilding:
    """Bir şablon bina formu."""

    def __init__(self, geom, form_type="", min_area=0, max_area=99999):
        self.geom = geom
        self.form_type = form_type
        self.min_area = min_area
        self.max_area = max_area
        self.aspect_ratio = polygon_aspect_ratio(geom)
        self.compactness = polygon_compactness(geom)
        self.obb = oriented_minimum_bounding_box(geom)


def load_templates(gpkg_path, layer_name=None):
    """
    GeoPackage dosyasından şablon bina formlarını yükler.

    Args:
        gpkg_path: str — .gpkg dosya yolu
        layer_name: str|None — katman adı (None ise ilk katman)

    Returns:
        list[TemplateBuilding]
    """
    if layer_name:
        uri = f"{gpkg_path}|layername={layer_name}"
    else:
        uri = gpkg_path

    layer = QgsVectorLayer(uri, "templates", "ogr")
    if not layer.isValid():
        return []

    templates = []
    for feat in layer.getFeatures():
        geom = feat.geometry()
        if geom.isEmpty():
            continue

        form_type = ""
        min_a = 0
        max_a = 99999

        field_names = [f.name() for f in layer.fields()]
        if 'form_tipi' in field_names:
            form_type = str(feat['form_tipi'] or "")
        if 'min_alan_m2' in field_names:
            try:
                min_a = float(feat['min_alan_m2'] or 0)
            except (TypeError, ValueError):
                pass
        if 'max_alan_m2' in field_names:
            try:
                max_a = float(feat['max_alan_m2'] or 99999)
            except (TypeError, ValueError):
                pass

        templates.append(TemplateBuilding(geom, form_type, min_a, max_a))

    return templates


def match_template_to_bbox(bbox_geom, templates, diversity="Medium",
                           target_area=None, rng=None):
    """
    Buildable bbox'a en uygun şablon formu seçer.

    Akıllı Eşleştirme:
    1. Bbox aspect ratio hesapla
    2. Template'lerin aspect ratio'ları ile karşılaştır
    3. En uygun alt kümeyi seç
    4. Diversity seviyesine göre rastgele bir tane seç

    Args:
        bbox_geom: QgsGeometry — yapılaşabilir alan
        templates: list[TemplateBuilding]
        diversity: str — "Low" / "Medium" / "High"
        target_area: float|None — hedef bina alanı
        rng: random.Random — rastgele sayı üreteci

    Returns:
        TemplateBuilding|None
    """
    if not templates:
        return None

    if rng is None:
        rng = random.Random()

    bbox_ar = polygon_aspect_ratio(bbox_geom)
    bbox_area = bbox_geom.area()

    # Aspect ratio uyumuna göre skorla
    scored = []
    for t in templates:
        ar_diff = abs(bbox_ar - t.aspect_ratio)
        # Alan uyum kontrolü
        if target_area:
            if t.min_area > target_area or t.max_area < target_area:
                continue

        scored.append((ar_diff, t))

    if not scored:
        # Hiçbiri uymazsa alan filtresi olmadan dene
        scored = [(abs(bbox_ar - t.aspect_ratio), t) for t in templates]

    scored.sort(key=lambda x: x[0])

    # Diversity seviyesine göre alt küme boyutu
    if diversity == "Low":
        pool_size = max(1, len(scored) // 5)
    elif diversity == "High":
        pool_size = len(scored)
    else:  # Medium
        pool_size = max(1, len(scored) // 2)

    pool = scored[:pool_size]
    return rng.choice(pool)[1]


def fit_template_to_bbox(template, bbox_geom, max_utilization=0.95,
                         rotate_to_fit=True):
    """
    Şablon bina formunu buildable bbox'a sığdırır.

    Adımlar:
    1. Template'in OBB'sini hesapla
    2. Bbox'ın OBB'sini hesapla
    3. Her iki OBB'nin uzun kenarlarını hizala (rotate)
    4. Template'i bbox boyutlarına göre anisotropic scale uygula
    5. Template'i bbox merkezine taşı
    6. max_utilization ile alan sınırla
    7. Bbox dışına taşma kontrolü (clip)

    Args:
        template: TemplateBuilding
        bbox_geom: QgsGeometry — yapılaşabilir alan poligonu
        max_utilization: float — bbox alanının max kullanım oranı (0-1)
        rotate_to_fit: bool — rotasyon uygulansın mı

    Returns:
        QgsGeometry|None — sığdırılmış bina formu (veya None)
    """
    if template.obb is None:
        return None

    bbox_obb = oriented_minimum_bounding_box(bbox_geom)
    if bbox_obb is None:
        return None

    t_obb = template.obb
    b_obb = bbox_obb

    # 1. Rotasyon: Template'in yönünü bbox'a hizala
    result_geom = QgsGeometry(template.geom)

    if rotate_to_fit:
        angle_diff = b_obb['angle'] - t_obb['angle']
        t_center = t_obb['center']
        if t_center:
            result_geom = rotate_geometry(result_geom, angle_diff, t_center)

    # 2. Ölçekleme: Template'i bbox boyutlarına sığdır
    t_w = t_obb['width']
    t_h = t_obb['height']
    b_w = b_obb['width'] * max_utilization
    b_h = b_obb['height'] * max_utilization

    if t_w <= 0 or t_h <= 0:
        return None

    scale_x = b_w / t_w
    scale_y = b_h / t_h
    uniform_scale = min(scale_x, scale_y)

    # Centroid etrafında uniform scale
    result_geom = scale_geometry_to_area(
        result_geom,
        template.geom.area() * (uniform_scale ** 2)
    )

    # 3. Öteleme: bbox merkezine taşı
    result_center = result_geom.centroid().asPoint()
    bbox_center = bbox_geom.centroid().asPoint()
    dx = bbox_center.x() - result_center.x()
    dy = bbox_center.y() - result_center.y()
    result_geom = translate_geometry(result_geom, dx, dy)

    # 4. Taşma kontrolü: bbox dışı kırp
    result_geom = result_geom.intersection(bbox_geom)

    if result_geom.isEmpty():
        return None

    return result_geom

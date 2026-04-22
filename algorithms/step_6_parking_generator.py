# -*- coding: utf-8 -*-
"""
Adım 6: ParkingGenerator — Parametrik otopark düzeni

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

import math
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingException,
    QgsField,
    QgsFields,
    QgsFeatureSink,
    QgsPointXY,
)


def _create_stall(cx, cy, w, d, rot):
    """Tek otopark stall rect (merkez tabanlı, döndürülmüş)."""
    hw, hd = w / 2.0, d / 2.0
    cos_a, sin_a = math.cos(rot), math.sin(rot)
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    pts = [
        QgsPointXY(x * cos_a - y * sin_a + cx, x * sin_a + y * cos_a + cy)
        for x, y in corners
    ]
    pts.append(pts[0])
    return QgsGeometry.fromPolygonXY([pts])


def _optimal_rotation(polygon_geom, entrance_point=None):
    """Poligonun OBB yönünü ve boyutlarını döner. Giriş noktası varsa aisle'ları ona hizalar."""
    obb = polygon_geom.orientedMinimumBoundingBox()
    if obb and len(obb) >= 5:
        _, _, angle, w, h = obb
        base_rot = math.radians(angle)
        # Giriş noktası varsa: OBB'nin hangi kenarına yakın olduğuna bak
        # ve aisle'ları o yöne hizala
        if entrance_point is not None:
            center = polygon_geom.centroid().asPoint()
            to_entrance = math.atan2(
                entrance_point.y() - center.y(), entrance_point.x() - center.x()
            )
            # OBB açısı ile giriş yönü arasındaki fark
            diff = abs(to_entrance - base_rot) % math.pi
            # Eğer giriş daha çok kısa kenara yakınsa 90° döndür
            if diff > math.pi / 4 and diff < 3 * math.pi / 4:
                base_rot += math.pi / 2
                w, h = h, w
        return base_rot, max(w, h), min(w, h)
    bb = polygon_geom.boundingBox()
    return 0.0, bb.width(), bb.height()


def generate_optimized_parking(
    polygon_geom,
    stall_w=2.5,
    stall_d=5.0,
    aisle_w=6.0,
    parking_angle_deg=90,
    stall_gap=0.01,
    edge_margin=0.5,
    entrance_point=None,
):
    """
    Poligon şekline göre optimize edilmiş otopark düzeni.
    entrance_point: En yakın yol noktası — aisle'lar bu yöne hizalanır.
    """
    if edge_margin > 0:
        work = polygon_geom.buffer(-edge_margin, 16)
        if work.isEmpty():
            return {"stalls": [], "aisles": [], "total_stalls": 0, "efficiency": 0}
    else:
        work = polygon_geom

    rotation, long_side, short_side = _optimal_rotation(work, entrance_point)
    center = work.centroid().asPoint()

    # Giriş çizgisi oluştur (varsa)
    entrance_line = None
    if entrance_point is not None:
        # Otopark sınırındaki en yakın noktayı bul
        nearest = polygon_geom.nearestPoint(QgsGeometry.fromPointXY(entrance_point))
        if not nearest.isEmpty():
            np = nearest.asPoint()
            entrance_line = QgsGeometry.fromPolylineXY([entrance_point, np])

    # Stall açısı düzeltmeleri
    if parking_angle_deg == 60:
        effective_depth = stall_d * math.cos(math.radians(30))
        effective_width = stall_w / math.cos(math.radians(30))
        stall_rot_offset = math.radians(30)
    elif parking_angle_deg == 45:
        effective_depth = stall_d * math.cos(math.radians(45))
        effective_width = stall_w / math.cos(math.radians(45))
        stall_rot_offset = math.radians(45)
    else:
        effective_depth = stall_d
        effective_width = stall_w
        stall_rot_offset = 0

    # Modül: stall_sırası + aisle + stall_sırası
    module_width = 2 * effective_depth + aisle_w
    n_modules = max(1, int(short_side / module_width))
    actual_total = n_modules * module_width
    start_perp = -actual_total / 2.0

    # Uzun kenar boyunca stall sayısı
    eff_stall_w = effective_width + stall_gap
    n_stalls_row = max(1, int(long_side / eff_stall_w))
    row_total = n_stalls_row * eff_stall_w
    start_along = -row_total / 2.0

    cos_r, sin_r = math.cos(rotation), math.sin(rotation)
    cos_rp, sin_rp = math.cos(rotation + math.pi / 2), math.sin(rotation + math.pi / 2)

    stalls = []
    aisles = []

    for m in range(n_modules):
        mc_offset = start_perp + m * module_width + module_width / 2.0
        mcx = center.x() + mc_offset * cos_rp
        mcy = center.y() + mc_offset * sin_rp

        # İki stall sırası
        for row in range(2):
            row_offset = (
                -(aisle_w / 2.0 + effective_depth / 2.0)
                if row == 0
                else (aisle_w / 2.0 + effective_depth / 2.0)
            )
            rcx = mcx + row_offset * cos_rp
            rcy = mcy + row_offset * sin_rp

            for s in range(n_stalls_row):
                along = start_along + s * eff_stall_w + eff_stall_w / 2.0
                sx = rcx + along * cos_r
                sy = rcy + along * sin_r

                stall_rot = rotation + stall_rot_offset * (1 if row == 0 else -1)
                sg = _create_stall(sx, sy, stall_w, stall_d, stall_rot)

                if work.contains(sg):
                    stalls.append(sg)
                elif not sg.intersection(work).isEmpty():
                    inter = sg.intersection(work)
                    if inter.area() > sg.area() * 0.75:
                        stalls.append(sg)

        # Aisle center line
        a1 = QgsPointXY(mcx - long_side / 2 * cos_r, mcy - long_side / 2 * sin_r)
        a2 = QgsPointXY(mcx + long_side / 2 * cos_r, mcy + long_side / 2 * sin_r)
        al = QgsGeometry.fromPolylineXY([a1, a2]).intersection(work)
        if not al.isEmpty():
            aisles.append(al)

    t_area = sum(s.area() for s in stalls)
    eff = t_area / polygon_geom.area() if polygon_geom.area() > 0 else 0

    return {
        "stalls": stalls,
        "aisles": aisles,
        "entrance_line": entrance_line,
        "total_stalls": len(stalls),
        "efficiency": round(eff, 3),
    }


class ParkingGeneratorAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    INPUT_ROADS = "INPUT_ROADS"
    STALL_WIDTH = "STALL_WIDTH"
    STALL_DEPTH = "STALL_DEPTH"
    AISLE_WIDTH = "AISLE_WIDTH"
    PARKING_ANGLE = "PARKING_ANGLE"
    STALL_GAP = "STALL_GAP"
    EDGE_MARGIN = "EDGE_MARGIN"
    OUTPUT_STALLS = "OUTPUT_STALLS"
    OUTPUT_AISLES = "OUTPUT_AISLES"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Otopark alanı katmanı (poligon)"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_ROADS,
                self.tr(
                    "Yol ağı katmanı (çizgi) — otopark girişini en yakın yola hizalar"
                ),
                [QgsProcessing.TypeVectorLine],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STALL_WIDTH,
                self.tr("Otopark yeri genişliği (m) — standart: 2.5"),
                QgsProcessingParameterNumber.Double,
                2.5,
                minValue=2.0,
                maxValue=4.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STALL_DEPTH,
                self.tr("Otopark yeri derinliği (m) — standart: 5.0"),
                QgsProcessingParameterNumber.Double,
                5.0,
                minValue=4.0,
                maxValue=7.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.AISLE_WIDTH,
                self.tr("Araç yolu genişliği (m) — 90° için min 6.0"),
                QgsProcessingParameterNumber.Double,
                6.0,
                minValue=3.0,
                maxValue=8.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PARKING_ANGLE,
                self.tr("Park açısı"),
                options=["90° (en verimli)", "60° (kolay manevra)", "45° (tek yön)"],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STALL_GAP,
                self.tr("Stall arası boşluk (m) — önerilen: 0.01"),
                QgsProcessingParameterNumber.Double,
                0.01,
                minValue=0.0,
                maxValue=0.5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.EDGE_MARGIN,
                self.tr("Kenar boşluğu (m)"),
                QgsProcessingParameterNumber.Double,
                0.5,
                minValue=0.0,
                maxValue=3.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_STALLS, self.tr("Otopark yerleri (poligon)")
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_AISLES, self.tr("Araç yolları (çizgi)")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        road_source = self.parameterAsSource(parameters, self.INPUT_ROADS, context)
        stall_w = self.parameterAsDouble(parameters, self.STALL_WIDTH, context)
        stall_d = self.parameterAsDouble(parameters, self.STALL_DEPTH, context)
        aisle_w = self.parameterAsDouble(parameters, self.AISLE_WIDTH, context)
        angle_idx = self.parameterAsInt(parameters, self.PARKING_ANGLE, context)
        gap = self.parameterAsDouble(parameters, self.STALL_GAP, context)
        margin = self.parameterAsDouble(parameters, self.EDGE_MARGIN, context)

        angle_map = {0: 90, 1: 60, 2: 45}
        parking_angle = angle_map.get(angle_idx, 90)

        if source is None:
            raise QgsProcessingException(self.tr("Katman yüklenemedi."))

        # Yol geometrilerini ön-yükle
        road_geoms = []
        if road_source:
            for rf in road_source.getFeatures():
                rg = rf.geometry()
                if not rg.isEmpty():
                    road_geoms.append(rg)
            feedback.pushInfo(
                f"Yol ağı: {len(road_geoms)} çizgi yüklendi → giriş hizalaması aktif"
            )
        else:
            feedback.pushInfo("⚠️ Yol ağı verilmedi — OBB yönüne göre hizalanacak")

        s_fields = QgsFields()
        s_fields.append(QgsField("area_fid", QVariant.Int))
        s_fields.append(QgsField("stall_id", QVariant.Int))
        s_fields.append(QgsField("stall_area_m2", QVariant.Double, "double", 20, 2))

        (s_sink, s_dest) = self.parameterAsSink(
            parameters,
            self.OUTPUT_STALLS,
            context,
            s_fields,
            QgsWkbTypes.Polygon,
            source.sourceCrs(),
        )

        a_fields = QgsFields()
        a_fields.append(QgsField("area_fid", QVariant.Int))
        (a_sink, a_dest) = self.parameterAsSink(
            parameters,
            self.OUTPUT_AISLES,
            context,
            a_fields,
            QgsWkbTypes.LineString,
            source.sourceCrs(),
        )

        total_stalls = 0
        total = source.featureCount() or 1

        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom.isEmpty():
                continue

            # En yakın yol noktasını bul
            entrance = None
            if road_geoms:
                min_dist = float("inf")
                for rg in road_geoms:
                    d = geom.distance(rg)
                    if d < min_dist:
                        min_dist = d
                        nearest_on_road = rg.nearestPoint(geom.centroid())
                        if not nearest_on_road.isEmpty():
                            entrance = nearest_on_road.asPoint()

            result = generate_optimized_parking(
                geom,
                stall_w,
                stall_d,
                aisle_w,
                parking_angle,
                gap,
                margin,
                entrance_point=entrance,
            )

            for si, sg in enumerate(result["stalls"]):
                sf = QgsFeature(s_fields)
                sf.setGeometry(sg)
                sf.setAttributes([feat.id(), si + 1, round(sg.area(), 2)])
                s_sink.addFeature(sf, QgsFeatureSink.FastInsert)

            for ag in result["aisles"]:
                af = QgsFeature(a_fields)
                af.setGeometry(ag)
                af.setAttributes([feat.id()])
                a_sink.addFeature(af, QgsFeatureSink.FastInsert)

            # Giriş çizgisi
            if result.get("entrance_line") and not result["entrance_line"].isEmpty():
                ef = QgsFeature(a_fields)
                ef.setGeometry(result["entrance_line"])
                ef.setAttributes([feat.id()])
                a_sink.addFeature(ef, QgsFeatureSink.FastInsert)

            total_stalls += result["total_stalls"]
            feedback.pushInfo(
                f"Alan {feat.id()}: {result['total_stalls']} yer, "
                f"verimlilik: {result['efficiency'] * 100:.1f}%"
            )
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(f"Toplam: {total_stalls} otopark yeri üretildi.")
        return {self.OUTPUT_STALLS: s_dest, self.OUTPUT_AISLES: a_dest}

    def name(self):
        return "6_parking_generator"

    def displayName(self):
        return "6. Parametrik Otopark Düzeni"

    def group(self):
        return "Yerleşim Planı İş Akışı"

    def groupId(self):
        return "yerlesim_plani_workflow"

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Poligon alanlarında parametrik otopark stall düzeni üretir.\n\n"
            "Yol ağı bağlantısı (opsiyonel ama önerilir):\n"
            "• Yol katmanı verildiğinde otopark girişi en yakın\n"
            "  yola hizalanır ve giriş çizgisi oluşturulur\n"
            "• Verilmezse OBB yönüne göre hizalanır\n\n"
            "Standart boyutlar:\n"
            "• 90°: stall 2.5×5.0m, aisle 6.0m (en verimli)\n"
            "• 60°: manevra kolay, aisle 4.5m\n"
            "• 45°: tek yön, aisle 3.6m\n\n"
            "Çıktılar:\n"
            "• Otopark yerleri: Her stall bir poligon\n"
            "• Araç yolları: Aisle çizgileri + giriş bağlantısı"
        )

    def createInstance(self):
        return ParkingGeneratorAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

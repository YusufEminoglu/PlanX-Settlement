# -*- coding: utf-8 -*-
"""
Adım 1: ParcelFlux — Ada → Parsel Bölme

Geliştirilmiş parsel üretici: genişlik varyasyonu, tek sıra algılama,
artık parçaları komşuya birleştirme.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

import processing
import math
import random
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingException,
    QgsField,
    QgsVectorLayer,
    QgsFeatureSink,
    QgsPointXY,
    QgsLineString,
    QgsProcessingMultiStepFeedback,
    QgsSpatialIndex,
)


class ParcelFluxAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    LOT_WIDTH = "LOT_WIDTH"
    MIN_AREA = "MIN_AREA"
    MAX_AREA = "MAX_AREA"
    MERGE_THRESHOLD = "MERGE_THRESHOLD"
    UNIFORM_CORNERS = "UNIFORM_CORNERS"
    WIDTH_VARIATION = "WIDTH_VARIATION"
    FISHBONE_OFFSET = "FISHBONE_OFFSET"
    ROW_WIDTH_ASYMMETRY = "ROW_WIDTH_ASYMMETRY"
    HLINE_OFFSET = "HLINE_OFFSET"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Girdi poligon katmanı (imar adası)"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LOT_WIDTH,
                self.tr("Hedef parsel genişliği (m) — 16m konut alanında yaygın"),
                QgsProcessingParameterNumber.Double,
                16.0,
                minValue=5.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_AREA,
                self.tr(
                    "Minimum parsel alanı (m²) — bundan küçük parseller birleştirilir"
                ),
                QgsProcessingParameterNumber.Double,
                300.0,
                minValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_AREA,
                self.tr("Maksimum parsel alanı (m²) — filtreleme üst sınırı"),
                QgsProcessingParameterNumber.Double,
                2000.0,
                minValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MERGE_THRESHOLD,
                self.tr(
                    "Küçük parsel birleştirme eşiği (ort. alanın %) — yüksek değer daha agresif birleştirir"
                ),
                QgsProcessingParameterNumber.Double,
                35.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.UNIFORM_CORNERS,
                self.tr(
                    "Köşeleri merkeze göre eşit dağıt — kapatıldığında parsel sıralaması bir kenardan başlar"
                ),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.WIDTH_VARIATION,
                self.tr(
                    "Parsel genişliği varyasyonu (%) — 0=sabit, 15=±%15 (18m vs 23m gibi doğal çeşitlilik)"
                ),
                QgsProcessingParameterNumber.Double,
                0.0,
                minValue=0.0,
                maxValue=25.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.FISHBONE_OFFSET,
                self.tr(
                    "Fishbone sınır offset (%) — bölme çizgilerindeki organik kayma, 0=düz"
                ),
                QgsProcessingParameterNumber.Double,
                0.0,
                minValue=0.0,
                maxValue=15.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ROW_WIDTH_ASYMMETRY,
                self.tr(
                    "Sıra genişlik asimetrisi (%) — ÖN BAHÇE genişlik farkı\n"
                    "0 = tüm parseller aynı genişlikte\n"
                    "10 = ±%10 → 20m lot ise: bir sıra ~22m, karşı sıra ~18m\n"
                    "North cepheli parseller ile South cepheli parsellerin\n"
                    "ön bahçe genişliklerinin farklı olmasını sağlar"
                ),
                QgsProcessingParameterNumber.Double,
                0.0,
                minValue=0.0,
                maxValue=25.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HLINE_OFFSET,
                self.tr(
                    "Ortadan bölen çizgi (h-line) kayması (%) — 0=tam orta\n"
                    "Arka bahçe sınır çizgisini merkezden kaydırır"
                ),
                QgsProcessingParameterNumber.Double,
                0.0,
                minValue=0.0,
                maxValue=25.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Çıktı parseller"))
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback = QgsProcessingMultiStepFeedback(30, feedback)

        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.tr("Girdi katmanı yüklenemedi."))

        lot_width = self.parameterAsDouble(parameters, self.LOT_WIDTH, context)
        min_area = self.parameterAsDouble(parameters, self.MIN_AREA, context)
        max_area = self.parameterAsDouble(parameters, self.MAX_AREA, context)
        merge_threshold = (
            self.parameterAsDouble(parameters, self.MERGE_THRESHOLD, context) / 100.0
        )
        uniform_corners = self.parameterAsBool(
            parameters, self.UNIFORM_CORNERS, context
        )
        width_var = self.parameterAsDouble(parameters, self.WIDTH_VARIATION, context)
        fishbone = self.parameterAsDouble(parameters, self.FISHBONE_OFFSET, context)
        row_asym = self.parameterAsDouble(parameters, self.ROW_WIDTH_ASYMMETRY, context)
        hline_off = self.parameterAsDouble(parameters, self.HLINE_OFFSET, context)

        features = list(source.getFeatures())
        if not features:
            raise QgsProcessingException(self.tr("Girdi katmanında obje bulunamadı."))

        feedback.pushInfo(
            f"Girdi: {len(features)} ada | Genişlik: {lot_width}m | "
            f"Genişlik varyasyonu: ±{width_var}% | Fishbone: {fishbone}% | "
            f"Sıra genişlik asimetrisi: ±{row_asym}% | H-line kayması: ±{hline_off}%"
        )

        # Çıktı alanları — orijinal + cephe hazırlık alanları
        fields = source.fields()
        fields.append(QgsField("aream2", QVariant.Double, "double", 20, 2))
        fields.append(QgsField("facade_front", QVariant.String, "string", 100))
        fields.append(QgsField("facade_side", QVariant.String, "string", 100))
        fields.append(QgsField("facade_back", QVariant.String, "string", 100))
        fields.append(QgsField("facade_count", QVariant.Int))
        fields.append(QgsField("is_corner", QVariant.Bool))
        fields.append(QgsField("front_direction", QVariant.String, "string", 20))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.MultiPolygon,
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException(self.tr("Çıktı katmanı oluşturulamadı."))

        # ═══ Poligonları hazırla ═══
        regular_layer = QgsVectorLayer(
            "Polygon?crs=" + source.sourceCrs().authid(), "regular", "memory"
        )
        irregular_layer = QgsVectorLayer(
            "Polygon?crs=" + source.sourceCrs().authid(), "irregular", "memory"
        )
        reg_prov = regular_layer.dataProvider()
        irr_prov = irregular_layer.dataProvider()
        reg_prov.addAttributes(source.fields())
        irr_prov.addAttributes(source.fields())
        regular_layer.updateFields()
        irregular_layer.updateFields()

        has_irregular = False
        for feat in features:
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            polys = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
            for polygon in polys:
                nf = QgsFeature(source.fields())
                nf.setAttributes(feat.attributes())
                if len(polygon[0]) == 5:
                    nf.setGeometry(QgsGeometry.fromPolygonXY(polygon))
                    reg_prov.addFeature(nf)
                else:
                    has_irregular = True
                    nf.setGeometry(QgsGeometry.fromPolygonXY(polygon))
                    irr_prov.addFeature(nf)
        feedback.setCurrentStep(2)

        if has_irregular:
            feedback.pushInfo("Düzensiz poligonlar OBB ile işleniyor...")
            omb_result = processing.run(
                "native:orientedminimumboundingbox",
                {"INPUT": irregular_layer, "OUTPUT": "memory:"},
                context=context,
                feedback=feedback,
            )
            merged_layer = processing.run(
                "native:mergevectorlayers",
                {"LAYERS": [regular_layer, omb_result["OUTPUT"]], "OUTPUT": "memory:"},
                context=context,
                feedback=feedback,
            )["OUTPUT"]
        else:
            merged_layer = regular_layer
        feedback.setCurrentStep(5)

        # ═══ Bölme çizgileri oluştur ═══
        feedback.pushInfo("Bölme çizgileri oluşturuluyor...")
        h_layer = QgsVectorLayer(
            "LineString?crs=" + source.sourceCrs().authid(), "h", "memory"
        )
        p_layer = QgsVectorLayer(
            "LineString?crs=" + source.sourceCrs().authid(), "p", "memory"
        )
        h_prov = h_layer.dataProvider()
        p_prov = p_layer.dataProvider()
        h_prov.addAttributes([QgsField("polygon_id", QVariant.Int)])
        p_prov.addAttributes([QgsField("polygon_id", QVariant.Int)])
        h_layer.updateFields()
        p_layer.updateFields()

        rng = random.Random(42)

        for feature in merged_layer.getFeatures():
            geom = feature.geometry()
            if geom.isEmpty():
                continue
            polys = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
            for polygon in polys:
                sides = []
                for i in range(len(polygon[0]) - 1):
                    side = QgsLineString([polygon[0][i], polygon[0][i + 1]])
                    sides.append((side, side.length()))
                if len(sides) < 2:
                    continue
                sides.sort(key=lambda x: x[1])

                # Kısa kenarlar = bölme yönü perpendicular olacak kenarlar
                shortest_sides = sides[:2]

                # ═══ H-line kayması (opsiyonel) ═══
                if hline_off > 0:
                    h_shift = rng.uniform(-hline_off, hline_off) / 100.0
                    h_ratio = 0.5 + h_shift
                else:
                    h_ratio = 0.5

                midpoints = []
                for s, _ in shortest_sides:
                    sp = s.startPoint()
                    ep = s.endPoint()
                    mx = sp.x() + h_ratio * (ep.x() - sp.x())
                    my = sp.y() + h_ratio * (ep.y() - sp.y())
                    midpoints.append(QgsPointXY(mx, my))

                division_line = QgsGeometry.fromPolylineXY(midpoints)

                # Orta çizgiyi ekle
                h_feat = QgsFeature()
                h_feat.setGeometry(division_line)
                h_feat.setAttributes([feature.id()])
                h_prov.addFeature(h_feat)

                dx = midpoints[1].x() - midpoints[0].x()
                dy = midpoints[1].y() - midpoints[0].y()
                angle = math.atan2(dy, dx)
                max_width = max(sides[0][1], sides[1][1])
                line_length = division_line.length()
                perp_angle = angle + math.pi / 2
                half_ext = (
                    max_width * 0.75
                )  # Yarım uzunluk — daha geniş (önceki 0.6 yetersiz kalıyordu)

                # ═══ Tek sıra / çift sıra tespiti ═══
                is_single_row = max_width < (lot_width * 1.8)
                if is_single_row:
                    feedback.pushInfo(
                        f"  Ada {feature.id()}: tek sıra mod (kısa kenar: {max_width:.1f}m)"
                    )

                # ═══ Sıra genişlik asimetrisi ═══
                # İki sıra için farklı parsel genişlikleri hesapla
                if row_asym > 0 and not is_single_row:
                    shift_pct = rng.uniform(-row_asym, row_asym) / 100.0
                    width_side_A = lot_width * (1 + shift_pct)  # Örn: 22m
                    width_side_B = lot_width * (1 - shift_pct)  # Örn: 18m
                    feedback.pushInfo(
                        f"  Ada {feature.id()}: sıra asimetrisi → "
                        f"A={width_side_A:.1f}m, B={width_side_B:.1f}m"
                    )
                else:
                    width_side_A = lot_width
                    width_side_B = lot_width

                fishbone_max = lot_width * (fishbone / 100.0) if fishbone > 0 else 0

                def _make_widths(base_w, n_seg):
                    """Genişlik varyasyonlu segment listesi."""
                    if width_var > 0 and n_seg > 1:
                        ws = [
                            base_w * (1 + rng.uniform(-width_var, width_var) / 100.0)
                            for _ in range(n_seg)
                        ]
                        if sum(ws) > 0:
                            sc = (
                                line_length - (line_length - n_seg * base_w) / 2
                            ) / sum(ws)
                            ws = [w * sc for w in ws]
                        return ws
                    return [base_w] * n_seg

                def _add_half_line(pt, direction, fish_off=0):
                    """h_line noktasından bir yöne yarım bölme çizgisi oluştur."""
                    par_angle = angle
                    bx = pt.x() + fish_off * math.cos(par_angle)
                    by = pt.y() + fish_off * math.sin(par_angle)
                    ex = bx + direction * half_ext * math.cos(perp_angle)
                    ey = by + direction * half_ext * math.sin(perp_angle)
                    hl = QgsGeometry.fromPolylineXY(
                        [QgsPointXY(bx, by), QgsPointXY(ex, ey)]
                    )
                    feat = QgsFeature()
                    feat.setGeometry(hl)
                    feat.setAttributes([feature.id()])
                    p_prov.addFeature(feat)

                if row_asym > 0 and not is_single_row:
                    # ═══ SPLIT MODE: Her sıra bağımsız aralıklarda ═══
                    # Taraf A (perp_angle yönü, +1)
                    n_seg_A = max(1, math.floor(line_length / width_side_A))
                    rem_A = line_length - n_seg_A * width_side_A
                    start_A = rem_A / 2 if uniform_corners else 0
                    widths_A = _make_widths(width_side_A, n_seg_A)
                    cum_A = start_A
                    for i in range(n_seg_A - 1):
                        cum_A += widths_A[i]
                        pt = division_line.interpolate(cum_A).asPoint()
                        fish = (
                            rng.uniform(-fishbone_max, fishbone_max)
                            if fishbone > 0
                            else 0
                        )
                        _add_half_line(pt, +1.0, fish)

                    # Taraf B (perp_angle karşı yönü, -1)
                    n_seg_B = max(1, math.floor(line_length / width_side_B))
                    rem_B = line_length - n_seg_B * width_side_B
                    start_B = rem_B / 2 if uniform_corners else 0
                    widths_B = _make_widths(width_side_B, n_seg_B)
                    cum_B = start_B
                    for i in range(n_seg_B - 1):
                        cum_B += widths_B[i]
                        pt = division_line.interpolate(cum_B).asPoint()
                        fish = (
                            rng.uniform(-fishbone_max, fishbone_max)
                            if fishbone > 0
                            else 0
                        )
                        _add_half_line(pt, -1.0, fish)
                else:
                    # ═══ NORMAL MODE: Tek düz çizgi (mevcut davranış) ═══
                    n_seg = max(1, math.floor(line_length / width_side_A))
                    rem = line_length - n_seg * width_side_A
                    start_off = rem / 2 if uniform_corners else 0
                    widths = _make_widths(width_side_A, n_seg)
                    cumulative = start_off
                    ext_w = max_width * 1.1

                    for i in range(n_seg - 1):
                        cumulative += widths[i]
                        point = division_line.interpolate(cumulative).asPoint()

                        if fishbone > 0:
                            l_off = rng.uniform(-fishbone_max, fishbone_max)
                            r_off = rng.uniform(-fishbone_max, fishbone_max)
                            pa = angle
                            lx = point.x() + l_off * math.cos(pa)
                            ly = point.y() + l_off * math.sin(pa)
                            x1 = lx + ext_w / 2 * math.cos(perp_angle)
                            y1 = ly + ext_w / 2 * math.sin(perp_angle)
                            rx = point.x() + r_off * math.cos(pa)
                            ry = point.y() + r_off * math.sin(pa)
                            x2 = rx - ext_w / 2 * math.cos(perp_angle)
                            y2 = ry - ext_w / 2 * math.sin(perp_angle)
                        else:
                            x1 = point.x() + ext_w / 2 * math.cos(perp_angle)
                            y1 = point.y() + ext_w / 2 * math.sin(perp_angle)
                            x2 = point.x() - ext_w / 2 * math.cos(perp_angle)
                            y2 = point.y() - ext_w / 2 * math.sin(perp_angle)

                        pl = QgsGeometry.fromPolylineXY(
                            [QgsPointXY(x1, y1), QgsPointXY(x2, y2)]
                        )
                        pf = QgsFeature()
                        pf.setGeometry(pl)
                        pf.setAttributes([feature.id()])
                        p_prov.addFeature(pf)

        feedback.setCurrentStep(10)
        feedback.pushInfo("Çizgiler uzatılıyor...")

        ext_h = processing.run(
            "native:extendlines",
            {
                "INPUT": h_layer,
                "START_DISTANCE": 0.05,
                "END_DISTANCE": 0.05,
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        ext_p = processing.run(
            "native:extendlines",
            {
                "INPUT": p_layer,
                "START_DISTANCE": 0.05,
                "END_DISTANCE": 0.05,
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        merged_lines = processing.run(
            "native:mergevectorlayers",
            {"LAYERS": [ext_h, ext_p], "OUTPUT": "memory:"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        clipped_lines = processing.run(
            "native:clip",
            {
                "INPUT": merged_lines,
                "OVERLAY": parameters[self.INPUT],
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        feedback.setCurrentStep(18)
        feedback.pushInfo("Poligonlar bölünüyor...")

        split_polygons = processing.run(
            "native:splitwithlines",
            {
                "INPUT": parameters[self.INPUT],
                "LINES": clipped_lines,
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        feedback.setCurrentStep(22)

        # ═══ Artık parçaları birleştirme (3 geçişli) ═══
        feedback.pushInfo("Küçük ve artık parseller birleştiriliyor...")

        def merge_small(layer, threshold_val, min_a):
            """Eşik altı parselleri en uzun ortak kenara sahip komşuya birleştirir."""
            areas = {}
            total_area = 0
            cnt = 0
            for f in layer.getFeatures():
                g = f.geometry()
                if g and not g.isEmpty():
                    a = g.area()
                    areas[f.id()] = a
                    total_area += a
                    cnt += 1

            si = QgsSpatialIndex()
            for f in layer.getFeatures():
                si.addFeature(f)

            merged = []
            processed = set()
            for f in layer.getFeatures():
                if f.id() in processed:
                    continue
                fid = f.id()
                if fid not in areas:
                    continue

                # Eşik altı VEYA min_area altı → birleştir
                should_merge = areas[fid] < threshold_val or areas[fid] < min_a
                if should_merge:
                    nbrs = si.intersects(f.geometry().boundingBox())
                    best = None
                    best_len = 0
                    for nid in nbrs:
                        if nid == fid or nid in processed:
                            continue
                        nf = layer.getFeature(nid)
                        ng = nf.geometry()
                        if ng is None or ng.isEmpty():
                            continue
                        shared = f.geometry().intersection(ng)
                        if shared.type() == QgsWkbTypes.LineGeometry:
                            sl = shared.length()
                            if sl > best_len:
                                best_len = sl
                                best = nf
                    if best:
                        mg = f.geometry().combine(best.geometry())
                        mf = QgsFeature(f.fields())
                        mf.setGeometry(mg)
                        mf.setAttributes(f.attributes())
                        merged.append(mf)
                        processed.add(fid)
                        processed.add(best.id())
                    else:
                        merged.append(f)
                        processed.add(fid)
                else:
                    merged.append(f)
                    processed.add(fid)
            return merged, sum(
                1 for _ in processed if _ in areas and areas.get(_, 999) < threshold_val
            ) // 2

        fc = split_polygons.featureCount()
        ta = sum(
            f.geometry().area() for f in split_polygons.getFeatures() if f.geometry()
        )
        thresh = merge_threshold * (ta / fc) if fc > 0 else 0

        # 3 geçiş — artık üçgenler ve dar şeritler dahil
        current_layer = split_polygons
        for pass_num in range(3):
            m, mc = merge_small(current_layer, thresh, min_area)
            feedback.pushInfo(f"  Geçiş {pass_num + 1}: {mc} parsel birleştirildi.")
            if mc == 0:
                break
            temp = QgsVectorLayer(
                "Polygon?crs=" + source.sourceCrs().authid(),
                f"pass{pass_num}",
                "memory",
            )
            tp = temp.dataProvider()
            tp.addAttributes(
                split_polygons.fields() if pass_num == 0 else current_layer.fields()
            )
            temp.updateFields()
            tp.addFeatures(m)
            current_layer = temp
            # Yeni eşik
            fc2 = temp.featureCount()
            ta2 = sum(f.geometry().area() for f in temp.getFeatures() if f.geometry())
            thresh = merge_threshold * (ta2 / fc2) if fc2 > 0 else 0

        # Son liste
        final_features = (
            m if mc > 0 or pass_num == 0 else list(current_layer.getFeatures())
        )
        feedback.setCurrentStep(28)

        # ═══ Çıktı üret ═══
        count = 0
        for feat in final_features:
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            area = geom.area()
            if area > max_area:
                continue
            # min_area altındakileri de dahil et (birleştirme onları yakalar)
            # Sadece çok minik kırıntıları atla
            if area < 5.0:
                continue

            nf = QgsFeature(fields)
            nf.setGeometry(geom)
            src_attrs = feat.attributes()
            while len(src_attrs) < source.fields().count():
                src_attrs.append(None)
            src_attrs = src_attrs[: source.fields().count()]
            attrs = src_attrs + [round(area, 2), "", "", "", 0, False, ""]
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            count += 1

        feedback.pushInfo(f"✅ Tamamlandı. {count} parsel üretildi.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return "1_parcel_flux"

    def displayName(self):
        return "1. ParcelFlux — Ada→Parsel Bölme"

    def group(self):
        return "Yerleşim Planı İş Akışı"

    def groupId(self):
        return "yerlesim_plani_workflow"

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "İmar adalarını belirtilen genişlikte parsellere böler.\n\n"
            "Parametreler:\n"
            "• Hedef parsel genişliği: Konut alanlarında genellikle 14-20m\n"
            "• Min/Max alan: Bu aralık dışındaki parseller filtrelenir\n"
            "• Birleştirme eşiği: Yüksek değer → daha agresif birleştirme\n"
            "• Genişlik varyasyonu: Aynı sıradaki parsellerin eni ±% değişir\n"
            "• Fishbone offset: Bölme çizgisi uçlarında organik kayma\n\n"
            "★ Sıra genişlik asimetrisi (en önemli parametre):\n"
            "  h_line'ın iki tarafındaki parsel sıraları FARKLI\n"
            "  genişliklerde bölünür.\n\n"
            "  Örnek: lot_width=20m, asimetri=%10 →\n"
            "  ┌──22m──┬──22m──┬──22m──┬──22m──┐\n"
            "  │ North │ North │ North │ North │ ← 22m genişlik\n"
            "  ├───────┴──┬────┴──┬────┴───────┤ ← h_line (ortada)\n"
            "  │  South   │ South │   South    │ ← 18m genişlik\n"
            "  └──18m─────┴─18m──┴────18m──────┘\n\n"
            "  İki tarafta FARKLI SAYIDA parsel oluşabilir.\n\n"
            "• H-line kayması: Opsiyonel, arka bahçe sınırını\n"
            "  merkezden kaydırır (derinlik farkı)\n\n"
            "Çıktı: Cephe sütunları boş gelir → Adım 2'de doldurulur."
        )

    def createInstance(self):
        return ParcelFluxAlgorithm()

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

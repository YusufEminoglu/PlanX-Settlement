# -*- coding: utf-8 -*-
"""
Adım 2: FacadeDetector — Parsel cephe tespiti
Network tabanlı ön/yan/arka cephe sınıflandırması.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

import os, sys
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingException,
    QgsFeatureSink,
    QgsPointXY,
)
import math

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from core.geometry_engine import (
    get_polygon_edges,
    edge_midpoint,
    edge_direction_angle,
    compass_direction,
)


class FacadeDetectorAlgorithm(QgsProcessingAlgorithm):
    INPUT_PARCELS = "INPUT_PARCELS"
    INPUT_ROADS = "INPUT_ROADS"
    THRESHOLD = "THRESHOLD"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_PARCELS,
                self.tr("Parsel katmanı (Adım 1 çıktısı)"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_ROADS,
                self.tr("Yol ağı katmanı (çizgi)"),
                [QgsProcessing.TypeVectorLine],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD,
                self.tr("Ön cephe mesafe eşiği (m) — 0=otomatik"),
                QgsProcessingParameterNumber.Double,
                0.0,
                minValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Cephe bilgili parseller")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT_PARCELS, context)
        road_source = self.parameterAsSource(parameters, self.INPUT_ROADS, context)
        threshold = self.parameterAsDouble(parameters, self.THRESHOLD, context)

        if source is None or road_source is None:
            raise QgsProcessingException(self.tr("Katmanlar yüklenemedi."))

        # Yol geometrilerini ön-yükle
        road_geoms = []
        for rf in road_source.getFeatures():
            rg = rf.geometry()
            if not rg.isEmpty():
                road_geoms.append(rg)

        if not road_geoms:
            raise QgsProcessingException(self.tr("Yol katmanında obje yok."))

        # Çıktı: aynı alanlar
        fields = source.fields()
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.MultiPolygon,
            source.sourceCrs(),
        )

        total = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break

            geom = feat.geometry()
            if geom.isEmpty():
                continue

            edges = get_polygon_edges(geom)
            if not edges:
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                continue

            # Otomatik eşik
            auto_threshold = threshold
            if auto_threshold <= 0:
                obb = geom.orientedMinimumBoundingBox()
                if obb and len(obb) >= 5:
                    auto_threshold = min(obb[3], obb[4]) * 0.6
                else:
                    auto_threshold = math.sqrt(geom.area()) * 0.5

            # Her kenarın orta noktası → en yakın yol mesafesi
            front_indices = []
            edge_dists = []
            for ei, (p1, p2) in enumerate(edges):
                mid = edge_midpoint(p1, p2)
                mid_g = QgsGeometry.fromPointXY(mid)
                min_dist = min(mid_g.distance(rg) for rg in road_geoms)
                edge_dists.append(min_dist)
                if min_dist < auto_threshold:
                    front_indices.append(ei)

            # Sınıflandırma
            n_edges = len(edges)
            front_set = set(front_indices)
            remaining = set(range(n_edges)) - front_set
            is_corner = len(front_indices) >= 2

            if is_corner:
                side_indices = []
                back_indices = sorted(remaining)
            else:
                if front_indices:
                    front_mids = [edge_midpoint(*edges[fi]) for fi in front_indices]
                    avg_front = QgsPointXY(
                        sum(m.x() for m in front_mids) / len(front_mids),
                        sum(m.y() for m in front_mids) / len(front_mids),
                    )
                    max_d = 0
                    back_idx = None
                    for idx in remaining:
                        mid = edge_midpoint(*edges[idx])
                        d = avg_front.distance(mid)
                        if d > max_d:
                            max_d = d
                            back_idx = idx
                    back_indices = [back_idx] if back_idx is not None else []
                    side_indices = sorted(remaining - set(back_indices))
                else:
                    side_indices = []
                    back_indices = sorted(remaining)

            # Yön
            if front_indices:
                dirs = []
                for fi in front_indices:
                    a = edge_direction_angle(*edges[fi])
                    na = (a + 90) % 360
                    dirs.append(compass_direction(na))
                front_dir = dirs[0] if len(set(dirs)) == 1 else "coklu"
            else:
                front_dir = "belirsiz"

            # Öznitelikleri güncelle
            nf = QgsFeature(fields)
            nf.setGeometry(geom)
            attrs = list(feat.attributes())
            # facade_front, facade_side, facade_back, facade_count, is_corner, front_direction
            fn = [f.name() for f in fields]
            fi_map = {n: idx for idx, n in enumerate(fn)}
            if "facade_front" in fi_map:
                attrs[fi_map["facade_front"]] = ",".join(str(x) for x in front_indices)
            if "facade_side" in fi_map:
                attrs[fi_map["facade_side"]] = ",".join(str(x) for x in side_indices)
            if "facade_back" in fi_map:
                attrs[fi_map["facade_back"]] = ",".join(str(x) for x in back_indices)
            if "facade_count" in fi_map:
                attrs[fi_map["facade_count"]] = len(front_indices)
            if "is_corner" in fi_map:
                attrs[fi_map["is_corner"]] = is_corner
            if "front_direction" in fi_map:
                attrs[fi_map["front_direction"]] = front_dir
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo("Cephe tespiti tamamlandı.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return "2_facade_detector"

    def displayName(self):
        return "2. Cephe Tespiti (Ön/Yan/Arka)"

    def group(self):
        return "Yerleşim Planı İş Akışı"

    def groupId(self):
        return "yerlesim_plani_workflow"

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Parsel kenarlarını yol ağına göre ön/yan/arka cephe olarak sınıflandırır.\n\n"
            "Parametreler:\n"
            "• Parsel katmanı: Adım 1 çıktısı (facade sütunları boş)\n"
            "• Yol ağı: UİP çizgi katmanı (yol eksenleri)\n"
            "• Mesafe eşiği: Yola bu mesafeden yakın kenarlar = ön cephe\n"
            "  → 0 girildiğinde parsel derinliğinin %60'ı kullanılır\n\n"
            "Köşe parseli kuralları (İmar Yönetmeliği):\n"
            "• 1 ön cephe → 2 yan + 1 arka bahçe\n"
            "• 2 ön cephe (köşe) → 0 yan + 2 arka bahçe\n"
            "• 3+ ön cephe → 0 yan + 1 arka bahçe"
        )

    def createInstance(self):
        return FacadeDetectorAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

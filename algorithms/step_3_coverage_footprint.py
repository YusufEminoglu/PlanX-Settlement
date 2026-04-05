# -*- coding: utf-8 -*-
"""
Adım 3: CoverageFootprint — Setback-aware bina taban alanı
Kenar bazlı setback ile yapılaşabilir alan ve TAKS sınırlı bina footprint.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys, math
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField, QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsFeature, QgsGeometry, QgsWkbTypes, QgsProcessingException,
    QgsField, QgsFields, QgsFeatureSink, QgsPointXY
)

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from core.geometry_engine import get_polygon_edges, negative_buffer_per_edge, scale_geometry_to_area


class CoverageFootprintAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    TAKS_FIELD = 'TAKS_FIELD'
    SETBACK_FRONT_FIELD = 'SETBACK_FRONT_FIELD'
    SETBACK_SIDE_FIELD = 'SETBACK_SIDE_FIELD'
    SETBACK_BACK_FIELD = 'SETBACK_BACK_FIELD'
    USE_EDGE_SETBACK = 'USE_EDGE_SETBACK'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Parsel katmanı (Adım 2 çıktısı)'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.TAKS_FIELD, self.tr('TAKS (Taban Alanı Katsayısı) sütunu'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_FRONT_FIELD, self.tr('Ön bahçe mesafesi sütunu'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_SIDE_FIELD, self.tr('Yan bahçe mesafesi sütunu'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_BACK_FIELD, self.tr('Arka bahçe mesafesi sütunu'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterBoolean(
            self.USE_EDGE_SETBACK, self.tr('Kenar bazlı setback kullan'),
            defaultValue=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Bina taban alanları')))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        taks_field = self.parameterAsString(parameters, self.TAKS_FIELD, context)
        sb_front_f = self.parameterAsString(parameters, self.SETBACK_FRONT_FIELD, context)
        sb_side_f = self.parameterAsString(parameters, self.SETBACK_SIDE_FIELD, context)
        sb_back_f = self.parameterAsString(parameters, self.SETBACK_BACK_FIELD, context)
        use_edge = self.parameterAsBool(parameters, self.USE_EDGE_SETBACK, context)

        if source is None:
            raise QgsProcessingException(self.tr("Girdi katmanı yüklenemedi."))

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(f)
        out_fields.append(QgsField('bina_alan_m2', QVariant.Double, 'double', 20, 2))
        out_fields.append(QgsField('taks_kullanim', QVariant.Double, 'double', 20, 4))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs())

        total = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom.isEmpty():
                continue

            parcel_area = geom.area()
            try:
                taks = float(feat[taks_field] or 0)
            except (TypeError, ValueError):
                taks = 0.0
            try:
                sb_front = float(feat[sb_front_f] or 5.0)
            except (TypeError, ValueError):
                sb_front = 5.0
            try:
                sb_side = float(feat[sb_side_f] or 3.0)
            except (TypeError, ValueError):
                sb_side = 3.0
            try:
                sb_back = float(feat[sb_back_f] or 3.0)
            except (TypeError, ValueError):
                sb_back = 3.0

            if taks <= 0:
                continue

            if use_edge:
                # Cephe bilgilerinden kenar bazlı setback
                fn = [f.name() for f in source.fields()]
                fi_map = {n: idx for idx, n in enumerate(fn)}
                front_str = str(feat[fi_map.get('facade_front', -1)] or '') if 'facade_front' in fi_map else ''
                side_str = str(feat[fi_map.get('facade_side', -1)] or '') if 'facade_side' in fi_map else ''
                back_str = str(feat[fi_map.get('facade_back', -1)] or '') if 'facade_back' in fi_map else ''

                front_idxs = [int(x) for x in front_str.split(',') if x.strip().isdigit()]
                side_idxs = [int(x) for x in side_str.split(',') if x.strip().isdigit()]
                back_idxs = [int(x) for x in back_str.split(',') if x.strip().isdigit()]

                edges = get_polygon_edges(geom)
                edge_setbacks = []
                for ei in range(len(edges)):
                    if ei in front_idxs:
                        edge_setbacks.append(sb_front)
                    elif ei in side_idxs:
                        edge_setbacks.append(sb_side)
                    elif ei in back_idxs:
                        edge_setbacks.append(sb_back)
                    else:
                        edge_setbacks.append(sb_side)

                buildable = negative_buffer_per_edge(geom, edge_setbacks)
            else:
                # Uniform buffer fallback
                avg_sb = (sb_front + sb_side + sb_back) / 3.0
                buildable = geom.buffer(-avg_sb, 8)

            if buildable.isEmpty():
                continue

            # TAKS kısıtı
            max_area = parcel_area * taks
            buildable_area = buildable.area()
            if buildable_area > max_area:
                building = scale_geometry_to_area(buildable, max_area)
            else:
                building = buildable

            if building.isEmpty():
                continue

            bina_alan = building.area()
            taks_kullanim = bina_alan / parcel_area if parcel_area > 0 else 0

            nf = QgsFeature(out_fields)
            nf.setGeometry(building)
            attrs = list(feat.attributes()) + [round(bina_alan, 2), round(taks_kullanim, 4)]
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo("Bina taban alanları üretildi.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return '3_coverage_footprint'
    def displayName(self):
        return '3. Bina Taban Alanı (Setback + TAKS)'
    def group(self):
        return 'Yerleşim Planı İş Akışı'
    def groupId(self):
        return 'yerlesim_plani_workflow'
    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Kenar bazlı setback ve TAKS sınırı ile bina taban alanı üretir.\n\n"
            "Parametreler:\n"
            "• TAKS sütunu: Parsel katmanındaki Taban Alanı Katsayısı değeri (0.00-1.00)\n"
            "• Ön bahçe sütunu: Parsel öznitelikteki ön bahçe mesafesi (m)\n"
            "• Yan bahçe sütunu: Yan bahçe mesafesi (m)\n"
            "• Arka bahçe sütunu: Arka bahçe mesafesi (m)\n\n"
            "Kenar bazlı setback açıkken her kenar için cephe tipine göre\n"
            "farklı mesafe uygulanır. Kapatıldığında ortalama buffer kullanılır.")
    def createInstance(self):
        return CoverageFootprintAlgorithm()
    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

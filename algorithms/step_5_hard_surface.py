# -*- coding: utf-8 -*-
"""
Adım 5: Hard Surface — Sert zemin (yürüme alanı) üretimi

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsFeature, QgsGeometry, QgsWkbTypes, QgsProcessingException,
    QgsField, QgsFields, QgsFeatureSink, QgsSpatialIndex
)

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)
from core.hard_surface_engine import generate_hard_surface, calculate_hard_surface_ratio


class HardSurfaceAlgorithm(QgsProcessingAlgorithm):
    INPUT_BUILDINGS = 'INPUT_BUILDINGS'
    INPUT_PARCELS = 'INPUT_PARCELS'
    BUFFER_DIST = 'BUFFER_DIST'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_BUILDINGS,
            self.tr('Bina katmanı (Adım 3 veya 3B çıktısı)'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_PARCELS,
            self.tr('Parsel katmanı (Adım 2 çıktısı)'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterNumber(
            self.BUFFER_DIST,
            self.tr('Buffer mesafesi (m) — bina etrafındaki yürüme alanı genişliği'),
            QgsProcessingParameterNumber.Double, 3.0,
            minValue=1.0, maxValue=6.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Sert zemin katmanı')))

    def processAlgorithm(self, parameters, context, feedback):
        b_source = self.parameterAsSource(parameters, self.INPUT_BUILDINGS, context)
        p_source = self.parameterAsSource(parameters, self.INPUT_PARCELS, context)
        buf_dist = self.parameterAsDouble(parameters, self.BUFFER_DIST, context)

        if not b_source or not p_source:
            raise QgsProcessingException(self.tr("Katmanlar yüklenemedi."))

        out_fields = QgsFields()
        out_fields.append(QgsField('parcel_fid', QVariant.Int))
        out_fields.append(QgsField('hs_area_m2', QVariant.Double, 'double', 20, 2))
        out_fields.append(QgsField('hs_ratio', QVariant.Double, 'double', 20, 4))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.MultiPolygon, p_source.sourceCrs())

        b_index = QgsSpatialIndex()
        b_feats = {}
        for bf in b_source.getFeatures():
            b_index.addFeature(bf)
            b_feats[bf.id()] = bf

        total = p_source.featureCount() or 1
        count = 0
        for i, pf in enumerate(p_source.getFeatures()):
            if feedback.isCanceled():
                break
            pg = pf.geometry()
            if pg.isEmpty():
                continue

            candidates = b_index.intersects(pg.boundingBox())
            combined_building = QgsGeometry()
            for bid in candidates:
                bg = b_feats[bid].geometry()
                if pg.intersects(bg):
                    inter = pg.intersection(bg)
                    if combined_building.isEmpty():
                        combined_building = inter
                    else:
                        combined_building = combined_building.combine(inter)

            if combined_building.isEmpty():
                continue

            # Inline buffer — QGIS 3.40 uyumlu safe call
            try:
                buffered = combined_building.buffer(float(buf_dist), int(16))
            except TypeError:
                try:
                    buffered = combined_building.buffer(float(buf_dist), int(8))
                except Exception:
                    feedback.pushInfo(f"  ⚠️ Buffer hatası, parsel {pf.id()} atlandı")
                    continue

            if buffered is None or buffered.isEmpty():
                continue

            clipped = buffered.intersection(pg)
            if clipped is None or clipped.isEmpty():
                continue

            hs = clipped.difference(combined_building)
            if hs is None or hs.isEmpty():
                continue

            hs_area = hs.area()
            p_area = pg.area()
            ratio = hs_area / p_area if p_area > 0 else 0
            nf = QgsFeature(out_fields)
            nf.setGeometry(hs)
            nf.setAttributes([pf.id(), round(hs_area, 2), round(ratio, 4)])
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            count += 1
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(f"Tamamlandı: {count} parsel için sert zemin üretildi.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return '5_hard_surface'
    def displayName(self):
        return '5. Sert Zemin (Yürüme Alanı)'
    def group(self):
        return 'Yerleşim Planı İş Akışı'
    def groupId(self):
        return 'yerlesim_plani_workflow'
    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Bina taban alanı etrafında sert zemin (yürüme/servis alanı) üretir.\n\n"
            "Formül: sert_zemin = buffer(bina, mesafe) ∩ parsel − bina\n\n"
            "Parametreler:\n"
            "• Bina katmanı: Adım 3 veya 3B çıktısı olan bina footprint poligonları\n"
            "• Parsel katmanı: Cephe bilgili parsel poligonları\n"
            "• Buffer mesafesi: Bina etrafındaki yürüme alanı genişliği (genellikle 3-4 m)\n\n"
            "Çıktı alanları:\n"
            "• parcel_fid: Kaynak parsel ID\n"
            "• hs_area_m2: Sert zemin alanı (m²)\n"
            "• hs_ratio: Sert zemin / parsel oranı")
    def createInstance(self):
        return HardSurfaceAlgorithm()
    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

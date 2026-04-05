# -*- coding: utf-8 -*-
"""Adım 4: BuildingOptimizer — Bina-parsel uyum kontrolü ve kalite raporu.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField, QgsProcessingParameterNumber,
    QgsFeature, QgsGeometry, QgsWkbTypes, QgsProcessingException,
    QgsField, QgsFields, QgsFeatureSink, QgsSpatialIndex
)

class BuildingOptimizerAlgorithm(QgsProcessingAlgorithm):
    INPUT_PARCELS = 'INPUT_PARCELS'
    INPUT_BUILDINGS = 'INPUT_BUILDINGS'
    TAKS_FIELD = 'TAKS_FIELD'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_PARCELS, self.tr('Parsel katmanı'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_BUILDINGS, self.tr('Bina katmanı'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.TAKS_FIELD, self.tr('TAKS sütunu'),
            parentLayerParameterName=self.INPUT_PARCELS, optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Kontrol rapor katmanı')))

    def processAlgorithm(self, parameters, context, feedback):
        p_source = self.parameterAsSource(parameters, self.INPUT_PARCELS, context)
        b_source = self.parameterAsSource(parameters, self.INPUT_BUILDINGS, context)
        taks_field = self.parameterAsString(parameters, self.TAKS_FIELD, context)
        if not p_source or not b_source:
            raise QgsProcessingException(self.tr("Katmanlar yüklenemedi."))

        out_fields = QgsFields()
        out_fields.append(QgsField('parcel_fid', QVariant.Int))
        out_fields.append(QgsField('parcel_area_m2', QVariant.Double, 'double', 20, 2))
        out_fields.append(QgsField('building_area_m2', QVariant.Double, 'double', 20, 2))
        out_fields.append(QgsField('taks_actual', QVariant.Double, 'double', 20, 4))
        out_fields.append(QgsField('taks_target', QVariant.Double, 'double', 20, 4))
        out_fields.append(QgsField('taks_ok', QVariant.Bool))
        out_fields.append(QgsField('geom_valid', QVariant.Bool))
        out_fields.append(QgsField('status', QVariant.String, 'string', 50))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.MultiPolygon, p_source.sourceCrs())

        # Spatial index for buildings
        b_index = QgsSpatialIndex()
        b_feats = {}
        for bf in b_source.getFeatures():
            b_index.addFeature(bf)
            b_feats[bf.id()] = bf

        total = p_source.featureCount() or 1
        ok_count = 0
        warn_count = 0
        for i, pf in enumerate(p_source.getFeatures()):
            if feedback.isCanceled():
                break
            pg = pf.geometry()
            if pg.isEmpty():
                continue
            p_area = pg.area()

            taks_target = 0.0
            if taks_field:
                try:
                    taks_target = float(pf[taks_field] or 0)
                except (TypeError, ValueError):
                    pass

            # Find buildings in this parcel
            candidates = b_index.intersects(pg.boundingBox())
            total_b_area = 0.0
            b_valid = True
            for bid in candidates:
                bg = b_feats[bid].geometry()
                if pg.intersects(bg):
                    inter = pg.intersection(bg)
                    total_b_area += inter.area()
                    if not bg.isGeosValid():
                        b_valid = False

            taks_actual = total_b_area / p_area if p_area > 0 else 0
            taks_ok = taks_actual <= taks_target + 0.01 if taks_target > 0 else True

            if taks_ok and b_valid:
                status = "OK"
                ok_count += 1
            else:
                parts = []
                if not taks_ok:
                    parts.append("TAKS_ASIM")
                if not b_valid:
                    parts.append("GEOM_HATALI")
                status = ",".join(parts)
                warn_count += 1

            nf = QgsFeature(out_fields)
            nf.setGeometry(pg)
            nf.setAttributes([
                pf.id(), round(p_area, 2), round(total_b_area, 2),
                round(taks_actual, 4), round(taks_target, 4),
                taks_ok, b_valid, status])
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(f"Kontrol tamamlandı: {ok_count} OK, {warn_count} uyarı.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return '4_building_optimizer'
    def displayName(self):
        return '4. Bina-Parsel Uyum Kontrolü'
    def group(self):
        return 'Yerleşim Planı İş Akışı'
    def groupId(self):
        return 'yerlesim_plani_workflow'
    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "TAKS aşımı, geometri geçerliliği ve uyum kontrolu yapar.\n\n"
            "Kontroller:\n"
            "• bina_alan / parsel_alan ≤ TAKS\n"
            "• Geometri geçerliliği (self-intersection)\n\n"
            "Çıktı: Her parsel için OK/TAKS_ASIM/GEOM_HATALI durumu")
    def createInstance(self):
        return BuildingOptimizerAlgorithm()
    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

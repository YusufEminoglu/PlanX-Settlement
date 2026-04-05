# -*- coding: utf-8 -*-
"""Adım 7: LandscapeGenerator — Ağaç ve peyzaj elemanları üretimi.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys, random
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsFeature, QgsGeometry, QgsWkbTypes, QgsProcessingException,
    QgsField, QgsFields, QgsFeatureSink, QgsPointXY, QgsSpatialIndex
)


class LandscapeGeneratorAlgorithm(QgsProcessingAlgorithm):
    INPUT_PARCELS = 'INPUT_PARCELS'
    INPUT_BUILDINGS = 'INPUT_BUILDINGS'
    INPUT_GREEN = 'INPUT_GREEN'
    DENSITY = 'DENSITY'
    MIN_HEIGHT = 'MIN_HEIGHT'
    MAX_HEIGHT = 'MAX_HEIGHT'
    MIN_TREE_BUILDING = 'MIN_TREE_BUILDING'
    MIN_TREE_TREE = 'MIN_TREE_TREE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_PARCELS, self.tr('Parsel katmanı'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_BUILDINGS, self.tr('Bina katmanı'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_GREEN, self.tr('Yeşil alan katmanı (opsiyonel)'),
            [QgsProcessing.TypeVectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.DENSITY, self.tr('Ağaç yoğunluğu (500m² başına)'),
            QgsProcessingParameterNumber.Integer, 1, minValue=1, maxValue=10))
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_HEIGHT, self.tr('Min ağaç yüksekliği (m)'),
            QgsProcessingParameterNumber.Double, 1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_HEIGHT, self.tr('Max ağaç yüksekliği (m)'),
            QgsProcessingParameterNumber.Double, 5.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_TREE_BUILDING, self.tr('Min ağaç-bina mesafesi (m)'),
            QgsProcessingParameterNumber.Double, 2.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_TREE_TREE, self.tr('Min ağaç-ağaç mesafesi (m)'),
            QgsProcessingParameterNumber.Double, 3.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Ağaç noktaları')))

    def processAlgorithm(self, parameters, context, feedback):
        p_source = self.parameterAsSource(parameters, self.INPUT_PARCELS, context)
        b_source = self.parameterAsSource(parameters, self.INPUT_BUILDINGS, context)
        g_source = self.parameterAsSource(parameters, self.INPUT_GREEN, context)
        density = int(self.parameterAsDouble(parameters, self.DENSITY, context))
        minH = self.parameterAsDouble(parameters, self.MIN_HEIGHT, context)
        maxH = self.parameterAsDouble(parameters, self.MAX_HEIGHT, context)
        min_tb = self.parameterAsDouble(parameters, self.MIN_TREE_BUILDING, context)
        min_tt = self.parameterAsDouble(parameters, self.MIN_TREE_TREE, context)

        if not p_source or not b_source:
            raise QgsProcessingException(self.tr("Katmanlar yüklenemedi."))

        # Tüm bina geometrilerini birleştir (exclusion zone)
        all_buildings = QgsGeometry()
        for bf in b_source.getFeatures():
            bg = bf.geometry()
            if not bg.isEmpty():
                if min_tb > 0:
                    bg = bg.buffer(min_tb, 8)
                if all_buildings.isEmpty():
                    all_buildings = bg
                else:
                    all_buildings = all_buildings.combine(bg)

        out_fields = QgsFields()
        out_fields.append(QgsField('source_fid', QVariant.Int))
        out_fields.append(QgsField('height', QVariant.Double))
        out_fields.append(QgsField('source_type', QVariant.String, 'string', 20))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Point, p_source.sourceCrs())

        total_trees = 0

        def place_trees(geom, fid, source_type):
            nonlocal total_trees
            # Binalardan uzak alan
            if not all_buildings.isEmpty():
                available = geom.difference(all_buildings)
            else:
                available = geom
            if available.isEmpty():
                return

            area = available.area()
            count = max(1, int(density * area / 500.0))
            bbox = available.boundingBox()
            placed = []

            for _ in range(count):
                for _attempt in range(500):
                    x = random.uniform(bbox.xMinimum(), bbox.xMaximum())
                    y = random.uniform(bbox.yMinimum(), bbox.yMaximum())
                    pt = QgsPointXY(x, y)
                    pt_g = QgsGeometry.fromPointXY(pt)
                    if not available.contains(pt_g):
                        continue
                    if any(pt.distance(prev) < min_tt for prev in placed):
                        continue
                    placed.append(pt)
                    break
                else:
                    continue

                h = random.uniform(minH, maxH)
                nf = QgsFeature(out_fields)
                nf.setGeometry(QgsGeometry.fromPointXY(placed[-1]))
                nf.setAttributes([fid, round(h, 1), source_type])
                sink.addFeature(nf, QgsFeatureSink.FastInsert)
                total_trees += 1

        # Parsellere ağaç yerleştir
        total = p_source.featureCount() or 1
        for i, pf in enumerate(p_source.getFeatures()):
            if feedback.isCanceled():
                break
            place_trees(pf.geometry(), pf.id(), 'parsel')
            feedback.setProgress(int((i + 1) / total * 50))

        # Yeşil alanlara ağaç yerleştir
        if g_source:
            g_total = g_source.featureCount() or 1
            for i, gf in enumerate(g_source.getFeatures()):
                if feedback.isCanceled():
                    break
                place_trees(gf.geometry(), gf.id(), 'yesil_alan')
                feedback.setProgress(50 + int((i + 1) / g_total * 50))

        feedback.pushInfo(f"Tamamlandı: {total_trees} ağaç yerleştirildi.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return '7_landscape_generator'
    def displayName(self):
        return '7. Peyzaj / Ağaç Yerleştirme'
    def group(self):
        return 'Yerleşim Planı İş Akışı'
    def groupId(self):
        return 'yerlesim_plani_workflow'
    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Parsellerin yeşil alanlarına ve park alanlarına ağaç noktaları üretir.\n\n"
            "Parametreler:\n"
            "• Parsel katmanı: Bahçe alanları için\n"
            "• Bina katmanı: Bina alanları hariç tutulur\n"
            "• Yeşil alan: Park/rekreasyon alanları (opsiyonel)\n"
            "• Yoğunluk: 500m² başına ağaç sayısı\n"
            "• Min mesafeler: Ağaç→bina ve ağaç→ağaç mesafesi\n\n"
            "Çıktı: Nokta katmanı (height, source_type öznitelikleri)")
    def createInstance(self):
        return LandscapeGeneratorAlgorithm()
    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

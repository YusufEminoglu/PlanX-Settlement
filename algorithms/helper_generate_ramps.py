# -*- coding: utf-8 -*-
"""
Helper: Rampa Üretici

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import math
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber, QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsProcessingException, QgsField, QgsFields, QgsFeatureSink, QgsPointXY,
    QgsFillSymbol, QgsSingleSymbolRenderer, QgsGradientFillSymbolLayer
)


class GenerateRampsAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    RAMP_WIDTH = 'RAMP_WIDTH'
    RAMP_LENGTH = 'RAMP_LENGTH'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('İz / Doğrultu Katmanı (Çizgi veya Poligon)'),
            [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterNumber(
            self.RAMP_WIDTH,
            self.tr('Rampa Genişliği (m)'),
            QgsProcessingParameterNumber.Double, 2.0, minValue=0.5))
        self.addParameter(QgsProcessingParameterNumber(
            self.RAMP_LENGTH,
            self.tr('Rampa Uzunluğu (m)'),
            QgsProcessingParameterNumber.Double, 5.0, minValue=1.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Rampa Sınırı')))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        width = self.parameterAsDouble(parameters, self.RAMP_WIDTH, context)
        length = self.parameterAsDouble(parameters, self.RAMP_LENGTH, context)

        if source is None:
            raise QgsProcessingException(self.tr("Katman yüklenemedi."))

        out_fields = QgsFields()
        out_fields.append(QgsField('tip', QVariant.String, 'string', 20))
        out_fields.append(QgsField('genislik', QVariant.Double))
        out_fields.append(QgsField('uzunluk', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Polygon, source.sourceCrs())

        tot = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom.isEmpty():
                continue

            # Yön ve başlangıç noktasını tespit et
            if geom.type() == QgsWkbTypes.LineGeometry:
                polyline = geom.asPolyline()
                if not polyline or len(polyline) < 2:
                    continue
                p1 = polyline[0]
                p2 = polyline[-1]
                angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
                start_p = p1
            elif geom.type() == QgsWkbTypes.PolygonGeometry:
                obb = geom.orientedMinimumBoundingBox()
                if obb and len(obb) >= 5:
                    _, _, a, _, _ = obb
                    angle = math.radians(a)
                else:
                    angle = 0
                start_p = geom.centroid().asPoint()
            else:
                start_p = geom.centroid().asPoint()
                angle = 0

            p_angle = angle + math.pi / 2
            
            p1_x = start_p.x() + (width / 2) * math.cos(p_angle)
            p1_y = start_p.y() + (width / 2) * math.sin(p_angle)
            
            p2_x = start_p.x() - (width / 2) * math.cos(p_angle)
            p2_y = start_p.y() - (width / 2) * math.sin(p_angle)
            
            p3_x = p2_x + length * math.cos(angle)
            p3_y = p2_y + length * math.sin(angle)
            
            p4_x = p1_x + length * math.cos(angle)
            p4_y = p1_y + length * math.sin(angle)

            geom_ramp = QgsGeometry.fromPolygonXY(
                [[QgsPointXY(p1_x, p1_y), QgsPointXY(p2_x, p2_y),
                  QgsPointXY(p3_x, p3_y), QgsPointXY(p4_x, p4_y), QgsPointXY(p1_x, p1_y)]]
            )

            nf = QgsFeature(out_fields)
            nf.setGeometry(geom_ramp)
            nf.setAttributes(['Rampa', round(width, 2), round(length, 2)])
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            feedback.setProgress(int((i + 1) / tot * 100))

        return {self.OUTPUT: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        layer = context.getMapLayer(list(context.layersToLoadOnCompletion().keys())[0])
        if layer:
            # Degrade efekti ile yokuş gösterimi
            symbol = QgsFillSymbol.createSimple({'color': '220,220,220,255', 'outline_color': '50,50,50'})
            gradient = QgsGradientFillSymbolLayer()
            gradient.setColor(QCoreApplication.translate('Processing', '150,150,150,255'))
            gradient.setColor2(QCoreApplication.translate('Processing', '240,240,240,255'))
            symbol.changeSymbolLayer(0, gradient)
            
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()
        return {}

    def name(self):
        return 'helper_ramps'
    def displayName(self):
        return 'H2. Rampa Üretici'
    def group(self):
        return 'Yerleşim Planı Yardımcılar'
    def groupId(self):
        return 'yerlesim_plani_yardimcilar'
    def shortHelpString(self):
        return self.tr("Bir çizgi veya poligon doğrultusunda 2 Boyutlu rampa izdüşümü üretir.")
    def createInstance(self):
        return GenerateRampsAlgorithm()
    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

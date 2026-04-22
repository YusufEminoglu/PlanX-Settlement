# -*- coding: utf-8 -*-
"""
Helper: Merdiven Üretici

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
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingException,
    QgsField,
    QgsFields,
    QgsFeatureSink,
    QgsPointXY,
    QgsFillSymbol,
    QgsLinePatternFillSymbolLayer,
    QgsSingleSymbolRenderer,
)


class GenerateStairsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    STAIR_WIDTH = "STAIR_WIDTH"
    STAIR_TREAD = "STAIR_TREAD"
    STAIR_COUNT = "STAIR_COUNT"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("İz / Doğrultu Katmanı (Çizgi veya Poligon)"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STAIR_WIDTH,
                self.tr("Merdiven Genişliği (m)"),
                QgsProcessingParameterNumber.Double,
                2.0,
                minValue=0.5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STAIR_TREAD,
                self.tr("Basamak Derinliği / Basar (m)"),
                QgsProcessingParameterNumber.Double,
                0.3,
                minValue=0.15,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STAIR_COUNT,
                self.tr("Basamak Sayısı"),
                QgsProcessingParameterNumber.Integer,
                10,
                minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Merdiven Sınırı"))
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        width = self.parameterAsDouble(parameters, self.STAIR_WIDTH, context)
        tread = self.parameterAsDouble(parameters, self.STAIR_TREAD, context)
        count = self.parameterAsInt(parameters, self.STAIR_COUNT, context)

        if source is None:
            raise QgsProcessingException(self.tr("Katman yüklenemedi."))

        out_fields = QgsFields()
        out_fields.append(QgsField("tip", QVariant.String, "string", 20))
        out_fields.append(QgsField("genislik", QVariant.Double))
        out_fields.append(QgsField("uzunluk", QVariant.Double))
        out_fields.append(QgsField("basamak_sayisi", QVariant.Int))

        total_length = tread * count

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            QgsWkbTypes.Polygon,
            source.sourceCrs(),
        )

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

            # Basit dikdörtgen oluştur: start_p'den angle yönünde total_length kadar uzanır
            # Genişliği (width) angle'a dik eksende dengeli dağılır
            p_angle = angle + math.pi / 2

            p1_x = start_p.x() + (width / 2) * math.cos(p_angle)
            p1_y = start_p.y() + (width / 2) * math.sin(p_angle)

            p2_x = start_p.x() - (width / 2) * math.cos(p_angle)
            p2_y = start_p.y() - (width / 2) * math.sin(p_angle)

            p3_x = p2_x + total_length * math.cos(angle)
            p3_y = p2_y + total_length * math.sin(angle)

            p4_x = p1_x + total_length * math.cos(angle)
            p4_y = p1_y + total_length * math.sin(angle)

            stair_geom = QgsGeometry.fromPolygonXY(
                [
                    [
                        QgsPointXY(p1_x, p1_y),
                        QgsPointXY(p2_x, p2_y),
                        QgsPointXY(p3_x, p3_y),
                        QgsPointXY(p4_x, p4_y),
                        QgsPointXY(p1_x, p1_y),
                    ]
                ]
            )

            nf = QgsFeature(out_fields)
            nf.setGeometry(stair_geom)
            nf.setAttributes(
                ["Merdiven", round(width, 2), round(total_length, 2), count]
            )
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            feedback.setProgress(int((i + 1) / tot * 100))

        return {self.OUTPUT: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        layer = context.getMapLayer(list(context.layersToLoadOnCompletion().keys())[0])
        if layer:
            symbol = QgsFillSymbol.createSimple(
                {"color": "200,200,200,100", "outline_color": "50,50,50"}
            )

            # Merdiven basamakları (Hatch)
            hatch = QgsLinePatternFillSymbolLayer()
            hatch.setAngle(90)  # Yol doğrultusuna dik çizgi deseni varsayılan
            hatch.setDistance(1.0)  # Basamak aralığı (map units kullanacağız)
            hatch.setDistanceUnit(QgsWkbTypes.RenderMapUnits)
            symbol.appendSymbolLayer(hatch)

            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()
        return {}

    def name(self):
        return "helper_stairs"

    def displayName(self):
        return "H1. Merdiven Üretici"

    def group(self):
        return "Yerleşim Planı Yardımcılar"

    def groupId(self):
        return "yerlesim_plani_yardimcilar"

    def shortHelpString(self):
        return self.tr(
            "Bir çizgi veya poligon doğrultusunda 2 Boyutlu merdiven izdüşümü üretir."
        )

    def createInstance(self):
        return GenerateStairsAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

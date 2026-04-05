# -*- coding: utf-8 -*-
"""
Helper: Yaya Geçidi Üretici

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber, QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsProcessingException, QgsField, QgsFields, QgsFeatureSink,
    QgsLineSymbol, QgsSimpleLineSymbolLayer, QgsSingleSymbolRenderer, QgsWkbTypes
)


class PedestrianCrossingAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    CROSSING_WIDTH = 'CROSSING_WIDTH'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Yol Çizgisi veya Kavşak Çizgisi'),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterNumber(
            self.CROSSING_WIDTH,
            self.tr('Yaya Geçidi Genişliği (m) (Dash line sembolojisi için çizgi kalınlığı)'),
            QgsProcessingParameterNumber.Double, 5.0, minValue=2.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Yaya Geçidi (Çizgi)')))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        width = self.parameterAsDouble(parameters, self.CROSSING_WIDTH, context)

        if source is None:
            raise QgsProcessingException(self.tr("Katman yüklenemedi."))

        out_fields = QgsFields()
        out_fields.append(QgsField('tip', QVariant.String, 'string', 20))
        out_fields.append(QgsField('genislik', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.LineString, source.sourceCrs())

        tot = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom.isEmpty():
                continue

            nf = QgsFeature(out_fields)
            nf.setGeometry(geom)
            nf.setAttributes(['Yaya Gecidi', round(width, 2)])
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            feedback.setProgress(int((i + 1) / tot * 100))

        return {self.OUTPUT: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        layer = context.getMapLayer(list(context.layersToLoadOnCompletion().keys())[0])
        if layer:
            # Çizgi stilini MapUnits (metre) cinsinden kalınlaştır ve Dash (Yaya Geçidi Zebra) yap
            symbol = QgsLineSymbol.createSimple({
                'color': '230,230,230,255',
                'line_style': 'dash',
                'line_width': '5',  # Varsayılan 5 metre genişlik
                'customdash': '3;3' # 3 birim dolu, 3 birim boş
            })
            symbol.setOutputUnit(QgsWkbTypes.RenderMapUnits)
            
            # Parametrik width alanına bağlanabilir ama processing sonucunda QGIS'te map unit olarak render edilmesi yeterli
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()
        return {}

    def name(self):
        return 'helper_pedestrian_crossing'
    def displayName(self):
        return 'H3. Yaya Geçidi Üretici'
    def group(self):
        return 'Yerleşim Planı Yardımcılar'
    def groupId(self):
        return 'yerlesim_plani_yardimcilar'
    def shortHelpString(self):
        return self.tr(
            "Bir çizgi katmanını alarak 'Yaya Geçidi' olarak işaretler.\n"
            "Çıktı bir çizgi (LineString) olur. QGIS sembolojisi üzerinden\n"
            "çizgi kalınlığını 'genislik' sütunuyla eşleştirip\n"
            "Dash (Kesikli) Çizgi deseni uygulayarak gerçekçi görünüm elde edebilirsiniz.")
    def createInstance(self):
        return PedestrianCrossingAlgorithm()
    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

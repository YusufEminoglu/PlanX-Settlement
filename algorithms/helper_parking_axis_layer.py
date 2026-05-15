# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Özel Yardımcı Araç: Otopark Çizim Aksı (Geçici Katman)
"""
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsField, QgsFields, QgsCoordinateReferenceSystem,
    QgsProject, QgsVectorLayer, QgsEditorWidgetSetup
)

class HelperParkingAxisLayerAlgorithm(QgsProcessingAlgorithm):
    # Bu algoritmada QgsProcessingParameterFeatureSink YERİNE katmanı manuel oluşturacağız
    # ki attribute form widget'larını (dropdown) ayarlayabilelim.

    def initAlgorithm(self, config=None):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        # Geçici katman oluştur. EPSG:5253 istemişti kullanıcı.
        crs = QgsCoordinateReferenceSystem("EPSG:5253")

        layer = QgsVectorLayer(f"LineString?crs={crs.authid()}", "Otopark Çizim Aksı (Geçici)", "memory")
        if not layer.isValid():
            feedback.reportError("Katman oluşturulamadı!")
            return {}

        layer.startEditing()
        pr = layer.dataProvider()
        
        # Alanları ekle
        fields = QgsFields()
        fields.append(QgsField('aks_id', QVariant.Int))
        fields.append(QgsField('park_acisi', QVariant.String, 'string', 50))
        fields.append(QgsField('olusturma_yonu', QVariant.String, 'string', 50))
        fields.append(QgsField('hücre_bosluk', QVariant.Double, 'double', 10, 2))
        fields.append(QgsField('aks_mesafesi', QVariant.Double, 'double', 10, 2))
        
        pr.addAttributes(fields.toList())
        layer.commitChanges()

        # Widget ayarlamaları (Drop-down vb.)
        idx_angle = layer.fields().indexOf('park_acisi')
        setup_angle = QgsEditorWidgetSetup('ValueMap', {
            'map': {'90° (Dik)': '0', '60° (Açılı)': '1', '45° (Açılı)': '2', '0° (Paralel Park)': '3'}
        })
        layer.setEditorWidgetSetup(idx_angle, setup_angle)

        idx_side = layer.fields().indexOf('olusturma_yonu')
        setup_side = QgsEditorWidgetSetup('ValueMap', {
            'map': {'Sağ': '0', 'Sol': '1', 'Her İki Taraf': '2'}
        })
        layer.setEditorWidgetSetup(idx_side, setup_side)
        
        # aks_mesafesi default'u 0.0 olsun
        idx_distance = layer.fields().indexOf('aks_mesafesi')
        setup_dist = QgsEditorWidgetSetup('Range', {
            'Min': 0.0, 'Max': 5.0, 'Step': 0.1, 'AllowNull': False
        })
        layer.setEditorWidgetSetup(idx_distance, setup_dist)
        
        # Projeye ekle
        QgsProject.instance().addMapLayer(layer)
        
        feedback.pushInfo(self.tr("Geçici aks çizim katmanı EPSG:5253 olarak oluşturuldu ve attribute formları ayarlandı."))

        return {}

    def name(self):
        return 'helper_parking_axis_layer'

    def displayName(self):
        return 'Çizgi otoparkı oluşturmak için geçici aks katmanı oluştur'

    def group(self):
        return 'Otopark Araçları'

    def groupId(self):
        return 'parking_helpers'

    def shortHelpString(self):
        return self.tr(
            "Manuel çizgi üzerinden otopark oluşturmanızı sağlamak için "
            "işlem yapabileceğiniz geçici bir Scratch (Memory) çizgi katmanı (EPSG:5253) oluşturur.\n\n"
            "Oluşan katmanın Öznitelik Tablosunda park açısı ve yönü gibi alanlar form yapısında hazırdır.\n"
            "Çizim yaparken drop-down menülerden seçim yapabilirsiniz.")

    def createInstance(self):
        return HelperParkingAxisLayerAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

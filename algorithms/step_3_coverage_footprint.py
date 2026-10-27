# -*- coding: utf-8 -*-
"""
Adım 3.2: Ayrık Nizam Çözümü
Kenar bazlı (cephe bilinçli) setback + TAKS kısıtı ile ayrık nizam bina footprint üretimi.

Her parsel için bağımsız bir bina taban alanı üretilir.
Ön, yan ve arka bahçe mesafeleri adım 2'de hesaplanan cephe kenarlarına uygulanır.

Geliştirici: Geophilo
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField, QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsFeature, QgsProcessingException,
    QgsField, QgsFields, QgsFeatureSink
)

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from core.geometry_engine import scale_geometry_to_area
from core.footprint_engine import (
    NIZAM_DETACHED,
    build_nizam_configuration,
    feature_facade_indices,
    fit_footprint_to_target_area,
)


def _float(val, default=0.0):
    """TEXT sütunlardan güvenli float dönüşümü."""
    try:
        return float(str(val).strip().replace(',', '.')) if val not in (None, '', 'NULL') else default
    except (TypeError, ValueError):
        return default


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
            self.TAKS_FIELD, self.tr('TAKS sütunu (0.00–1.00 arası değer)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_FRONT_FIELD, self.tr('Ön bahçe mesafesi sütunu (m)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_SIDE_FIELD, self.tr('Yan bahçe mesafesi sütunu (m)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_BACK_FIELD, self.tr('Arka bahçe mesafesi sütunu (m)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterBoolean(
            self.USE_EDGE_SETBACK,
            self.tr('Cephe bilinçli setback kullan (Adım 2 facade_front/side/back alanları gerekir)'),
            defaultValue=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Ayrık nizam bina taban alanları')))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        taks_field = self.parameterAsString(parameters, self.TAKS_FIELD, context)
        sb_front_f = self.parameterAsString(parameters, self.SETBACK_FRONT_FIELD, context)
        sb_side_f = self.parameterAsString(parameters, self.SETBACK_SIDE_FIELD, context)
        sb_back_f = self.parameterAsString(parameters, self.SETBACK_BACK_FIELD, context)
        use_edge = self.parameterAsBool(parameters, self.USE_EDGE_SETBACK, context)

        if source is None:
            raise QgsProcessingException(self.tr("Girdi katmanı yüklenemedi."))

        field_index_map = {f.name(): idx for idx, f in enumerate(source.fields())}

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
            taks = _float(feat[taks_field], 0.0)
            sb_front = _float(feat[sb_front_f], 5.0)
            sb_side = _float(feat[sb_side_f], 3.0)
            sb_back = _float(feat[sb_back_f], 3.0)

            if taks <= 0:
                feedback.pushInfo(f"Parsel {feat.id()}: TAKS=0, atlandı.")
                continue

            if use_edge:
                facade_indices = feature_facade_indices(feat, field_index_map)
                config = build_nizam_configuration(
                    geom, facade_indices,
                    sb_front, sb_side, sb_back,
                    NIZAM_DETACHED,
                )
                building = fit_footprint_to_target_area(
                    geom,
                    config['edge_setbacks'],
                    parcel_area * taks,
                    config['adjustable_indices'],
                )
            else:
                avg_sb = (sb_front + sb_side + sb_back) / 3.0
                building = geom.buffer(-avg_sb, 8)
                if not building.isEmpty() and building.area() > parcel_area * taks:
                    building = scale_geometry_to_area(building, parcel_area * taks)

            if building.isEmpty():
                continue

            bina_alan = building.area()
            taks_kullanim = bina_alan / parcel_area if parcel_area > 0 else 0

            nf = QgsFeature(out_fields)
            nf.setGeometry(building)
            nf.setAttributes(list(feat.attributes()) + [
                round(bina_alan, 2),
                round(taks_kullanim, 4),
            ])
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo("Ayrık nizam bina taban alanları üretildi.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return '3_2_ayrik_nizam'

    def displayName(self):
        return '3.2. Ayrık Nizam Çözümü (Setback + TAKS)'

    def group(self):
        return 'Yerleşim Planı İş Akışı'

    def groupId(self):
        return 'yerlesim_plani_workflow'

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Geophilo\n\n"
            "Ayrık nizam (A nizam) için kenar-bilinçli bahçe mesafesi ve TAKS kısıtı\n"
            "uygulayarak her parselde bağımsız bir bina taban alanı üretir.\n\n"
            "Önkoşul:\n"
            "• Adım 2 (Cephe Tespiti) çıktısı — cephe sınıflandırması için\n"
            "  facade_front, facade_side, facade_back sütunları gerekir.\n\n"
            "Parametreler:\n"
            "• TAKS sütunu: Parsel bazında Taban Alanı Katsayısı (0.00–1.00)\n"
            "• Ön bahçe (m): Yola bakan cephe ile bina arasındaki minimum mesafe\n"
            "• Yan bahçe (m): Parsel yan sınırları ile bina arasındaki mesafe\n"
            "• Arka bahçe (m): Arka parselle arasındaki mesafe\n"
            "• Cephe bilinçli: Adım 2'nin cephe sınıflandırmasını kullan (önerilir)\n\n"
            "Değer Formatı:\n"
            "• Tüm sayısal değerlerin metin (text) formatlı sütunlarda olması desteklenir.\n"
            "• TAKS değeri 0.00–1.00 aralığında olmalıdır (örn. 0.40 = %40 TAKS).\n\n"
            "Çıktı: Her parsel için ayrı bir bina taban alanı geometrisi.\n"
            "Birleştirme yapılmaz, her bina bağımsız bir poligondur.")

    def createInstance(self):
        return CoverageFootprintAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

# -*- coding: utf-8 -*-
"""
Adım 4.1: Bina Makroform Yerleştirme — Şablon katmandan bina formu sığdırma

Geliştirici: Geophilo
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterVectorLayer, QgsProcessingParameterEnum,
    QgsProcessingParameterNumber, QgsProcessingParameterBoolean,
    QgsFeature, QgsGeometry, QgsWkbTypes, QgsProcessingException,
    QgsField, QgsFields, QgsFeatureSink, QgsFeatureRequest,
    QgsVectorLayer
)

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from core.parcel_randomizer import _LCG

from core.macroform_engine import TemplateBuilding, match_template_to_bbox, fit_template_to_bbox
from core.geometry_engine import polygon_aspect_ratio, polygon_compactness, oriented_minimum_bounding_box


def _load_templates_from_layer(layer, selected_only=False):
    """
    Yüklü bir QgsVectorLayer'dan şablon bina formları yükler.
    File-path gerektirmez; haritada açık her katman kullanılabilir.

    Args:
        layer: QgsVectorLayer — polinom geometrili şablon katmanı
        selected_only: bool — True ise yalnızca seçili nesneleri kullan

    Returns:
        list[TemplateBuilding]
    """
    if layer is None or not layer.isValid():
        return []

    field_names = [f.name() for f in layer.fields()]
    templates = []

    if selected_only and layer.selectedFeatureCount() > 0:
        features = layer.selectedFeatures()
    else:
        features = layer.getFeatures()

    for feat in features:
        geom = feat.geometry()
        if geom.isEmpty():
            continue

        form_type = ""
        min_a = 0.0
        max_a = 99999.0

        if 'form_tipi' in field_names:
            form_type = str(feat['form_tipi'] or "")
        if 'min_alan_m2' in field_names:
            try:
                min_a = float(feat['min_alan_m2'] or 0)
            except (TypeError, ValueError):
                pass
        if 'max_alan_m2' in field_names:
            try:
                max_a = float(feat['max_alan_m2'] or 99999)
            except (TypeError, ValueError):
                pass

        templates.append(TemplateBuilding(geom, form_type, min_a, max_a))

    return templates


class BuildingMacroformAlgorithm(QgsProcessingAlgorithm):
    INPUT_BUILDINGS = 'INPUT_BUILDINGS'
    TEMPLATE_LAYER  = 'TEMPLATE_LAYER'
    SELECTED_ONLY   = 'SELECTED_ONLY'
    DIVERSITY       = 'DIVERSITY'
    MAX_UTILIZATION = 'MAX_UTILIZATION'
    ROTATE_TO_FIT   = 'ROTATE_TO_FIT'
    RANDOM_SEED     = 'RANDOM_SEED'
    OUTPUT          = 'OUTPUT'

    def initAlgorithm(self, config=None):
        # ── Giriş: bina taban alanı katmanı ──────────────────────────────
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_BUILDINGS,
            self.tr('Bina taban alanı katmanı (Adım 3.x çıktısı)'),
            [QgsProcessing.TypeVectorPolygon]))

        # ── Şablon katmanı: haritadan seçilir, dosya yolu gerekmez ───────
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.TEMPLATE_LAYER,
            self.tr('Şablon bina formları katmanı (açık katmanlardan seçin)'),
            [QgsProcessing.TypeVectorPolygon]))

        # ── Seçili nesneler kısıtı ────────────────────────────────────────
        self.addParameter(QgsProcessingParameterBoolean(
            self.SELECTED_ONLY,
            self.tr('Şablon katmanda yalnızca seçili nesneleri kullan'),
            defaultValue=False))

        # ── Form seçim ve ölçekleme parametreleri ─────────────────────────
        self.addParameter(QgsProcessingParameterEnum(
            self.DIVERSITY,
            self.tr('Form çeşitlilik seviyesi'),
            options=[
                self.tr('Düşük — en uyumlu form'),
                self.tr('Orta — yarı rastgele'),
                self.tr('Yüksek — tam rastgele')
            ],
            defaultValue=1))

        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_UTILIZATION,
            self.tr('Maks alan kullanımı (%)'),
            QgsProcessingParameterNumber.Double,
            defaultValue=95.0,
            minValue=50.0,
            maxValue=100.0))

        self.addParameter(QgsProcessingParameterBoolean(
            self.ROTATE_TO_FIT,
            self.tr('Şablonu sığdırmak için döndür'),
            defaultValue=True))

        self.addParameter(QgsProcessingParameterNumber(
            self.RANDOM_SEED,
            self.tr('Rastgele tohum (0 = her seferinde farklı)'),
            QgsProcessingParameterNumber.Integer,
            defaultValue=0,
            minValue=0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Makroformlu binalar')))

    # ─────────────────────────────────────────────────────────────────────
    def processAlgorithm(self, parameters, context, feedback):
        source       = self.parameterAsSource(parameters, self.INPUT_BUILDINGS, context)
        tmpl_layer   = self.parameterAsVectorLayer(parameters, self.TEMPLATE_LAYER, context)
        selected_only= self.parameterAsBool(parameters, self.SELECTED_ONLY, context)
        diversity_idx= self.parameterAsInt(parameters, self.DIVERSITY, context)
        max_util     = self.parameterAsDouble(parameters, self.MAX_UTILIZATION, context) / 100.0
        rotate       = self.parameterAsBool(parameters, self.ROTATE_TO_FIT, context)
        seed         = self.parameterAsInt(parameters, self.RANDOM_SEED, context)

        diversity_map = {0: "Low", 1: "Medium", 2: "High"}
        diversity = diversity_map.get(diversity_idx, "Medium")

        if source is None:
            raise QgsProcessingException(self.tr("Girdi katmanı yüklenemedi."))

        # Şablonları yüklü katmandan al
        templates = _load_templates_from_layer(tmpl_layer, selected_only)
        if not templates:
            raise QgsProcessingException(
                self.tr("Şablon katmanında uygun polygon bulunamadı. "
                        "'Seçili nesneler' seçeneği aktifse en az bir nesne seçili olmalı."))

        feedback.pushInfo(f"{len(templates)} şablon form yüklendi"
                          + (" (seçili nesnelerden)" if selected_only else "") + ".")

        rng = _LCG(seed if seed > 0 else 42)

        # Çıktı alanları
        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(f)
        out_fields.append(QgsField('form_tipi',     QVariant.String, 'string', 50))
        out_fields.append(QgsField('macroform_alan_m2', QVariant.Double, 'double', 20, 2))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs())

        total = source.featureCount() or 1
        placed = 0

        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            bbox_geom = feat.geometry()
            if bbox_geom.isEmpty():
                continue

            target_area = bbox_geom.area() * max_util
            tmpl = match_template_to_bbox(bbox_geom, templates, diversity, target_area, rng)

            if tmpl is None:
                # Fallback: orijinal bbox'ı kullan
                nf = QgsFeature(out_fields)
                nf.setGeometry(bbox_geom)
                nf.setAttributes(list(feat.attributes()) + ['orijinal', round(bbox_geom.area(), 2)])
                sink.addFeature(nf, QgsFeatureSink.FastInsert)
                continue

            fitted = fit_template_to_bbox(tmpl, bbox_geom, max_util, rotate)
            if fitted is None or fitted.isEmpty():
                nf = QgsFeature(out_fields)
                nf.setGeometry(bbox_geom)
                nf.setAttributes(list(feat.attributes()) + ['fallback', round(bbox_geom.area(), 2)])
                sink.addFeature(nf, QgsFeatureSink.FastInsert)
                continue

            nf = QgsFeature(out_fields)
            nf.setGeometry(fitted)
            nf.setAttributes(list(feat.attributes()) + [tmpl.form_type, round(fitted.area(), 2)])
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            placed += 1
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(f"Tamamlandı: {placed} / {total} bina için makroform uygulandı.")
        return {self.OUTPUT: dest_id}

    # ── Metadata ──────────────────────────────────────────────────────────
    def name(self):
        return '4_1_bina_makroform'

    def displayName(self):
        return '4.1. Bina Makroform Yerleştirme'

    def group(self):
        return 'Yerleşim Planı İş Akışı'

    def groupId(self):
        return 'yerlesim_plani_workflow'

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Geophilo\n\n"
            "Şablon bina formlarını (L, U, T, I vb.) buildable bbox'a sığdırır.\n\n"
            "Şablon Katmanı:\n"
            "• QGIS'te açık herhangi bir polygon katmanını şablon olarak seçin\n"
            "• 'form_tipi', 'min_alan_m2', 'max_alan_m2' alanları isteğe bağlıdır\n"
            "• Sadece belirli şablonları kullanmak için önce seçin, 'Seçili nesneler' kutucuğunu işaretleyin\n\n"
            "Parametreler:\n"
            "• Çeşitlilik: Düşük=en uyumlu, Yüksek=geniş küme\n"
            "• Alan kullanımı: Bbox alanının max %%'si\n"
            "• Döndürme: Şablonu bbox'a hizalamak için\n\n"
            "Eşleştirme: Şablon aspect ratio ile bbox aspect ratio\n"
            "karşılaştırılır, en uyumlu alt kümeden rastgele seçilir.\n\n"
            "Opsiyonel adımdır — kullanılmazsa setback bina formu kalır.")

    def createInstance(self):
        return BuildingMacroformAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

# -*- coding: utf-8 -*-
"""
Adım 3B: Building Macroform — Şablon veya dinamik bina formu yerleştirme

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

import os, sys, random
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsFeature,
    QgsProcessingException,
    QgsField,
    QgsFields,
    QgsFeatureSink,
)

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from core.macroform_engine import (
    load_templates,
    match_template_to_bbox,
    fit_template_to_bbox,
)


class BuildingMacroformAlgorithm(QgsProcessingAlgorithm):
    INPUT_BUILDINGS = "INPUT_BUILDINGS"
    INPUT_PARCELS = "INPUT_PARCELS"
    TEMPLATE_FILE = "TEMPLATE_FILE"
    DIVERSITY = "DIVERSITY"
    MAX_UTILIZATION = "MAX_UTILIZATION"
    ROTATE_TO_FIT = "ROTATE_TO_FIT"
    RANDOM_SEED = "RANDOM_SEED"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_BUILDINGS,
                self.tr("Bina taban alanı katmanı (Adım 3 çıktısı)"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_PARCELS,
                self.tr("Parsel katmanı"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.TEMPLATE_FILE,
                self.tr("Şablon bina formları (.gpkg)"),
                extension="gpkg",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DIVERSITY,
                self.tr("Form çeşitlilik seviyesi"),
                options=["Düşük", "Orta", "Yüksek"],
                defaultValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_UTILIZATION,
                self.tr("Maks alan kullanımı (%)"),
                QgsProcessingParameterNumber.Double,
                95.0,
                minValue=50.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ROTATE_TO_FIT, self.tr("Sığdırmak için döndür"), defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RANDOM_SEED,
                self.tr("Rastgele tohum (0=rastgele)"),
                QgsProcessingParameterNumber.Integer,
                0,
                minValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Makroformlu binalar")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT_BUILDINGS, context)
        gpkg_path = self.parameterAsString(parameters, self.TEMPLATE_FILE, context)
        diversity_idx = self.parameterAsInt(parameters, self.DIVERSITY, context)
        max_util = (
            self.parameterAsDouble(parameters, self.MAX_UTILIZATION, context) / 100.0
        )
        rotate = self.parameterAsBool(parameters, self.ROTATE_TO_FIT, context)
        seed = self.parameterAsInt(parameters, self.RANDOM_SEED, context)

        diversity_map = {0: "Low", 1: "Medium", 2: "High"}
        diversity = diversity_map.get(diversity_idx, "Medium")

        if source is None:
            raise QgsProcessingException(self.tr("Girdi katmanı yüklenemedi."))

        templates = load_templates(gpkg_path)
        if not templates:
            raise QgsProcessingException(self.tr("Şablon dosyasında form bulunamadı."))
        feedback.pushInfo(f"{len(templates)} şablon form yüklendi.")

        rng = random.Random(seed if seed > 0 else None)

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(f)
        out_fields.append(QgsField("form_tipi", QVariant.String, "string", 50))
        out_fields.append(
            QgsField("macroform_alan_m2", QVariant.Double, "double", 20, 2)
        )

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            source.wkbType(),
            source.sourceCrs(),
        )

        total = source.featureCount() or 1
        placed = 0
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            bbox_geom = feat.geometry()
            if bbox_geom.isEmpty():
                continue

            target_area = bbox_geom.area() * max_util
            tmpl = match_template_to_bbox(
                bbox_geom, templates, diversity, target_area, rng
            )
            if tmpl is None:
                # Fallback: orijinal bbox geometrisini kullan
                nf = QgsFeature(out_fields)
                nf.setGeometry(bbox_geom)
                attrs = list(feat.attributes()) + [
                    "orijinal",
                    round(bbox_geom.area(), 2),
                ]
                nf.setAttributes(attrs)
                sink.addFeature(nf, QgsFeatureSink.FastInsert)
                continue

            fitted = fit_template_to_bbox(tmpl, bbox_geom, max_util, rotate)
            if fitted is None or fitted.isEmpty():
                nf = QgsFeature(out_fields)
                nf.setGeometry(bbox_geom)
                attrs = list(feat.attributes()) + [
                    "fallback",
                    round(bbox_geom.area(), 2),
                ]
                nf.setAttributes(attrs)
                sink.addFeature(nf, QgsFeatureSink.FastInsert)
                continue

            nf = QgsFeature(out_fields)
            nf.setGeometry(fitted)
            attrs = list(feat.attributes()) + [tmpl.form_type, round(fitted.area(), 2)]
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            placed += 1
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(f"Tamamlandı: {placed} bina makroform uygulandı.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return "3b_building_macroform"

    def displayName(self):
        return "3B. Bina Makroform Yerleştirme (Opsiyonel)"

    def group(self):
        return "Yerleşim Planı İş Akışı"

    def groupId(self):
        return "yerlesim_plani_workflow"

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Şablon kütüphanesinden bina formlarını buildable bbox'a sığdırır.\n\n"
            "Parametreler:\n"
            "• Şablon dosyası: .gpkg formatında bina formları (L, U, T, I vb.)\n"
            "• Çeşitlilik: Düşük=en uyumlu, Yüksek=geniş küme\n"
            "• Alan kullanımı: Bbox alanının max %'si\n"
            "• Döndürme: Formu bbox'a hizalamak için\n\n"
            "Eşleştirme: Template aspect ratio ile bbox aspect ratio\n"
            "karşılaştırılır, en uyumlu alt kümeden rastgele seçilir.\n\n"
            "Opsiyonel adımdır — kullanılmazsa klask setback bina kalır."
        )

    def createInstance(self):
        return BuildingMacroformAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

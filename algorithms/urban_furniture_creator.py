# -*- coding: utf-8 -*-
"""
Kentsel Donatı Katmanı Oluşturucu
Yerleşim planında kullanılacak kent mobilyaları için hazır stillenmiş
nokta katmanı üretir. Öğrenci bu katmanı açıp elemanları haritaya yerleştirir.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

import os
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingException,
    QgsField,
    QgsFields,
    QgsFeatureSink,
    QgsPointXY,
    QgsMarkerSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsEditorWidgetSetup,
)

# ── Kent mobilyası kataloğu ──────────────────────────────────────────
FURNITURE_CATALOG = [
    ("bank", "Oturma Bankı", "oturma", "furniture_bench.svg", "#8B7355", 5.0),
    (
        "aydinlatma",
        "Aydınlatma Direği",
        "aydinlatma",
        "furniture_light.svg",
        "#FFD700",
        4.0,
    ),
    ("cop_kovasi", "Çöp Kovası", "temizlik", "furniture_trash.svg", "#4A5568", 3.5),
    (
        "yangin_muslubu",
        "Yangın Musluğu",
        "guvenlik",
        "furniture_hydrant.svg",
        "#E53E3E",
        4.0,
    ),
    (
        "agac_donati",
        "Süs Ağacı / Ağaç (donatı)",
        "peyzaj",
        "furniture_tree.svg",
        "#38A169",
        6.0,
    ),
    (
        "bilgi_panosu",
        "Bilgi Panosu / Tabela",
        "bilgilendirme",
        "furniture_infoboard.svg",
        "#4A5568",
        4.0,
    ),
    ("cesme", "Çeşme / Su Öğesi", "peyzaj", "furniture_fountain.svg", "#3182CE", 5.0),
    (
        "bisiklet_park",
        "Bisiklet Parkı",
        "ulasim",
        "furniture_bench.svg",
        "#DD6B20",
        4.5,
    ),
    (
        "elektrik_sarj",
        "EV Şarj İstasyonu",
        "ulasim",
        "furniture_light.svg",
        "#38B2AC",
        4.5,
    ),
    (
        "oyun_alani",
        "Çocuk Oyun Alanı İşareti",
        "rekreasyon",
        "furniture_fountain.svg",
        "#ED8936",
        7.0,
    ),
    ("araba", "Araba", "ulasim", "furniture_car.svg", "#607D8B", 15.0),
    (
        "trafik_isigi",
        "Trafik Işığı",
        "ulasim",
        "furniture_traffic_light.svg",
        "#333333",
        3.0,
    ),
]


class UrbanFurnitureAlgorithm(QgsProcessingAlgorithm):
    CRS = "CRS"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS,
                self.tr("Koordinat sistemi — projenizle aynı olmalı"),
                defaultValue="EPSG:5253",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Kentsel donatı katmanı (hazır stillenmiş)")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        crs = self.parameterAsCrs(parameters, self.CRS, context)

        fields = QgsFields()
        fields.append(QgsField("donati_id", QVariant.String, "string", 30))
        fields.append(QgsField("donati_adi", QVariant.String, "string", 60))
        fields.append(QgsField("kategori", QVariant.String, "string", 30))
        fields.append(QgsField("svg_dosya", QVariant.String, "string", 255))
        fields.append(QgsField("renk", QVariant.String, "string", 10))
        fields.append(QgsField("boyut_mm", QVariant.Double))
        fields.append(QgsField("aciklama", QVariant.String, "string", 200))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields, QgsWkbTypes.Point, crs
        )
        if sink is None:
            raise QgsProcessingException(self.tr("Çıktı katmanı oluşturulamadı."))

        icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")

        # Her donatı tipi için bir örnek nokta oluştur (0,0 noktasında)
        # Öğrenci bunları kopyalayıp istediği yere taşıyacak
        for i, (did, name, cat, svg, color, size) in enumerate(FURNITURE_CATALOG):
            f = QgsFeature(fields)
            # Sıfır noktası yerine yan yana dizelim ki görülebilsin
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
            svg_path = os.path.join(icon_dir, svg)
            f.setAttributes(
                [
                    did,
                    name,
                    cat,
                    svg_path,
                    color,
                    size,
                    f"Yerleşim planı donatısı: {name}. Bu noktayı kopyalayıp istediğiniz konuma taşıyın.",
                ]
            )
            sink.addFeature(f, QgsFeatureSink.FastInsert)

        feedback.pushInfo(
            f"✅ {len(FURNITURE_CATALOG)} adet kentsel donatı şablonu oluşturuldu."
        )
        feedback.pushInfo("")
        feedback.pushInfo("KULLANIM:")
        feedback.pushInfo("1. Oluşan katmanı düzenleme moduna alın (kalem ikonu)")
        feedback.pushInfo("2. 'donati_id' sütununa göre istediğiniz donatıyı seçin")
        feedback.pushInfo("3. Haritada istenen konuma nokta ekleyin")
        feedback.pushInfo("4. Eklediğiniz noktanın 'donati_id' alanını doldurun")
        feedback.pushInfo(
            "   (Sadece açılır listeden 'donati_id' seçmeniz yeterlidir!)"
        )
        feedback.pushInfo("")
        feedback.pushInfo("SVG semboller otomatik olarak 'donati_id' değerine göre")
        feedback.pushInfo("kategorize edilmiş stillerle gösterilecektir.")

        return {self.OUTPUT: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        """Çıktı katmanına SVG tabanlı kategorize stil uygula."""
        output_layer = context.getMapLayer(
            list(context.layersToLoadOnCompletion().keys())[0]
        )
        if output_layer is None:
            return {}

        icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")
        categories = []

        for did, name, cat, svg, color, size in FURNITURE_CATALOG:
            svg_path = os.path.join(icon_dir, svg)
            symbol = QgsMarkerSymbol.createSimple({})
            symbol.deleteSymbolLayer(0)
            svg_layer = QgsSvgMarkerSymbolLayer(svg_path, size)
            svg_layer.setFillColor(symbol.color())
            symbol.appendSymbolLayer(svg_layer)
            symbol.setSize(size)
            categories.append(QgsRendererCategory(did, symbol, name))

        renderer = QgsCategorizedSymbolRenderer("donati_id", categories)
        output_layer.setRenderer(renderer)

        # ── Form Ayarları (Attribute Form Configuration) ──
        idx_id = output_layer.fields().indexOf("donati_id")
        if idx_id >= 0:
            # Dropdown menüsü için value map
            vmap = {name: did for did, name, cat, svg, color, size in FURNITURE_CATALOG}
            setup = QgsEditorWidgetSetup("ValueMap", {"map": vmap})
            output_layer.setEditorWidgetSetup(idx_id, setup)

        # Diğer metadata alanlarını gizle (Öğrenci formunda karmaşa yaratmasın)
        hidden_fields = ["donati_adi", "kategori", "svg_dosya", "renk", "boyut_mm"]
        for field_name in hidden_fields:
            idx = output_layer.fields().indexOf(field_name)
            if idx >= 0:
                output_layer.setEditorWidgetSetup(
                    idx, QgsEditorWidgetSetup("Hidden", {})
                )

        output_layer.triggerRepaint()

        return {}

    def name(self):
        return "urban_furniture"

    def displayName(self):
        return "★ Kentsel Donatı Katmanı Oluştur"

    def group(self):
        return "Yerleşim Planı Yardımcılar"

    def groupId(self):
        return "yerlesim_plani_yardimcilar"

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Yerleşim planında kullanılacak kent mobilyaları için\n"
            "hazır stillenmiş nokta katmanı oluşturur.\n\n"
            "İçerdiği donatılar:\n"
            "• 🪑 Oturma Bankı\n"
            "• 💡 Aydınlatma Direği\n"
            "• 🗑️ Çöp Kovası\n"
            "• 🧯 Yangın Musluğu\n"
            "• 🌳 Süs Ağacı\n"
            "• 📋 Bilgi Panosu\n"
            "• ⛲ Çeşme / Su Öğesi\n"
            "• 🚲 Bisiklet Parkı\n"
            "• ⚡ EV Şarj İstasyonu\n"
            "• 🎠 Çocuk Oyun Alanı\n"
            "• 🚗 Araba\n"
            "• 🚦 Trafik Işığı\n\n"
            "Kullanım:\n"
            "1. Bu algoritmayı çalıştırın → donatı katmanı oluşur\n"
            "2. Katmanı düzenleme moduna alın (kalem ikonu)\n"
            "3. Haritada donatı eklemek istediğiniz yere tıklayın\n"
            "4. Açılan formdan (Dropdown) doğrudan istediğiniz donatıyı seçin\n"
            "5. SVG semboller otomatik olarak belirecektir."
        )

    def createInstance(self):
        return UrbanFurnitureAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

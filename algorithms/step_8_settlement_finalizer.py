# -*- coding: utf-8 -*-
"""
Adım 8: SettlementFinalizer — Yerleşim planı birleştirme ve rapor
Otopark yeterliliği + nüfus yoğunluğu + genel istatistik

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterField,
    QgsFeature,
    QgsWkbTypes,
    QgsProcessingException,
    QgsField,
    QgsFields,
    QgsFeatureSink,
    QgsSpatialIndex,
)


class SettlementFinalizerAlgorithm(QgsProcessingAlgorithm):
    INPUT_PARCELS = "INPUT_PARCELS"
    INPUT_BUILDINGS = "INPUT_BUILDINGS"
    INPUT_TREES = "INPUT_TREES"
    INPUT_HARDSURFACE = "INPUT_HARDSURFACE"
    INPUT_PARKING = "INPUT_PARKING"
    TAKS_FIELD = "TAKS_FIELD"
    KAKS_FIELD = "KAKS_FIELD"
    FLAT_SIZE = "FLAT_SIZE"
    HOUSEHOLD_SIZE = "HOUSEHOLD_SIZE"
    OUTPUT_STATS = "OUTPUT_STATS"
    OUTPUT_PARKING_REPORT = "OUTPUT_PARKING_REPORT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_PARCELS,
                self.tr("Parsel katmanı"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_BUILDINGS,
                self.tr("Bina katmanı"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_TREES,
                self.tr("Ağaç katmanı (opsiyonel)"),
                [QgsProcessing.TypeVectorPoint],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_HARDSURFACE,
                self.tr("Sert zemin katmanı (opsiyonel)"),
                [QgsProcessing.TypeVectorPolygon],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_PARKING,
                self.tr("Otopark stall katmanı (opsiyonel)"),
                [QgsProcessing.TypeVectorPolygon],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.TAKS_FIELD,
                self.tr("TAKS sütunu"),
                parentLayerParameterName=self.INPUT_PARCELS,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.KAKS_FIELD,
                self.tr("KAKS/Emsal sütunu"),
                parentLayerParameterName=self.INPUT_PARCELS,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.FLAT_SIZE,
                self.tr("Ortalama daire büyüklüğü (m²) — konut istatistikleri için"),
                QgsProcessingParameterNumber.Double,
                120.0,
                minValue=40.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HOUSEHOLD_SIZE,
                self.tr("Ortalama hane halkı büyüklüğü — 2026 TÜİK ortalaması ~2.77"),
                QgsProcessingParameterNumber.Double,
                2.77,
                minValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_STATS, self.tr("Genel istatistik raporu")
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_PARKING_REPORT,
                self.tr("Otopark yeterliliği raporu (parsel bazlı)"),
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        p_src = self.parameterAsSource(parameters, self.INPUT_PARCELS, context)
        b_src = self.parameterAsSource(parameters, self.INPUT_BUILDINGS, context)
        t_src = self.parameterAsSource(parameters, self.INPUT_TREES, context)
        hs_src = self.parameterAsSource(parameters, self.INPUT_HARDSURFACE, context)
        pk_src = self.parameterAsSource(parameters, self.INPUT_PARKING, context)
        kaks_f = self.parameterAsString(parameters, self.KAKS_FIELD, context)
        flat_size = self.parameterAsDouble(parameters, self.FLAT_SIZE, context)
        hh_size = self.parameterAsDouble(parameters, self.HOUSEHOLD_SIZE, context)

        if not p_src or not b_src:
            raise QgsProcessingException(
                self.tr("Parsel ve bina katmanları zorunludur.")
            )

        # ═══ Genel İstatistik Raporu ═══
        stat_fields = QgsFields()
        stat_fields.append(QgsField("metric", QVariant.String, "string", 100))
        stat_fields.append(QgsField("value", QVariant.Double, "double", 20, 2))
        stat_fields.append(QgsField("unit", QVariant.String, "string", 20))

        (stat_sink, stat_dest) = self.parameterAsSink(
            parameters,
            self.OUTPUT_STATS,
            context,
            stat_fields,
            QgsWkbTypes.NoGeometry,
            p_src.sourceCrs(),
        )

        # ═══ Otopark Yeterliliği Raporu (Parsel Bazlı) ═══
        park_fields = QgsFields()
        park_fields.append(QgsField("parcel_fid", QVariant.Int))
        park_fields.append(QgsField("parcel_area_m2", QVariant.Double, "double", 20, 2))
        park_fields.append(QgsField("kaks_emsal", QVariant.Double, "double", 20, 4))
        park_fields.append(
            QgsField("toplam_insaat_m2", QVariant.Double, "double", 20, 2)
        )
        park_fields.append(QgsField("tahmini_daire", QVariant.Int))
        park_fields.append(QgsField("tahmini_nufus", QVariant.Double, "double", 20, 1))
        park_fields.append(QgsField("gerekli_otopark", QVariant.Int))
        park_fields.append(QgsField("mevcut_otopark", QVariant.Int))
        park_fields.append(QgsField("otopark_yeterli", QVariant.Bool))
        park_fields.append(QgsField("otopark_fazla_eksik", QVariant.Int))

        (park_sink, park_dest) = self.parameterAsSink(
            parameters,
            self.OUTPUT_PARKING_REPORT,
            context,
            park_fields,
            QgsWkbTypes.MultiPolygon,
            p_src.sourceCrs(),
        )

        # Otopark index
        pk_index = QgsSpatialIndex()
        pk_feats = {}
        if pk_src:
            for pf in pk_src.getFeatures():
                pk_index.addFeature(pf)
                pk_feats[pf.id()] = pf

        # İstatistikler
        total_parcel_area = 0
        total_building_area = 0
        total_parcels = 0
        total_buildings = 0
        total_pop = 0.0
        total_needed_parking = 0
        total_existing_parking = 0
        total_flats = 0

        # Building index
        b_index = QgsSpatialIndex()
        b_feats = {}
        for bf in b_src.getFeatures():
            b_index.addFeature(bf)
            b_feats[bf.id()] = bf
            total_buildings += 1
            total_building_area += bf.geometry().area()

        for pf in p_src.getFeatures():
            if feedback.isCanceled():
                break

            pg = pf.geometry()
            if pg.isEmpty():
                continue

            p_area = pg.area()
            total_parcel_area += p_area
            total_parcels += 1

            # KAKS/Emsal değeri
            kaks_val = 0.0
            if kaks_f:
                try:
                    raw = str(pf[kaks_f] or "").replace(",", ".")
                    kaks_val = float(raw) if raw else 0.0
                except (TypeError, ValueError):
                    pass

            # Toplam inşaat alanı
            tia = p_area * kaks_val if kaks_val > 0 else 0

            # Tahmini daire ve nüfus
            tahmini_daire = int(tia / flat_size) if flat_size > 0 and tia > 0 else 0
            tahmini_nufus = tahmini_daire * hh_size
            total_flats += tahmini_daire
            total_pop += tahmini_nufus

            # 2026 Otopark Yönetmeliği: Konut → her daire için 1 otopark
            gerekli_otopark = tahmini_daire
            total_needed_parking += gerekli_otopark

            # Parseldeki mevcut otopark sayısı
            mevcut = 0
            if pk_src:
                candidates = pk_index.intersects(pg.boundingBox())
                for cid in candidates:
                    sg = pk_feats[cid].geometry()
                    if pg.intersects(sg):
                        mevcut += 1
            total_existing_parking += mevcut

            yeterli = mevcut >= gerekli_otopark
            fark = mevcut - gerekli_otopark

            nf = QgsFeature(park_fields)
            nf.setGeometry(pg)
            nf.setAttributes(
                [
                    pf.id(),
                    round(p_area, 2),
                    round(kaks_val, 4),
                    round(tia, 2),
                    tahmini_daire,
                    round(tahmini_nufus, 1),
                    gerekli_otopark,
                    mevcut,
                    yeterli,
                    fark,
                ]
            )
            park_sink.addFeature(nf, QgsFeatureSink.FastInsert)

        # ═══ Genel istatistik çıktısı ═══
        stats = [
            ("parsel_sayisi", total_parcels, "adet"),
            ("bina_sayisi", total_buildings, "adet"),
            ("toplam_parsel_alan_m2", total_parcel_area, "m²"),
            ("toplam_bina_alan_m2", total_building_area, "m²"),
            (
                "ortalama_taks",
                total_building_area / total_parcel_area if total_parcel_area > 0 else 0,
                "oran",
            ),
            ("tahmini_toplam_daire", total_flats, "adet"),
            ("tahmini_toplam_nufus", total_pop, "kişi"),
            ("gerekli_otopark_toplam", total_needed_parking, "adet"),
            ("mevcut_otopark_toplam", total_existing_parking, "adet"),
            ("otopark_fark", total_existing_parking - total_needed_parking, "adet"),
        ]

        if t_src:
            stats.append(("agac_sayisi", t_src.featureCount(), "adet"))
        if hs_src:
            hs_area = sum(f.geometry().area() for f in hs_src.getFeatures())
            stats.append(("sert_zemin_alan_m2", hs_area, "m²"))

        for key, val, unit in stats:
            sf = QgsFeature(stat_fields)
            sf.setAttributes([key, round(val, 2), unit])
            stat_sink.addFeature(sf, QgsFeatureSink.FastInsert)
            feedback.pushInfo(f"  {key}: {round(val, 2)} {unit}")

        feedback.pushInfo(
            "\n✅ Yerleşim planı istatistikleri ve otopark yeterliliği hazır."
        )
        return {self.OUTPUT_STATS: stat_dest, self.OUTPUT_PARKING_REPORT: park_dest}

    def name(self):
        return "8_settlement_finalizer"

    def displayName(self):
        return "8. Yerleşim Planı Raporu + Otopark Yeterliliği"

    def group(self):
        return "Yerleşim Planı İş Akışı"

    def groupId(self):
        return "yerlesim_plani_workflow"

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Tüm katmanları değerlendirip istatistik rapor üretir.\n\n"
            "İki ayrı çıktı:\n"
            "1. Genel İstatistik: Parsel/bina sayısı, alan, TAKS, nüfus\n"
            "2. Otopark Yeterliliği (parsel bazlı):\n"
            "   • KAKS/Emsal × parsel alanı = toplam inşaat alanı\n"
            "   • Toplam inşaat / daire büyüklüğü = tahmini daire\n"
            "   • Daire × hane halkı = tahmini nüfus\n"
            "   • 2026 Yönetmelik: 1 daire = 1 otopark yeri (konut)\n\n"
            "Parametreler:\n"
            "• KAKS sütunu: Parsel katmanındaki emsal/kaks değeri\n"
            "• Daire büyüklüğü: Bölgesel ortalama (İzmir ~120 m²)\n"
            "• Hane halkı: TÜİK ortalaması ~2.77 kişi"
        )

    def createInstance(self):
        return SettlementFinalizerAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

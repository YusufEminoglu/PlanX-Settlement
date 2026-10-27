# -*- coding: utf-8 -*-
"""
Adım 3.4: Bitişik Nizam Çözümü

Mevzuat:
• Bitişik nizamda YAN BAHÇE YOKTUR — sadece ön ve arka bahçe var.
• Ön cephe(ler) → ön bahçe mesafesi (yola bakan cepheler)
• Arka cephe   → ARKA BAHÇe mesafesi (0 değil!)
• Yan kenarlar → 0 m (bitişik kenar — komşuya kadar yapılır)
• Köşe parsellerde birden fazla ön cephe olabilir — tümüne ön bahçe
• Sınıflandırılmamış kenarlar → arka bahçe varsayımı (güvenli taraf)

Geliştirici: Geophilo
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsFields, QgsField, QgsGeometry,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
)

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from core.geometry_engine import get_polygon_edges
from core.footprint_engine import feature_facade_indices, fit_footprint_to_target_area
from core.geometry_engine import scale_geometry_to_area


def _float(val, default=0.0):
    try:
        return float(str(val).strip().replace(',', '.')) if val not in (None, '', 'NULL') else default
    except (TypeError, ValueError):
        return default

def _edge_geom_list(geom):
    """Parsel kenarları için QgsGeometry listesi."""
    edges = get_polygon_edges(geom)
    return [QgsGeometry.fromPolylineXY([p1, p2]) for p1, p2 in edges]


class AttachedCoverageFootprintAlgorithm(QgsProcessingAlgorithm):
    INPUT          = 'INPUT'
    ADA_ID_FIELD   = 'ADA_ID_FIELD'
    TAKS_FIELD     = 'TAKS_FIELD'
    SETBACK_FRONT  = 'SETBACK_FRONT'
    SETBACK_BACK   = 'SETBACK_BACK'
    OUTPUT         = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Parsel katmanı (Adım 2 çıktısı)'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.ADA_ID_FIELD, self.tr('Ada ID sütunu (Aynı adadaki blokları birleştirmek için)'),
            parentLayerParameterName=self.INPUT, optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.TAKS_FIELD, self.tr('TAKS sütunu (0.00–1.00)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_FRONT, self.tr('Ön bahçe mesafesi sütunu (m) — yola bakan cephe(ler)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_BACK, self.tr('Arka bahçe mesafesi sütunu (m) — arka komşu sınırı'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Bitişik nizam bina taban alanları')))

    def processAlgorithm(self, parameters, context, feedback):
        source       = self.parameterAsSource(parameters, self.INPUT, context)
        ada_id_field = self.parameterAsString(parameters, self.ADA_ID_FIELD, context)
        taks_field   = self.parameterAsString(parameters, self.TAKS_FIELD, context)
        front_field  = self.parameterAsString(parameters, self.SETBACK_FRONT, context)
        back_field   = self.parameterAsString(parameters, self.SETBACK_BACK, context)

        if source is None:
            raise QgsProcessingException(self.tr('Girdi katmanı yüklenemedi.'))

        field_index_map = {f.name(): idx for idx, f in enumerate(source.fields())}

        from core.footprint_engine import guess_ada_id_field
        if not ada_id_field:
            ada_id_field = guess_ada_id_field(field_index_map.keys())

        # Ada gruplama
        all_feats = list(source.getFeatures())
        ada_groups = {}
        for feat in all_feats:
            if feat.geometry().isEmpty():
                continue
            ada_key = (
                str(feat[field_index_map[ada_id_field]])
                if ada_id_field and ada_id_field in field_index_map
                else str(feat.id())
            )
            ada_groups.setdefault(ada_key, []).append(feat)

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(f)
        out_fields.append(QgsField('nizam_tip',      QVariant.String, 'string', 20))
        out_fields.append(QgsField('on_cephe_adet',  QVariant.Int))
        out_fields.append(QgsField('bina_alan_m2',   QVariant.Double, 'double', 20, 2))
        out_fields.append(QgsField('taks_kullanim',  QVariant.Double, 'double', 20, 4))

        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs())

        total     = len(ada_groups) or 1
        generated = 0

        from core.geometry_engine import oriented_minimum_bounding_box
        import math

        for prog, (ada_key, group_feats) in enumerate(ada_groups.items()):
            if feedback.isCanceled():
                break

            ada_geom = QgsGeometry()
            for feat in group_feats:
                ada_geom = ada_geom.combine(feat.geometry()) if not ada_geom.isEmpty() else QgsGeometry(feat.geometry())

            obb = oriented_minimum_bounding_box(ada_geom)
            if not obb:
                continue

            angle = obb['angle']
            w, h = obb['width'], obb['height']
            a_rad = math.radians(angle)
            if w < h:
                a_rad += math.pi / 2.0
                w, h = h, w

            dx_long, dy_long = math.cos(a_rad), math.sin(a_rad)
            dx_short, dy_short = -dy_long, dx_long

            ada_dict = {f.id(): f for f in group_feats}

            for feat in group_feats:
                geom        = feat.geometry()
                parcel_area = geom.area()
                taks        = _float(feat[taks_field], 0.0)
                sb_front    = _float(feat[front_field], 5.0)
                sb_back     = _float(feat[back_field], 3.0)

                if taks <= 0:
                    continue

                edge_count = len(get_polygon_edges(geom))
                edge_geoms = _edge_geom_list(geom) # Needs _edge_geom_list definition, wait
                facade     = feature_facade_indices(feat, field_index_map)
                front_indices = set(facade.get('front', []))

                edge_setbacks = [0.0] * edge_count
                adjustable    = []

                f_c = geom.centroid().asPoint()
                
                is_corner_val = feat.attribute('is_corner') if feat.fields().indexOf('is_corner') != -1 else False
                fac_cnt_val = feat.attribute('facade_count') if feat.fields().indexOf('facade_count') != -1 else 1
                is_corner_parcel = is_corner_val in (True, 1, 'true', '1') or float(fac_cnt_val) > 1

                for e_idx, e_geom in enumerate(edge_geoms):
                    if e_idx in front_indices:
                        edge_setbacks[e_idx] = sb_front
                        adjustable.append(e_idx)
                        continue

                    touched_neighbor = None
                    touched_len = 0
                    for n_id, n_feat in ada_dict.items():
                        if n_id == feat.id():
                            continue
                        inter = e_geom.intersection(n_feat.geometry())
                        if not inter.isEmpty() and inter.length() > 0.40:
                            if inter.length() > touched_len:
                                touched_len = inter.length()
                                touched_neighbor = n_feat

                    if touched_neighbor:
                        n_c = touched_neighbor.geometry().centroid().asPoint()
                        vec_x = n_c.x() - f_c.x()
                        vec_y = n_c.y() - f_c.y()
                        p_long = abs(vec_x * dx_long + vec_y * dy_long)
                        p_short = abs(vec_x * dx_short + vec_y * dy_short)

                        is_row_neighbor = (p_long > p_short)

                        if is_row_neighbor:
                            # Uzun kenar komşusu = Sıfır Yan Bahçe (Bitişik)
                            edge_setbacks[e_idx] = 0.0
                        else:
                            # Kısa kenar komşusu = Arka Bahçe (Avlu için)
                            edge_setbacks[e_idx] = 0.0 if is_corner_parcel else sb_back
                            adjustable.append(e_idx)
                    else:
                        # Arka/Derinlik komşusu
                        edge_setbacks[e_idx] = 0.0 if is_corner_parcel else sb_back
                        adjustable.append(e_idx)

                building = fit_footprint_to_target_area(
                    geom, edge_setbacks, parcel_area * taks, adjustable)

                if building is None or building.isEmpty():
                    continue

                bina_alan = building.area()
                nf = QgsFeature(out_fields)
                nf.setGeometry(building)
                nf.setAttributes(list(feat.attributes()) + [
                    'bitisik', len(front_indices),
                    round(bina_alan, 2),
                    round(bina_alan / parcel_area, 4),
                ])
                sink.addFeature(nf, QgsFeatureSink.FastInsert)
                generated += 1

            feedback.setProgress(int((prog + 1) / total * 100))

        feedback.pushInfo(self.tr(
            f'Bitişik nizam: {generated} bağımsız bina footprint üretildi.'))
        return {self.OUTPUT: dest_id}

    def name(self):         return '3_4_bitisik_nizam'
    def displayName(self):  return '3.4. Bitişik Nizam Çözümü'
    def group(self):        return 'Yerleşim Planı İş Akışı'
    def groupId(self):      return 'yerlesim_plani_workflow'

    def shortHelpString(self):
        return self.tr(
            '━━━ planX — Yerleşim Planı Araç Seti ━━━\n'
            'Geliştirici: Geophilo\n\n'
            'Bitişik Nizam (B nizam) kurallarına göre bina taban alanı üretir.\n\n'
            'Setback Kuralı — Öncelik Sırası:\n'
            '1. Ön cephe(ler)     → ön bahçe mesafesi (yola bakan)\n'
            '2. Arka cephe        → ARKA BAHÇE mesafesi (0 değil!)\n'
            '3. Yan kenarlar      → 0 m (komşuya bitişik kenar)\n'
            '4. Sınıflandırılmamış→ arka bahçe varsayımı (güvenli)\n\n'
            'Köşe Parseller:\n'
            '• Birden fazla facade_front kenarı varsa tümü ön bahçe alır\n'
            '• Yük: ic_kenar_adet = 0 ise izole (her iki yan üst tabandan geliyor)\n\n'
            'Önkoşul:\n'
            '• Adım 2 (Cephe Tespiti) çıktısı — facade_front / back / side alanları\n'
            '• Cephe verisi yoksa uniform buffer + arka bahçe uygulanır\n\n'
            'Parametreler:\n'
            '• TAKS sütunu: Taban Alanı Katsayısı (0.00–1.00)\n'
            '• Ön bahçe sütunu: Yol cephesi mesafesi (m)\n'
            '• Arka bahçe sütunu: Arka komşu mesafesi (m)\n\n'
            'NOT: Bitişik nizamda YAN BAHÇE YOKTUR. Yan kenarlar tamamen 0 m setback alır,\n'
            'bina yan komşu parsel sınırına kadar uzanabilir.\n\n'
            'Değer Formatı: Metin (TEXT) sütunlar desteklenir.')

    def createInstance(self):
        return AttachedCoverageFootprintAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

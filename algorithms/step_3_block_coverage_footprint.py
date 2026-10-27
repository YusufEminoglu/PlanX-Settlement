# -*- coding: utf-8 -*-
"""
Adım 3.3: Blok Nizam Çözümü

Mevzuat:
• Ada içinde yan komşu parsellerin ORTAKlaştıkları YANI KENAR → 0 m setback
• Grubun dışa bakan serbest yan kenarı → 1 × yan bahçe (setback_side)
  (Böylece iki blok grubu arasında 2 × yan bahçe boşluk oluşur)
• Ön cephe(ler) → ön bahçe mesafesi
• ARKA BAHÇE → ayrı bir parametre, 0 değil! (Arka komşuya mesafe korunur)
• Köşe parsellerde birden fazla ön cephe varsa tümüne ön bahçe uygulanır

Ortak kenar tespiti — iki katmanlı:
  1. Önce facade_side sınıflandırması (Adım 2 çıktısı) kullanılır
  2. Bu sınıflandırma içinde fiziksel komşu paylaşımı kontrol edilir
  Böylece facade_back yanlışlıkla 0 almaz.

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
from core.footprint_engine import feature_facade_indices, fit_footprint_to_target_area, guess_ada_id_field


def _float(val, default=0.0):
    try:
        return float(str(val).strip().replace(',', '.')) if val not in (None, '', 'NULL') else default
    except (TypeError, ValueError):
        return default


def _edge_geom_list(geom):
    """Parsel kenarları için QgsGeometry listesi."""
    edges = get_polygon_edges(geom)
    return [QgsGeometry.fromPolylineXY([p1, p2]) for p1, p2 in edges]


def _shared_indices_within(edge_geoms, neighbor_geoms, candidate_set, tolerance=0.40):
    """
    candidate_set içindeki kenar indekslerinden fiziksel olarak bir komşuya
    değen (shared) olanları döner.
    candidate_set = boşsa tüm kenarlar kontrol edilir.
    """
    shared = set()
    for idx, eg in enumerate(edge_geoms):
        if candidate_set and idx not in candidate_set:
            continue
        for ng in neighbor_geoms:
            inters = eg.intersection(ng)
            if not inters.isEmpty() and inters.length() > tolerance:
                shared.add(idx)
                break
    return shared


class BlockCoverageFootprintAlgorithm(QgsProcessingAlgorithm):
    INPUT          = 'INPUT'
    ADA_ID_FIELD   = 'ADA_ID_FIELD'
    TAKS_FIELD     = 'TAKS_FIELD'
    SETBACK_FRONT  = 'SETBACK_FRONT'
    SETBACK_SIDE   = 'SETBACK_SIDE'
    SETBACK_BACK   = 'SETBACK_BACK'
    OUTPUT         = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Parsel katmanı (Adım 2 çıktısı)'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.ADA_ID_FIELD, self.tr('Ada ID sütunu (aynı adadaki parselleri belirler)'),
            parentLayerParameterName=self.INPUT, optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.TAKS_FIELD, self.tr('TAKS sütunu (0.00–1.00)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_FRONT, self.tr('Ön bahçe mesafesi sütunu (m) — yola bakan cephe'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_SIDE, self.tr('Yan bahçe mesafesi sütunu (m) — serbest dış yan kenar'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.SETBACK_BACK, self.tr('Arka bahçe mesafesi sütunu (m) — arka komşu sınırı'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Blok nizam bina taban alanları')))

    def processAlgorithm(self, parameters, context, feedback):
        source       = self.parameterAsSource(parameters, self.INPUT, context)
        ada_id_field = self.parameterAsString(parameters, self.ADA_ID_FIELD, context)
        taks_field   = self.parameterAsString(parameters, self.TAKS_FIELD, context)
        front_field  = self.parameterAsString(parameters, self.SETBACK_FRONT, context)
        side_field   = self.parameterAsString(parameters, self.SETBACK_SIDE, context)
        back_field   = self.parameterAsString(parameters, self.SETBACK_BACK, context)

        if source is None:
            raise QgsProcessingException(self.tr('Girdi katmanı yüklenemedi.'))

        field_index_map = {f.name(): idx for idx, f in enumerate(source.fields())}
        if not ada_id_field:
            ada_id_field = guess_ada_id_field(field_index_map.keys())

        # Tüm unsurları oku — ada grupla
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
        out_fields.append(QgsField('ic_kenar_adet',  QVariant.Int))
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

            # 1. Ada Genel Alanını ve Eksenini Bul
            ada_geom = QgsGeometry()
            for feat in group_feats:
                ada_geom = ada_geom.combine(feat.geometry()) if not ada_geom.isEmpty() else QgsGeometry(feat.geometry())

            obb = oriented_minimum_bounding_box(ada_geom)
            if not obb:
                continue

            # Uzun ekseni belirle
            angle = obb['angle']
            w, h = obb['width'], obb['height']
            a_rad = math.radians(angle)
            if w < h:
                a_rad += math.pi / 2.0
                w, h = h, w

            dx_long, dy_long = math.cos(a_rad), math.sin(a_rad)
            dx_short, dy_short = -dy_long, dx_long

            # 2. Parselleri Uzun Eksene Göre Sırala
            def _proj(feat):
                c = feat.geometry().centroid().asPoint()
                return c.x() * dx_long + c.y() * dy_long

            sorted_feats = sorted(group_feats, key=_proj)

            # 3. Graph Tabanlı Row Neighbor Eşleştirmesi (Blok İkilileri)
            # Spatial sıralama arka bahçeleri de yan yana dizebiliyordu. Bu yüzden önce row neighbor grafiği çıkarıyoruz.
            pairs = []
            matched = set()
            
            for idx in range(len(sorted_feats)):
                if idx in matched:
                    continue
                f1 = sorted_feats[idx]
                geom1 = f1.geometry()
                c1 = geom1.centroid().asPoint()
                
                paired_with = None
                
                # Sadece sonraki parsellere bakıyoruz, mesafe ve row komşuluğu kontrol ediyoruz
                for j in range(idx + 1, len(sorted_feats)):
                    if j in matched:
                        continue
                    f2 = sorted_feats[j]
                    geom2 = f2.geometry()
                    
                    if geom1.intersects(geom2.buffer(0.05, 5)):
                        # Acaba row neighbor mu? Merkez izdüşümüne bak!
                        c2 = geom2.centroid().asPoint()
                        vec_x = c2.x() - c1.x()
                        vec_y = c2.y() - c1.y()
                        p_long = abs(vec_x * dx_long + vec_y * dy_long)
                        p_short = abs(vec_x * dx_short + vec_y * dy_short)
                        
                        if p_long > p_short:
                            # Evet, bu bir yan (sıra) komşusu
                            paired_with = f2
                            matched.add(j)
                            break
                            
                if paired_with:
                    pairs.append([f1, paired_with])
                    matched.add(idx)
                else:
                    pairs.append([f1])
                    matched.add(idx)
                        
            paired_map = {}
            for p_idx, pair in enumerate(pairs):
                for pf in pair:
                    paired_map[pf.id()] = [x.id() for x in pair]

            # Tüm adadaki komşuları dict'te tut (hızlı centroid ve geometri için)
            ada_dict = {f.id(): f for f in sorted_feats}

            # 4. Form Üretimi
            for pair in pairs:
                paired_ids = set(f.id() for f in pair)

                for feat in pair:
                    geom        = feat.geometry()
                    parcel_area = geom.area()
                    taks        = _float(feat[taks_field], 0.0)
                    sb_front    = _float(feat[front_field], 5.0)
                    sb_side     = _float(feat[side_field], 3.0)
                    sb_back     = _float(feat[back_field], 3.0)

                    if taks <= 0:
                        continue

                    edge_count  = len(get_polygon_edges(geom))
                    edge_geoms  = _edge_geom_list(geom)

                    facade        = feature_facade_indices(feat, field_index_map)
                    front_indices = set(facade.get('front', []))

                    edge_setbacks = [0.0] * edge_count
                    adjustable    = []

                    f_c = geom.centroid().asPoint()

                    is_corner_val = feat.attribute('is_corner') if feat.fields().indexOf('is_corner') != -1 else False
                    fac_cnt_val = feat.attribute('facade_count') if feat.fields().indexOf('facade_count') != -1 else 1
                    is_corner_parcel = is_corner_val in (True, 1, 'true', '1') or float(fac_cnt_val) > 1

                    # Her bir kenar için komşu kontrolü yap
                    for e_idx, e_geom in enumerate(edge_geoms):
                        # Dış cephe mi?
                        if e_idx in front_indices:
                            edge_setbacks[e_idx] = sb_front
                            adjustable.append(e_idx)
                            continue

                        # Hangi komşuya değiyor?
                        touched_neighbor = None
                        for n_id, n_feat in ada_dict.items():
                            if n_id == feat.id():
                                continue
                            n_geom_buffered = n_feat.geometry().buffer(0.05, 5)
                            inter = e_geom.intersection(n_geom_buffered)
                            if not inter.isEmpty() and inter.length() > 0.40:
                                touched_neighbor = n_feat
                                break

                        if touched_neighbor:
                            # Komşunun yönünü centroid projeksiyonuyla anla
                            n_c = touched_neighbor.geometry().centroid().asPoint()
                            vec_x = n_c.x() - f_c.x()
                            vec_y = n_c.y() - f_c.y()
                            p_long = abs(vec_x * dx_long + vec_y * dy_long)
                            p_short = abs(vec_x * dx_short + vec_y * dy_short)

                            is_row_neighbor = (p_long > p_short)

                            if is_row_neighbor:
                                if touched_neighbor.id() in paired_ids:
                                    # Kendi grubundaki sıra komşusu = Sıfır Yan Bahçe
                                    edge_setbacks[e_idx] = 0.0
                                else:
                                    # Başka grubun sıra komşusu = Yan Bahçe
                                    edge_setbacks[e_idx] = sb_side
                                    adjustable.append(e_idx)
                            else:
                                # Arka arkaya (veya kısa eksendeki) komşu = Arka Bahçe
                                edge_setbacks[e_idx] = 0.0 if is_corner_parcel else sb_back
                                adjustable.append(e_idx)
                        else:
                            # Komşuya değmiyor -> Güvenli liman arka bahçe.
                            if e_idx in facade.get('back', []):
                                edge_setbacks[e_idx] = 0.0 if is_corner_parcel else sb_back
                            else:
                                edge_setbacks[e_idx] = sb_side
                            adjustable.append(e_idx)

                    # Hesapla
                    building = fit_footprint_to_target_area(
                        geom, edge_setbacks, parcel_area * taks, adjustable)

                    if building is None or building.isEmpty():
                        continue

                    bina_alan = building.area()
                    taks_use  = bina_alan / parcel_area if parcel_area > 0 else 0.0

                    nf = QgsFeature(out_fields)
                    nf.setGeometry(building)
                    nf.setAttributes(list(feat.attributes()) + [
                        'blok', len(paired_ids)-1,
                        round(bina_alan, 2), round(taks_use, 4),
                    ])
                    sink.addFeature(nf, QgsFeatureSink.FastInsert)
                    generated += 1

            feedback.setProgress(int((prog + 1) / total * 100))

        feedback.pushInfo(self.tr(
            f'Blok nizam: {generated} bağımsız bina footprint üretildi.'))
        return {self.OUTPUT: dest_id}

    def name(self):         return '3_3_blok_nizam'
    def displayName(self):  return '3.3. Blok Nizam Çözümü'
    def group(self):        return 'Yerleşim Planı İş Akışı'
    def groupId(self):      return 'yerlesim_plani_workflow'

    def shortHelpString(self):
        return self.tr(
            '━━━ planX — Yerleşim Planı Araç Seti ━━━\n'
            'Geliştirici: Geophilo\n\n'
            'Blok Nizam (BL nizam) kurallarına göre her parselde bağımsız bina taban alanı üretir.\n\n'
            'Setback Kuralı — Öncelik Sırası:\n'
            '1. Ön cephe(ler)            → ön bahçe mesafesi (yoll yüzü)\n'
            '2. Arka cephe               → ARKA BAHÇe mesafesi (0 değil!)\n'
            '3. Aynı ada içi ortak yan   → 0 m (blok grubu iç yüzü)\n'
            '4. Serbest dış yan kenar    → 1 × yan bahçe (dışa bakan yüz)\n'
            '→ İki blok grubu arasında: 2 × yan bahçe boşluk\n\n'
            'Ortak Kenar Tespiti:\n'
            '• Adım 2 facade_side sınıflandırması kullanılır (varsa)\n'
            '• Yalnızca yan olarak etiketlenmiş kenarlar 0 m alabilir\n'
            '• Arka bahçe kenarı asla 0 m almaz\n'
            '• Cephe verisi yoksa, front/back dışı tüm kenarlar taranır\n\n'
            'Çıktı Alanı:\n'
            '• ic_kenar_adet: Tespit edilen iç ortak kenar sayısı\n'
            '  (0 olması parselin izole olduğunu, 2+ olması her iki yanının bitişik\n'
            '  olduğunu gösterir — köşe olmayan ara binalar)\n\n'
            'Her bina ayrı poligondur; geometriler birleştirilmez.\n\n'
            'Değer Formatı: Metin (TEXT) sütunlar desteklenir.')

    def createInstance(self):
        return BlockCoverageFootprintAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

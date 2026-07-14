# -*- coding: utf-8 -*-
"""
Adım 3.1: Emsal Koşulu — Ada Çözümü (FAR / Avlulu Çevre-Blok)

Parametrik kentsel kütle yaklaşımı:
• Ada çevresinde yapı yaklaşma sınırına oturarak, iç avlu bırakan
  dinamik çevre-blok binalar
• Setback çizgileri ~10m modüllere ayrılarak (veya istenen form sayısına göre)
  dinamik/prosedürel (rastgele L, U, O, I formları vb.) kütleler oluşturulur.
• Binalar birbirlerine en az 2×(yan bahçe) kadar açık mesafe bırakır.
• Her bina bağımsız bir poligon geometrisidir.
• Minimum bina derinliği: 9 m

Yençok (Hmax) → kat adedi → TAKS = E / kat adedi (≤ 1.0)

Geliştirici: Yusuf Eminoglu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys, math
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsFields, QgsField,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsGeometry, QgsPointXY, QgsWkbTypes
)

_base = os.path.dirname(os.path.dirname(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from core.parcel_randomizer import _LCG

from core.footprint_engine import compute_far_side_yard, compute_floor_count_from_height
from core.geometry_engine import oriented_minimum_bounding_box, scale_geometry_to_area, get_polygon_edges

# Dinamik form modülünden gerekli öğeleri güvenli yükle
mod_3c = sys.modules.get('planx_yerlesim_step_3c_dynamic_macroform')
if mod_3c:
    generate_dynamic_form = mod_3c.generate_dynamic_form
    _FORM_NAMES = mod_3c._FORM_NAMES
    _FORM_LABELS = mod_3c._FORM_LABELS
else:
    try:
        from algorithms.step_3c_dynamic_macroform import generate_dynamic_form, _FORM_NAMES, _FORM_LABELS
    except ImportError:
        _FORM_NAMES = ['dikdortgen']
        _FORM_LABELS = ['Dikdörtgen (I)']
        def generate_dynamic_form(bbox_geom, f_type, allowed, rng):
            return bbox_geom, 'dikdortgen'


def _float(val, default=0.0):
    try:
        return float(str(val).strip().replace(',', '.')) if val not in (None, '', 'NULL') else default
    except (TypeError, ValueError):
        return default


def _segmented_perimeter_forms(buildable, target_area, side_yard, min_depth, num_forms, rng, allowed_forms):
    """
    Buildable poligonun kenarlarını belirli sayıda parsele bölerek hedef TAKS
    alanına uygun dinamik formlar üretir.
    """
    if buildable.isEmpty() or target_area <= 0:
        return []

    # 1. Kenarları çıkar
    edges = get_polygon_edges(buildable)
    valid_edges = []
    total_length = 0.0
    
    # Çok kısa kenarları ele ve iç yöne (normal) bakan bounding box üretmek için vektörü hazırla
    center = buildable.centroid().asPoint()
    for e in edges:
        p1, p2 = e[0], e[1]
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length < 10.0:  # 10m'den kısa kenarlara yapı dizilmez (genelde köşe pahlarıdır)
            continue
        
        nx, ny = -dy/length, dx/length
        # İçeri bakıp bakmadığını test et:
        test_pt = QgsPointXY(p1.x() + dx/2 + nx*min_depth, p1.y() + dy/2 + ny*min_depth)
        if not buildable.contains(QgsGeometry.fromPointXY(test_pt)):
            nx, ny = -nx, -ny # ters çevir
        
        valid_edges.append({'p1': p1, 'p2': p2, 'len': length, 'nx': nx, 'ny': ny})
        total_length += length
        
    if not valid_edges:
        sg = scale_geometry_to_area(buildable, target_area)
        return [(sg, 'fallback')] if not sg.isEmpty() else []

    # Hedef Derinlik ve Dağılım Hesabı
    # Toplam num_forms adet yapıyı bu kenarlara uzunlukları oranında dağıtalım (min 1 forms if long enough)
    forms_per_edge = []
    total_assigned = 0
    for ve in valid_edges:
        count = int(round((ve['len'] / total_length) * num_forms))
        # max capacity check (widest building = 5m + gaps)
        max_cap = int(ve['len'] / (5 + 2*side_yard))
        count = min(count, max_cap)
        forms_per_edge.append(count)
        total_assigned += count
        
    # Kalanı en uzuna ekle/çıkar (eğer num_forms tutturulmak isteniyorsa ama gerek yok parametrik olabilir)
    actual_num_forms = sum(forms_per_edge)
    if actual_num_forms == 0:
        # kenarlar var ama hepsi max_cap falan küçük, en az 1 tane form koyalım
        widest_idx = max(range(len(valid_edges)), key=lambda i: valid_edges[i]['len'])
        forms_per_edge[widest_idx] = 1
        actual_num_forms = 1
        
    # Her bir parça "building_width", aralarında "2 * side_yard" boşluk kalacak.
    # Total assigned parça ile net kullanım alanlarını bulalım. Formların ortalama bbox doluluk oranı ~0.65
    avg_density = 0.65
    total_effective_width = total_length - actual_num_forms * (2 * side_yard)
    if total_effective_width <= 5.0 * actual_num_forms:
        # Sığmıyor
        sg = scale_geometry_to_area(buildable, target_area)
        return [(sg, 'fallback')] if not sg.isEmpty() else []

    calc_depth = target_area / (total_effective_width * avg_density)
    calc_depth = max(min_depth, min(calc_depth, 35.0)) # en fazla 35m derinlik
    
    # Avlu sınırı ile clip atmak, derinliğin parseli taşıp arka komşuya girmesini önler
    courtyard = buildable.buffer(-calc_depth, 8)
    clipping_ring = buildable.difference(courtyard) if not courtyard.isEmpty() else buildable

    buildings = []
    
    for i, ve in enumerate(valid_edges):
        count = forms_per_edge[i]
        if count == 0:
            continue
            
        edge_len = ve['len']
        p1, p2 = ve['p1'], ve['p2']
        nx, ny = ve['nx'], ve['ny']
        
        # Parçaları köşelerden de 1 yan bahçe çekerek yerleştir
        eff_len = edge_len - 2 * side_yard
        if eff_len < 5:
            continue
            
        b_width = (eff_len - (count - 1) * 2 * side_yard) / count
        if b_width < 5:
            count = int(eff_len / (5 + 2*side_yard))
            if count == 0: continue
            b_width = (eff_len - (count - 1) * 2 * side_yard) / count
            
        dx = (p2.x() - p1.x()) / edge_len
        dy = (p2.y() - p1.y()) / edge_len
        
        # Angle of tangent
        angle = math.atan2(dy, dx)
        
        for k in range(count):
            # Center of the segment
            cx_start = p1.x() + side_yard * dx + k * (b_width + 2*side_yard) * dx
            cy_start = p1.y() + side_yard * dy + k * (b_width + 2*side_yard) * dy
            
            # center of building bbox edge
            cx_edge = cx_start + (b_width/2) * dx
            cy_edge = cy_start + (b_width/2) * dy
            
            # center of the full bbox (shifted inwards by calc_depth/2)
            cx_box = cx_edge + nx * (calc_depth/2)
            cy_box = cy_edge + ny * (calc_depth/2)
            
            # bbox corners
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            hw, hd = b_width/2, calc_depth/2
            corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd)]
            
            pts = [QgsPointXY(cx_box + lx*cos_a - ly*sin_a, cy_box + lx*sin_a + ly*cos_a) for lx, ly in corners]
            bbox_geom = QgsGeometry.fromPolygonXY([pts])
            
            bbox_geom = bbox_geom.intersection(clipping_ring)
            if bbox_geom.isEmpty():
                continue
                
            # Dinamik formu oluştur
            f_geom, f_type = generate_dynamic_form(bbox_geom, "rastgele", allowed_forms, rng)
            if not f_geom.isEmpty():
                # En yakın node-to-node uzaklık garantisi (Kullanıcı İsteği)
                # Binalar arası mesafe 2*side_yard
                min_gap = 2 * side_yard
                for existing_g, _ in buildings:
                    if f_geom.distance(existing_g) < min_gap:
                        # Yakın olan kısmı tam olarak min_gap sınırı kalacak şekilde kes (boydan küçült)
                        f_geom = f_geom.difference(existing_g.buffer(min_gap, 5))
                
                # Kesim sonrası geometri çoklu poligon haline gelmiş olabilir veya çok küçülebilir
                if f_geom.type() == QgsWkbTypes.PolygonGeometry:
                    if not f_geom.isEmpty() and f_geom.area() > 25: # En az 25m2 kalsın
                        buildings.append((f_geom, f_type))

    if not buildings:
        fallback = scale_geometry_to_area(buildable, target_area)
        return [(fallback, 'fallback')] if not fallback.isEmpty() else []

    return buildings


class CoverageFootprintFarAlgorithm(QgsProcessingAlgorithm):
    INPUT            = 'INPUT'
    FAR_FIELD        = 'FAR_FIELD'
    HMAX_FIELD       = 'HMAX_FIELD'
    FIXED_SETBACK    = 'FIXED_SETBACK'
    AVG_FLOOR_HEIGHT = 'AVG_FLOOR_HEIGHT'
    MIN_DEPTH        = 'MIN_DEPTH'
    
    # Dynamic forms parameters
    FORM_TYPE        = 'FORM_TYPE'
    ALLOWED_FORMS    = 'ALLOWED_FORMS'
    DIVERSITY        = 'DIVERSITY'
    NUM_FORMS        = 'NUM_FORMS'
    RANDOM_SEED      = 'RANDOM_SEED'
    
    OUTPUT           = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Emsal çözümü yapılacak ada katmanı (her unsur 1 ada sayılır)'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.FAR_FIELD, self.tr('Emsal (FAR / E) sütunu — toplam inşaat alanı / ada alanı'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.HMAX_FIELD, self.tr('Yençok yükseklik (Hmax) sütunu (m)'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterNumber(
            self.FIXED_SETBACK, self.tr('Ada çevresi yapı yaklaşma mesafesi (m)'),
            QgsProcessingParameterNumber.Double, defaultValue=5.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.AVG_FLOOR_HEIGHT, self.tr('Ortalama kat yüksekliği (m) — Hmax → kat adedi'),
            QgsProcessingParameterNumber.Double, defaultValue=3.1, minValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_DEPTH, self.tr('Minimum bina derinliği (m) — en dar kısım'),
            QgsProcessingParameterNumber.Double, defaultValue=9.0, minValue=5.0))
            
        self.addParameter(QgsProcessingParameterEnum(
            self.FORM_TYPE, self.tr('Form seçim modu'),
            options=['Rastgele (karışık)', 'Belirli formlar'], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.ALLOWED_FORMS, self.tr('İzin verilen formlar (tikleyerek seçin)'),
            options=_FORM_LABELS, allowMultiple=True, defaultValue=list(range(len(_FORM_LABELS)))))
        self.addParameter(QgsProcessingParameterNumber(
            self.NUM_FORMS, self.tr('Adada üretilecek rastgele form sayısı (kapasite el verdiğince)'),
            QgsProcessingParameterNumber.Integer, 6, minValue=1, maxValue=50))
        self.addParameter(QgsProcessingParameterNumber(
            self.RANDOM_SEED, self.tr('Rastgele tohum (0=tamamen rastgele)'),
            QgsProcessingParameterNumber.Integer, 0, minValue=0))
            
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Emsal çözümü — dinamik çevre-blok binaları')))

    def processAlgorithm(self, parameters, context, feedback):
        source        = self.parameterAsSource(parameters, self.INPUT, context)
        far_field     = self.parameterAsString(parameters, self.FAR_FIELD, context)
        hmax_field    = self.parameterAsString(parameters, self.HMAX_FIELD, context)
        fixed_setback = self.parameterAsDouble(parameters, self.FIXED_SETBACK, context)
        avg_floor_h   = self.parameterAsDouble(parameters, self.AVG_FLOOR_HEIGHT, context)
        min_depth     = self.parameterAsDouble(parameters, self.MIN_DEPTH, context)
        
        mode_idx      = self.parameterAsInt(parameters, self.FORM_TYPE, context)
        allowed_idx   = self.parameterAsEnums(parameters, self.ALLOWED_FORMS, context)
        num_forms     = self.parameterAsInt(parameters, self.NUM_FORMS, context)
        seed          = self.parameterAsInt(parameters, self.RANDOM_SEED, context)

        if source is None:
            raise QgsProcessingException(self.tr('Girdi katmanı yüklenemedi.'))

        # İzin verilen formları belirle
        if mode_idx == 1 and allowed_idx:
            allowed = [_FORM_NAMES[i] for i in allowed_idx if i < len(_FORM_NAMES)]
        else:
            allowed = _FORM_NAMES[:]

        rng = _LCG(seed if seed > 0 else 42)

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(f)
        out_fields.append(QgsField('ada_katman_id',   QVariant.Int))
        out_fields.append(QgsField('form_tipi',       QVariant.String, 'string', 30))
        out_fields.append(QgsField('bina_no',         QVariant.Int))
        out_fields.append(QgsField('bina_sayisi',     QVariant.Int))
        out_fields.append(QgsField('kat_adedi',       QVariant.Int))
        out_fields.append(QgsField('min_bina_mesafesi', QVariant.Double, 'double', 20, 2))
        out_fields.append(QgsField('taks_hedef',      QVariant.Double, 'double', 20, 4))
        out_fields.append(QgsField('bina_alan_m2',    QVariant.Double, 'double', 20, 2))

        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs())

        total     = source.featureCount() or 1
        generated = 0

        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break

            union_geom = feat.geometry()
            if union_geom.isEmpty():
                continue

            far  = _float(feat[far_field], 0.0)
            hmax = _float(feat[hmax_field], 0.0)

            if far <= 0:
                feedback.pushInfo(f'Parsel ID {feat.id()}: FAR=0, atlandı.')
                continue

            floor_count = compute_floor_count_from_height(hmax, avg_floor_h)
            side_yard   = compute_far_side_yard(floor_count)
            taks_target = min(1.0, far / max(floor_count, 1))

            buildable = union_geom.buffer(-fixed_setback, 8)
            if buildable.isEmpty():
                feedback.pushInfo(f'Parsel ID {feat.id()}: Yapı yaklaşma sonrası alan kalmadı.')
                continue

            target_area = buildable.area() * taks_target

            # Setback etrafında binaları diz (segmentasyon mantığı)
            buildings = _segmented_perimeter_forms(buildable, target_area, side_yard, min_depth, num_forms, rng, allowed)

            n_bldg = len(buildings)
            for bno, (bldg_geom, f_label) in enumerate(buildings, start=1):
                if bldg_geom is None or bldg_geom.isEmpty():
                    continue

                nf = QgsFeature(out_fields)
                nf.setGeometry(bldg_geom)
                nf.setAttributes(list(feat.attributes()) + [
                    feat.id(), f_label, bno, n_bldg, floor_count,
                    round(side_yard * 2, 2), round(taks_target, 4), round(bldg_geom.area(), 2),
                ])
                sink.addFeature(nf, QgsFeatureSink.FastInsert)
                generated += 1

            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(self.tr(
            f'Emsal çözümü tamamlandı. Toplam {generated} dinamik çevre-blok bina üretildi.'))
        return {self.OUTPUT: dest_id}

    def name(self):         return '3_1_emsal_ada'
    def displayName(self):  return '3.1. Emsal Koşulu — Ada Çözümü (FAR)'
    def group(self):        return 'Yerleşim Planı İş Akışı'
    def groupId(self):      return 'yerlesim_plani_workflow'

    def shortHelpString(self):
        return self.tr(
            '━━━ planX — Yerleşim Planı Araç Seti ━━━\n'
            'Geliştirici: Yusuf Eminoglu\n\n'
            'Emsal (FAR) değerinden ada / parsel çevre-blok kütlesi üretir.\n\n'
            'Parametrik Kentsel Kütle Modeli (Dinamik Segmentasyon):\n'
            '• Ada çevresinde yapı yaklaşma mesafesi sınırı tespit edilir.\n'
            '• Bu sınır hattı (aksan) dinamik olarak parçalara bölünür ve formlar (L, I, T, U vs) yerleştirilir.\n'
            '• Yapıların birbirleri arası mesafesi en az 2×(yan bahçe) tutulur.\n'
            '• İlgili formlar form tipine göre ada şekline (90 derece kırıklarla) otomatik uyum sağlar.\n\n'
            'Not:\n'
            'Bu eklentide "Ada ID" istenmez, giren her bir poligon (unsur) bağımsız bir Ada/Parsel gibi '
            'davranır ve çevresinde sıralı binalar üretilir.')

    def createInstance(self):
        return CoverageFootprintFarAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

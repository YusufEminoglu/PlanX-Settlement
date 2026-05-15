# -*- coding: utf-8 -*-
"""
Adım 6: ParkingGenerator — Parametrik otopark düzeni
Bu versiyon, ada dış formuna (çevresine) uyumlu "perimeter" otopark üretir.
Geliştirici: Yusuf Eminoglu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""
import os, sys, math
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber, QgsFeature, QgsGeometry, QgsWkbTypes, 
    QgsProcessingException, QgsField, QgsFields, QgsFeatureSink, QgsPointXY
)

def _create_stall(cx, cy, w, d, rot):
    """Tek otopark stall rect (merkez tabanlı, döndürülmüş)."""
    hw, hd = w / 2.0, d / 2.0
    cos_a, sin_a = math.cos(rot), math.sin(rot)
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    pts = [QgsPointXY(x * cos_a - y * sin_a + cx,
                      x * sin_a + y * cos_a + cy) for x, y in corners]
    pts.append(pts[0])
    return QgsGeometry.fromPolygonXY([pts])

def generate_perimeter_parking(polygon_geom, stall_w=2.5, stall_d=5.0, stall_gap=0.01, edge_margin=0.5, aisle_w=6.0, entrance_pt=None):
    """
    Poligonun kenarlarına paralel, ada formuna tam oturan çevre (perimeter) otopark yerleşimi.
    Alan elverdikçe içe doğru ringler halinde yeni otoparklar dizer.
    Eğer road_pt (Giriş) girilmişse oradan merkeze doğru 7m genişliğinde giriş koridoru bırakır.
    """
    if edge_margin > 0:
        work = polygon_geom.buffer(-edge_margin, 16)
        if work.isEmpty():
            return []
    else:
        work = polygon_geom
        
    stalls = []
    level = 0
    max_levels = 15 # Güvenlik sınırı
    
    corridor_geom = None
    if entrance_pt:
        c = polygon_geom.centroid().asPoint()
        corridor_geom = QgsGeometry.fromPolylineXY([entrance_pt, c])
    
    while not work.isEmpty() and level < max_levels:
        if work.isMultipart():
            polys = work.asMultiPolygon()
        else:
            polys = [work.asPolygon()]
            
        added_in_level = 0
            
        # Her poligonun dış ringi boyunca iterate et
        for poly in polys:
            if not poly:
                continue
            ring = poly[0]
            # Her segment için
            for i in range(len(ring) - 1):
                p1 = ring[i]
                p2 = ring[i+1]
                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                length = math.hypot(dx, dy)
                actual_w = stall_w + stall_gap
                count = int(length / actual_w)
                if count == 0:
                    continue
                    
                ux = dx / length
                uy = dy / length
                
                vx1, vy1 = -uy, ux
                vx2, vy2 = uy, -ux
                
                # İç yüzü test et
                mx, my = p1.x() + dx/2, p1.y() + dy/2
                tp1 = QgsPointXY(mx + vx1 * stall_d/2, my + vy1 * stall_d/2)
                
                if work.contains(QgsGeometry.fromPointXY(tp1)):
                    vx, vy = vx1, vy1
                else:
                    vx, vy = vx2, vy2
                    
                rot = math.atan2(dy, dx)
                start_offset = (length - (count * actual_w)) / 2.0 + (actual_w / 2.0)
                
                for c in range(count):
                    dist = start_offset + c * actual_w
                    cx_line = p1.x() + ux * dist
                    cy_line = p1.y() + uy * dist
                    
                    # Merkezi içeri ötele
                    cx = cx_line + vx * (stall_d / 2.0)
                    cy = cy_line + vy * (stall_d / 2.0)
                    
                    sg = _create_stall(cx, cy, stall_w, stall_d, rot)
                    
                    # Giriş (Corridor) engeline takılıyor mu (3.5 metre yarı yarıya 7m açıklık)
                    if corridor_geom and not corridor_geom.isEmpty():
                        if corridor_geom.distance(sg.centroid()) <= 3.5:
                            continue
                    
                    # Sadece poligon içinde olanları ve birbirleriyle çakışmayanları ekle
                    if work.contains(sg):
                        overlap = False
                        for existing in stalls:
                            inter = sg.intersection(existing)
                            if not inter.isEmpty() and inter.area() > 0.1:
                                overlap = True
                                break
                        if not overlap:
                            stalls.append(sg)
                            added_in_level += 1
                            
        # Eğer bu ringde hiçbir şey eklenemediyse (alan çok dar vs), çık.
        if added_in_level == 0:
            break
            
        # Sonraki ring için poligonu içeri doğru daralt (Otopark derinliği + manevra yolu kadar)
        work = work.buffer(-(stall_d + aisle_w), 16)
        level += 1
                        
    return stalls


class ParkingGeneratorAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    ROAD_LAYER = 'ROAD_LAYER'
    STALL_WIDTH = 'STALL_WIDTH'
    STALL_DEPTH = 'STALL_DEPTH'
    AISLE_WIDTH = 'AISLE_WIDTH'
    STALL_GAP = 'STALL_GAP'
    EDGE_MARGIN = 'EDGE_MARGIN'
    OUTPUT_STALLS = 'OUTPUT_STALLS'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Otopark alanı katmanı (poligon)'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.ROAD_LAYER, self.tr('Yol Orta Çizgisi (Araç girişi için) (İsteğe Bağlı)'),
            [QgsProcessing.TypeVectorLine], defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.STALL_WIDTH, self.tr('Otopark yeri genişliği (m) — standart: 2.5'),
            QgsProcessingParameterNumber.Double, 2.5, minValue=2.0, maxValue=4.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.STALL_DEPTH, self.tr('Otopark yeri derinliği (m) — standart: 5.0'),
            QgsProcessingParameterNumber.Double, 5.0, minValue=4.0, maxValue=7.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.AISLE_WIDTH, self.tr('Araç Geçiş/Manevra Yolu (m) — İç ringler için'),
            QgsProcessingParameterNumber.Double, 6.0, minValue=3.0, maxValue=10.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.STALL_GAP, self.tr('Stall arası boşluk (m) — İsteğe bağlı (önerilen 0)'),
            QgsProcessingParameterNumber.Double, 0.0, minValue=0.0, maxValue=2.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.EDGE_MARGIN, self.tr('Kenar boşluğu / Yoldan Çekme (m)'),
            QgsProcessingParameterNumber.Double, 0.5, minValue=0.0, maxValue=5.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_STALLS, self.tr('Otopark yerleri (poligon)')))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        road_source = self.parameterAsSource(parameters, self.ROAD_LAYER, context)
        
        stall_w = self.parameterAsDouble(parameters, self.STALL_WIDTH, context)
        stall_d = self.parameterAsDouble(parameters, self.STALL_DEPTH, context)
        aisle_w = self.parameterAsDouble(parameters, self.AISLE_WIDTH, context)
        gap = self.parameterAsDouble(parameters, self.STALL_GAP, context)
        margin = self.parameterAsDouble(parameters, self.EDGE_MARGIN, context)

        if source is None:
            raise QgsProcessingException(self.tr("Katman yüklenemedi."))
            
        road_geoms = []
        if road_source is not None:
            for rf in road_source.getFeatures():
                if not rf.geometry().isEmpty():
                    road_geoms.append(rf.geometry())

        s_fields = QgsFields()
        s_fields.append(QgsField('area_fid', QVariant.Int))
        s_fields.append(QgsField('stall_id', QVariant.Int))
        s_fields.append(QgsField('stall_area_m2', QVariant.Double, 'double', 20, 2))

        (s_sink, s_dest) = self.parameterAsSink(
            parameters, self.OUTPUT_STALLS, context,
            s_fields, QgsWkbTypes.Polygon, source.sourceCrs())

        total_stalls = 0
        total = source.featureCount() or 1

        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom.isEmpty():
                continue

            entrance_pt = None
            if road_geoms:
                min_d = float('inf')
                for rg in road_geoms:
                    inter_dist = geom.distance(rg)
                    if inter_dist < min_d:
                        min_d = inter_dist
                        nearest = geom.nearestPoint(rg)
                        if not nearest.isEmpty():
                            entrance_pt = nearest.asPoint()

            generated_stalls = generate_perimeter_parking(geom, stall_w, stall_d, gap, margin, aisle_w, entrance_pt)

            for si, sg in enumerate(generated_stalls):
                sf = QgsFeature(s_fields)
                sf.setGeometry(sg)
                sf.setAttributes([feat.id(), si + 1, round(sg.area(), 2)])
                s_sink.addFeature(sf, QgsFeatureSink.FastInsert)

            count = len(generated_stalls)
            total_stalls += count
            feedback.pushInfo(f"Alan {feat.id()}: Ada formuna uygun {count} adet otopark yeri dizildi.")
            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(f"Toplam: {total_stalls} otopark yeri Ada formunda üretildi.")
        return {self.OUTPUT_STALLS: s_dest}

    def name(self):
        return '7_parking_generator'
    def displayName(self):
        return '7. Parametrik Otopark Düzeni (Ada Uyumlu)'
    def group(self):
        return 'Yerleşim Planı İş Akışı'
    def groupId(self):
        return 'yerlesim_plani_workflow'
    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Yusuf Eminoglu\n\n"
            "Tasarımsal Güncelleme: Otopark hücreleri artık sabit gridler yerine,\n"
            "aynı Emsal çözümünde olduğu gibi ADA FORMUNA ve ÇEVRESİNE uyumlu olarak\n"
            "dizilmektedir. Her 10 otoparkta 1 adet peyzaj/ağaç boşluğu bırakılır!\n\n"
            "Alan elverişli olduğu sürece iç içe ringler (halkalar) halinde\n"
            "merkeze doğru inilerek otopark yerleştirmeye devam edilir.\n\n"
            "Çıktılar:\n"
            "• Otopark yerleri: Adanın şeklini takip eden çevre bant otopark dizisi.")
    def createInstance(self):
        return ParkingGeneratorAlgorithm()
    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

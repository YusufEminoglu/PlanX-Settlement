# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Özel Yardımcı Araç: Çizilen aks üzerinden otopark üretici (Line-based)
"""
import math
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber, QgsProcessingParameterEnum,
    QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsField, QgsFields, QgsFeatureSink, QgsPointXY
)

def _create_stall(cx, cy, w, d, rot):
    hw, hd = w / 2.0, d / 2.0
    cos_a, sin_a = math.cos(rot), math.sin(rot)
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    pts = [QgsPointXY(x * cos_a - y * sin_a + cx,
                      x * sin_a + y * cos_a + cy) for x, y in corners]
    pts.append(pts[0])
    return QgsGeometry.fromPolygonXY([pts])

def normalize_angle(angle):
    """Açıyı 0-360 arasına veya radyan için 0-2pi arasına modlar, bu math fonksiyonu değil yardımcı"""
    return angle % (2 * math.pi)

class HelperAxisParkingGeneratorAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    STALL_WIDTH = 'STALL_WIDTH'
    STALL_DEPTH = 'STALL_DEPTH'
    PARKING_ANGLE = 'PARKING_ANGLE'
    SIDE = 'SIDE'
    STALL_GAP = 'STALL_GAP'
    AXIS_OFFSET = 'AXIS_OFFSET'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Otopark Çizim Aksı (Çizgi)'),
            [QgsProcessing.TypeVectorLine]))
            
        self.addParameter(QgsProcessingParameterNumber(
            self.STALL_WIDTH, self.tr('Otopark yeri genişliği (m)'),
            QgsProcessingParameterNumber.Double, 2.5, minValue=2.0, maxValue=4.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.STALL_DEPTH, self.tr('Otopark yeri derinliği (m)'),
            QgsProcessingParameterNumber.Double, 5.0, minValue=4.0, maxValue=7.0))
            
        self.addParameter(QgsProcessingParameterEnum(
            self.PARKING_ANGLE, self.tr('Park açısı (Çizgiye Göre)'),
            options=['90° (Dik)', '60° (Açılı)', '45° (Açılı)', '0° (Paralel Park)'],
            defaultValue=0))
            
        self.addParameter(QgsProcessingParameterEnum(
            self.SIDE, self.tr('Oluşturma Yönü (Çizim Yönüne Göre)'),
            options=['Sağ', 'Sol', 'Her İki Taraf'],
            defaultValue=0))
            
        self.addParameter(QgsProcessingParameterNumber(
            self.STALL_GAP, self.tr('Hücreler arası boşluk (m)'),
            QgsProcessingParameterNumber.Double, 0.0, minValue=0.0, maxValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.AXIS_OFFSET, self.tr('Akstan uzaklık (m) - Çizgi ile otopark arası mesafe'),
            QgsProcessingParameterNumber.Double, 0.0, minValue=0.0, maxValue=5.0))
            
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Aks Otopark Yerleri (Poligon)')))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        stall_w = self.parameterAsDouble(parameters, self.STALL_WIDTH, context)
        stall_d = self.parameterAsDouble(parameters, self.STALL_DEPTH, context)
        angle_idx = self.parameterAsInt(parameters, self.PARKING_ANGLE, context)
        side_idx = self.parameterAsInt(parameters, self.SIDE, context)
        gap = self.parameterAsDouble(parameters, self.STALL_GAP, context)
        ax_offset = self.parameterAsDouble(parameters, self.AXIS_OFFSET, context)

        if source is None:
            raise QgsProcessingException(self.tr("Girdi katmanı yüklenemedi."))

        # 0: 90 deg, 1: 60 deg, 2: 45 deg, 3: 0 deg
        angle_map = {0: 90, 1: 60, 2: 45, 3: 0}
        p_angle = angle_map.get(angle_idx, 90)

        out_fields = QgsFields()
        out_fields.append(QgsField('aks_id', QVariant.Int))
        out_fields.append(QgsField('stall_no', QVariant.Int))
        out_fields.append(QgsField('alan_m2', QVariant.Double, 'double', 20, 2))

        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Polygon, source.sourceCrs())

        total = source.featureCount() or 1
        generated = 0

        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
                
            geom = feat.geometry()
            if geom.isEmpty() or geom.type() != QgsWkbTypes.LineGeometry:
                continue

            if geom.isMultipart():
                lines = geom.asMultiPolyline()
            else:
                lines = [geom.asPolyline()]

            for line in lines:
                if len(line) < 2:
                    continue
                    
                # Feature'dan attribute'ları okumaya çalış
                feat_angle_str = feat.attribute('park_acisi') if feat.fields().indexOf('park_acisi') != -1 else None
                feat_side_str = feat.attribute('olusturma_yonu') if feat.fields().indexOf('olusturma_yonu') != -1 else None
                feat_gap = feat.attribute('hücre_bosluk') if feat.fields().indexOf('hücre_bosluk') != -1 else None
                feat_offset = feat.attribute('aks_mesafesi') if feat.fields().indexOf('aks_mesafesi') != -1 else None

                # Veri tiplerini ve değerlerini parse et
                # park_acisi: 0, 1, 2, 3 dönebilir
                if feat_angle_str is not None and str(feat_angle_str).isdigit():
                    local_p_angle = angle_map.get(int(feat_angle_str), p_angle)
                else:
                    local_p_angle = p_angle
                    
                # olusturma_yonu: 0, 1, 2 dönebilir
                if feat_side_str is not None and str(feat_side_str).isdigit():
                    local_side_idx = int(feat_side_str)
                else:
                    local_side_idx = side_idx
                    
                local_gap = float(feat_gap) if feat_gap is not None and str(feat_gap).replace('.','').isdigit() else gap
                local_offset = float(feat_offset) if feat_offset is not None and str(feat_offset).replace('.','').isdigit() else ax_offset

                # Segment bazlı üret
                for j in range(len(line) - 1):
                    p1 = line[j]
                    p2 = line[j+1]
                    
                    dx = p2.x() - p1.x()
                    dy = p2.y() - p1.y()
                    length = math.hypot(dx, dy)
                    if length < stall_w:
                        continue
                        
                    ux = dx / length
                    uy = dy / length
                    line_angle = math.atan2(dy, dx)
                    
                    # Açı ve efektif yürüme boyu düzeltmeleri
                    if local_p_angle == 60:
                        rad = math.radians(30)
                        eff_w = stall_w / math.cos(rad)
                        eff_d = stall_d * math.cos(rad) + stall_w * math.sin(rad)
                        stall_rot = line_angle - rad
                    elif local_p_angle == 45:
                        rad = math.radians(45)
                        eff_w = stall_w / math.cos(rad)
                        eff_d = stall_d * math.cos(rad) + stall_w * math.sin(rad)
                        stall_rot = line_angle - rad
                    elif local_p_angle == 0:
                        eff_w = stall_d
                        eff_d = stall_w
                        stall_rot = line_angle
                    else:
                        eff_w = stall_w
                        eff_d = stall_d
                        stall_rot = line_angle
                    
                    actual_w = eff_w + local_gap
                    count = int(length / actual_w)
                    if count == 0:
                        continue
                        
                    start_offset = (length - (count * actual_w)) / 2.0 + (actual_w / 2.0)
                    
                    sides = []
                    if local_side_idx in (0, 2): sides.append('right')
                    if local_side_idx in (1, 2): sides.append('left')
                    
                    for s_dir in sides:
                        # Dik vektör: çizim yönüne sağ veya sol
                        if s_dir == 'right':
                            vx, vy = uy, -ux
                            rot_offset = stall_rot
                        else:
                            vx, vy = -uy, ux
                            rot_offset = stall_rot if local_p_angle in (0, 90) else line_angle + (line_angle - stall_rot)
                            
                        # Merkezleri çizgi üzerinde diz ama tam yapının dışına offsetle
                        for c_idx in range(count):
                            dist = start_offset + c_idx * actual_w
                            cx_line = p1.x() + ux * dist
                            cy_line = p1.y() + uy * dist
                            
                            cx = cx_line + vx * (eff_d / 2.0 + local_offset)
                            cy = cy_line + vy * (eff_d / 2.0 + local_offset)
                            
                            sg = _create_stall(cx, cy, stall_w, stall_d, rot_offset)
                            if not sg.isEmpty():
                                generated += 1
                                nf = QgsFeature(out_fields)
                                nf.setGeometry(sg)
                                nf.setAttributes([feat.id(), generated, round(sg.area(), 2)])
                                sink.addFeature(nf, QgsFeatureSink.FastInsert)

            feedback.setProgress(int((i + 1) / total * 100))

        feedback.pushInfo(f"Toplam: {generated} otopark yeri aks üzerinden üretildi.")
        return {self.OUTPUT: dest_id}

    def name(self):
        return 'helper_axis_parking_generator'

    def displayName(self):
        return 'Çizgi Çerçevesinde Otopark Oluştur (Helper)'

    def group(self):
        return 'Otopark Araçları'

    def groupId(self):
        return 'parking_helpers'

    def shortHelpString(self):
        return self.tr(
            "Çizgisel bir hatta paralel, dik veya açılı otopark dizileri oluşturur.\n\n"
            "Çizilen doğrunun 'sağına' veya 'soluna' parametrik olarak boşluksuz otopark atar.")

    def createInstance(self):
        return HelperAxisParkingGeneratorAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate('Processing', s)

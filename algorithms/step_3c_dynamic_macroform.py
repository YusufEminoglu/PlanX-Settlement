# -*- coding: utf-8 -*-
"""
Adım 3C: Dynamic Macroform — Prosedürel bina formu üretici

Gerçekçi mimari kısıtlar:
• Minimum kanat derinliği ≥ 7m (yapısal minimum)
• Minimum kanat genişliği ≥ 5m
• Aspect ratio kontrollü
• Dropdown ile çoklu form seçimi (tiklenebilir)

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

import random
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsFeature,
    QgsGeometry,
    QgsProcessingException,
    QgsField,
    QgsFields,
    QgsFeatureSink,
    QgsPointXY,
)

# ═══════════════════════════════════════════════════════════════════════
# MİMARİ KISITLAR
# ═══════════════════════════════════════════════════════════════════════
MIN_WING_DEPTH = 7.0  # Minimum kanat derinliği (m) — yapısal zorunluluk
MIN_WING_WIDTH = 5.0  # Minimum kanat genişliği (m)

# ═══════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════


def _rect(x, y, w, h):
    """Dikdörtgen poligon (sol-alt köşe tabanlı)."""
    pts = [
        QgsPointXY(x, y),
        QgsPointXY(x + w, y),
        QgsPointXY(x + w, y + h),
        QgsPointXY(x, y + h),
        QgsPointXY(x, y),
    ]
    return QgsGeometry.fromPolygonXY([pts])


def _can_fit(w, h, min_depth=MIN_WING_DEPTH):
    """Verilen boyutlara uygun form üretilebilir mi?"""
    return w >= min_depth and h >= min_depth


# ═══════════════════════════════════════════════════════════════════════
# FORM ÜRETİCİLER — Her biri (w, h, rng) alır, (geom, type_name) döner
# ═══════════════════════════════════════════════════════════════════════


def gen_dikdortgen(w, h, rng):
    """Basit dikdörtgen — hafif içe daralmalarla."""
    shrink_w = rng.uniform(0.80, 0.95)
    bw = max(MIN_WING_WIDTH, w * shrink_w)
    ox = (w - bw) / 2
    return _rect(ox, 0, bw, h), "dikdortgen"


def gen_L(w, h, rng):
    """L formu — ana gövde + yan kanat (≥7m derinlik)."""
    # Ana gövde: en az 7m genişlikte, tam yükseklikte
    main_w = max(MIN_WING_DEPTH, w * rng.uniform(0.35, 0.55))
    # Alt kanat: tam genişlikte, en az 7m yükseklikte
    wing_h = max(MIN_WING_DEPTH, h * rng.uniform(0.3, 0.5))

    if rng.random() > 0.5:  # Ayna: sol veya sağ
        r1 = _rect(0, 0, main_w, h)
        r2 = _rect(0, 0, w, wing_h)
    else:
        r1 = _rect(w - main_w, 0, main_w, h)
        r2 = _rect(0, 0, w, wing_h)
    return r1.combine(r2), "L"


def gen_L_ters(w, h, rng):
    """Ters L — kanat üstte."""
    main_w = max(MIN_WING_DEPTH, w * rng.uniform(0.35, 0.55))
    wing_h = max(MIN_WING_DEPTH, h * rng.uniform(0.3, 0.5))

    if rng.random() > 0.5:
        r1 = _rect(0, 0, main_w, h)
        r2 = _rect(0, h - wing_h, w, wing_h)
    else:
        r1 = _rect(w - main_w, 0, main_w, h)
        r2 = _rect(0, h - wing_h, w, wing_h)
    return r1.combine(r2), "L_ters"


def gen_U(w, h, rng):
    """U formu — iki kol + alt bağlantı (tüm kanatlar ≥7m)."""
    arm_w = max(MIN_WING_DEPTH, w * rng.uniform(0.25, 0.38))
    base_h = max(MIN_WING_DEPTH, h * rng.uniform(0.25, 0.38))
    gap = w - 2 * arm_w
    if gap < MIN_WING_WIDTH:
        arm_w = max(MIN_WING_DEPTH, (w - MIN_WING_WIDTH) / 2)

    r_left = _rect(0, 0, arm_w, h)
    r_right = _rect(w - arm_w, 0, arm_w, h)
    r_base = _rect(0, 0, w, base_h)
    return r_left.combine(r_right).combine(r_base), "U"


def gen_T(w, h, rng):
    """T formu — alt gövde + üst baş (kanatlar ≥7m)."""
    stem_w = max(MIN_WING_DEPTH, w * rng.uniform(0.35, 0.50))
    head_h = max(MIN_WING_DEPTH, h * rng.uniform(0.30, 0.45))
    stem_h = h - head_h

    stem_x = (w - stem_w) / 2
    r_stem = _rect(stem_x, 0, stem_w, stem_h)
    r_head = _rect(0, stem_h, w, head_h)
    return r_stem.combine(r_head), "T"


def gen_T_ters(w, h, rng):
    """Ters T — kafa altta."""
    stem_w = max(MIN_WING_DEPTH, w * rng.uniform(0.35, 0.50))
    head_h = max(MIN_WING_DEPTH, h * rng.uniform(0.30, 0.45))
    stem_h = h - head_h

    stem_x = (w - stem_w) / 2
    r_head = _rect(0, 0, w, head_h)
    r_stem = _rect(stem_x, head_h, stem_w, stem_h)
    return r_head.combine(r_stem), "T_ters"


def gen_Z(w, h, rng):
    """Z/S formu — iki kaydırılmış blok (≥7m)."""
    block_w = max(MIN_WING_DEPTH, w * rng.uniform(0.50, 0.70))
    half_h = h / 2
    overlap = h * 0.15  # Bloklar arasında örtüşme
    shift = max(0, w - block_w)

    r1 = _rect(0, 0, block_w, half_h + overlap)
    r2 = _rect(shift, half_h - overlap, block_w, half_h + overlap)
    combined = r1.combine(r2)
    # Sınır kontrolü
    bbox_clip = _rect(0, 0, w, h)
    return combined.intersection(bbox_clip), "Z"


def gen_H(w, h, rng):
    """H formu — iki kol + orta bağlantı."""
    arm_w = max(MIN_WING_DEPTH, w * rng.uniform(0.25, 0.35))
    bridge_h = max(MIN_WING_DEPTH, h * rng.uniform(0.25, 0.40))
    bridge_y = (h - bridge_h) / 2

    r_left = _rect(0, 0, arm_w, h)
    r_right = _rect(w - arm_w, 0, arm_w, h)
    r_bridge = _rect(0, bridge_y, w, bridge_h)
    return r_left.combine(r_right).combine(r_bridge), "H"


def gen_C(w, h, rng):
    """C/parantez formu — üç kanat, bir taraf açık."""
    arm_depth = max(MIN_WING_DEPTH, w * rng.uniform(0.30, 0.50))
    top_h = max(MIN_WING_DEPTH, h * rng.uniform(0.20, 0.30))
    bot_h = max(MIN_WING_DEPTH, h * rng.uniform(0.20, 0.30))

    r_spine = _rect(0, 0, arm_depth, h)
    r_top = _rect(0, h - top_h, w, top_h)
    r_bot = _rect(0, 0, w, bot_h)
    return r_spine.combine(r_top).combine(r_bot), "C"


def gen_avlu(w, h, rng):
    """Avlulu (O) — dış - iç, minimum 7m duvar."""
    wall = max(MIN_WING_DEPTH, min(w, h) * rng.uniform(0.20, 0.30))
    inner_w = w - 2 * wall
    inner_h = h - 2 * wall
    if inner_w < 3 or inner_h < 3:
        return _rect(0, 0, w, h), "dikdortgen"
    outer = _rect(0, 0, w, h)
    inner = _rect(wall, wall, inner_w, inner_h)
    return outer.difference(inner), "avlu"


def gen_E(w, h, rng):
    """E formu — omurga + 3 paralel kanat."""
    spine_w = max(MIN_WING_DEPTH, w * rng.uniform(0.20, 0.30))
    wing_h = max(MIN_WING_DEPTH, h * rng.uniform(0.18, 0.28))
    gap = (h - 3 * wing_h) / 2
    if gap < 2:
        wing_h = max(MIN_WING_DEPTH, (h - 4) / 3)
        gap = max(1, (h - 3 * wing_h) / 2)

    r_spine = _rect(0, 0, spine_w, h)
    r_w1 = _rect(0, 0, w, wing_h)
    r_w2 = _rect(0, wing_h + gap, w, wing_h)
    r_w3 = _rect(0, h - wing_h, w, wing_h)
    return r_spine.combine(r_w1).combine(r_w2).combine(r_w3), "E"


def gen_artı(w, h, rng):
    """+ (artı) formu — iki dik kol (≥7m)."""
    v_w = max(MIN_WING_DEPTH, w * rng.uniform(0.35, 0.50))
    h_h = max(MIN_WING_DEPTH, h * rng.uniform(0.35, 0.50))

    r_vert = _rect((w - v_w) / 2, 0, v_w, h)
    r_horiz = _rect(0, (h - h_h) / 2, w, h_h)
    return r_vert.combine(r_horiz), "arti"


# ── Form haritası ────────────────────────────────────────────────────
_FORM_GENERATORS = {
    "dikdortgen": gen_dikdortgen,
    "L": gen_L,
    "L_ters": gen_L_ters,
    "U": gen_U,
    "T": gen_T,
    "T_ters": gen_T_ters,
    "Z": gen_Z,
    "H": gen_H,
    "C": gen_C,
    "avlu": gen_avlu,
    "E": gen_E,
    "arti": gen_artı,
}

_FORM_NAMES = list(_FORM_GENERATORS.keys())
_FORM_LABELS = [
    "Dikdörtgen (I)",
    "L",
    "Ters L",
    "U",
    "T",
    "Ters T",
    "Z (kaydırmalı)",
    "H",
    "C (parantez)",
    "Avlulu (O)",
    "E (tarak)",
    "+ (artı)",
]


def generate_dynamic_form(
    bbox_geom, form_type="rastgele", allowed_forms=None, rng=None
):
    """
    Buildable bbox içine prosedürel bina formu üretir.
    Tüm kanatlar ≥ 7m derinlikte olur.
    """
    if rng is None:
        rng = random.Random()

    obb = bbox_geom.orientedMinimumBoundingBox()
    if not obb or len(obb) < 5:
        bb = bbox_geom.boundingBox()
        w, h = bb.width(), bb.height()
        angle = 0
        center = QgsPointXY(bb.center())
    else:
        obb_geom, _, angle, w, h = obb
        center = obb_geom.centroid().asPoint()

    if w < h:
        w, h = h, w
        angle += 90

    # Form seç
    pool = allowed_forms if allowed_forms else _FORM_NAMES
    if form_type != "rastgele" and form_type in _FORM_GENERATORS:
        chosen = form_type
    else:
        # Boyut uyumlu formları filtrele
        feasible = []
        for f in pool:
            if f in ("avlu", "H", "E") and (w < 20 or h < 20):
                continue  # Küçük parsellere karmaşık form uygulanmaz
            if f in ("U", "C") and (w < 15 or h < 15):
                continue
            feasible.append(f)
        if not feasible:
            feasible = ["dikdortgen"]
        chosen = rng.choice(feasible)

    gen_func = _FORM_GENERATORS.get(chosen, gen_dikdortgen)
    form_geom, actual_type = gen_func(w, h, rng)

    if form_geom.isEmpty():
        form_geom, actual_type = gen_dikdortgen(w, h, rng)

    # Formu bbox'a hizala: rotate + translate
    form_center = form_geom.centroid().asPoint()
    if abs(angle) > 0.1:
        form_geom.rotate(angle, form_center)
    new_center = form_geom.centroid().asPoint()
    form_geom.translate(center.x() - new_center.x(), center.y() - new_center.y())

    # Bbox ile kırp
    form_geom = form_geom.intersection(bbox_geom)
    if form_geom.isEmpty():
        form_geom = bbox_geom.buffer(-min(w, h) * 0.05, 8)
        actual_type = "fallback"

    return form_geom, actual_type


# ═══════════════════════════════════════════════════════════════════════
# PROCESSING ALGORİTMASI
# ═══════════════════════════════════════════════════════════════════════


class DynamicMacroformAlgorithm(QgsProcessingAlgorithm):
    INPUT_BUILDINGS = "INPUT_BUILDINGS"
    FORM_TYPE = "FORM_TYPE"
    ALLOWED_FORMS = "ALLOWED_FORMS"
    DIVERSITY = "DIVERSITY"
    RANDOM_SEED = "RANDOM_SEED"
    OUTPUT = "OUTPUT"

    _TYPE_OPTIONS = ["Rastgele (karışık)", "Belirli formlar (aşağıdan seçin)"]

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_BUILDINGS,
                self.tr("Bina taban alanı katmanı (Adım 3 çıktısı — buildable bbox)"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.FORM_TYPE,
                self.tr("Form seçim modu"),
                options=self._TYPE_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ALLOWED_FORMS,
                self.tr("İzin verilen formlar (tikleyerek seçin)"),
                options=_FORM_LABELS,
                allowMultiple=True,
                defaultValue=list(range(len(_FORM_LABELS))),
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DIVERSITY,
                self.tr(
                    "Çeşitlilik — ardışık parsellerde aynı form tekrarlanmasın (1-5)"
                ),
                QgsProcessingParameterNumber.Integer,
                3,
                minValue=1,
                maxValue=5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RANDOM_SEED,
                self.tr("Rastgele tohum (0=tamamen rastgele, >0=tekrarlanabilir)"),
                QgsProcessingParameterNumber.Integer,
                0,
                minValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Dinamik formlu binalar")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        b_source = self.parameterAsSource(parameters, self.INPUT_BUILDINGS, context)
        mode_idx = self.parameterAsInt(parameters, self.FORM_TYPE, context)
        allowed_idx = self.parameterAsEnums(parameters, self.ALLOWED_FORMS, context)
        diversity = self.parameterAsInt(parameters, self.DIVERSITY, context)
        seed = self.parameterAsInt(parameters, self.RANDOM_SEED, context)

        if b_source is None:
            raise QgsProcessingException(self.tr("Girdi katmanı yüklenemedi."))

        # İzin verilen formları belirle
        if mode_idx == 1 and allowed_idx:
            allowed = [_FORM_NAMES[i] for i in allowed_idx if i < len(_FORM_NAMES)]
        else:
            allowed = _FORM_NAMES[:]

        rng = random.Random(seed if seed > 0 else None)

        out_fields = QgsFields()
        for f in b_source.fields():
            out_fields.append(f)
        out_fields.append(QgsField("form_tipi", QVariant.String, "string", 20))
        out_fields.append(QgsField("form_alan_m2", QVariant.Double, "double", 20, 2))
        out_fields.append(QgsField("bbox_doluluk", QVariant.Double, "double", 20, 4))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            b_source.wkbType(),
            b_source.sourceCrs(),
        )

        total = b_source.featureCount() or 1
        placed = 0
        last_forms = []

        for i, feat in enumerate(b_source.getFeatures()):
            if feedback.isCanceled():
                break
            bbox_geom = feat.geometry()
            if bbox_geom.isEmpty():
                continue
            bbox_area = bbox_geom.area()

            # Çeşitlilik kontrolü
            if diversity > 1 and len(last_forms) > 0:
                pool = [
                    f
                    for f in allowed
                    if f not in last_forms[-min(diversity, len(last_forms)) :]
                ]
                if not pool:
                    pool = allowed[:]
            else:
                pool = allowed[:]

            form_type = rng.choice(pool)
            form_geom, actual_type = generate_dynamic_form(
                bbox_geom, form_type, allowed, rng
            )

            if form_geom.isEmpty():
                continue

            last_forms.append(actual_type)
            if len(last_forms) > 10:
                last_forms.pop(0)

            form_area = form_geom.area()
            doluluk = form_area / bbox_area if bbox_area > 0 else 0

            nf = QgsFeature(out_fields)
            nf.setGeometry(form_geom)
            attrs = list(feat.attributes()) + [
                actual_type,
                round(form_area, 2),
                round(doluluk, 4),
            ]
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.FastInsert)
            placed += 1
            feedback.setProgress(int((i + 1) / total * 100))

        form_counts = {}
        for f in last_forms:
            form_counts[f] = form_counts.get(f, 0) + 1
        feedback.pushInfo(f"✅ {placed} bina için dinamik form üretildi.")
        feedback.pushInfo(f"Form dağılımı: {form_counts}")
        return {self.OUTPUT: dest_id}

    def name(self):
        return "3c_dynamic_macroform"

    def displayName(self):
        return "3C. Dinamik Bina Formu (Prosedürel)"

    def group(self):
        return "Yerleşim Planı İş Akışı"

    def groupId(self):
        return "yerlesim_plani_workflow"

    def shortHelpString(self):
        return self.tr(
            "━━━ planX — Yerleşim Planı Araç Seti ━━━\n"
            "Geliştirici: Araş.Gör. Yusuf Eminoğlu\n\n"
            "Prosedürel bina formu üretici.\n"
            "Minimum kanat derinliği: 7m (mimari zorunluluk)\n\n"
            "12 form tipi (tiklenebilir):\n"
            "• Dikdörtgen — hafif ölçek varyasyonlu\n"
            "• L / Ters L — köşe çıkıntılı (ayna rastgele)\n"
            "• U — iki kol + alt bağlantı, avlu açık\n"
            "• T / Ters T — gövde + baş\n"
            "• Z — kaydırılmış iki blok\n"
            "• H — iki kol + orta bağlantı\n"
            "• C — üç kanat, bir taraf açık\n"
            "• Avlulu (O) — iç boşluklu, duvar ≥7m\n"
            "• E (tarak) — omurga + 3 paralel kanat\n"
            "• + (artı) — iki dik kol\n\n"
            "Kısıtlar:\n"
            "• Tüm kanatlar ≥ 7m derinlikte\n"
            "• Küçük parsellere karmaşık formlar uygulanmaz\n"
            "• Çeşitlilik parametresi ardışık tekrarı önler"
        )

    def createInstance(self):
        return DynamicMacroformAlgorithm()

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

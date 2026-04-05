# -*- coding: utf-8 -*-
"""
planX — Attribute Manager
Öznitelik sütun yönetimi ve güncelleme araçları.
"""
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField


# Cephe analizi sütunları
FACADE_FIELDS = [
    QgsField('facade_front', QVariant.String, 'string', 100),
    QgsField('facade_side', QVariant.String, 'string', 100),
    QgsField('facade_back', QVariant.String, 'string', 100),
    QgsField('facade_count', QVariant.Int),
    QgsField('is_corner', QVariant.Bool),
    QgsField('front_direction', QVariant.String, 'string', 20),
]


def add_facade_fields(fields):
    """Mevcut QgsFields nesnesine cephe alanlarını ekler."""
    for f in FACADE_FIELDS:
        fields.append(QgsField(f))
    return fields


def facade_attrs_from_classification(classification):
    """
    classify_all_edges() çıktısından öznitelik değerleri üretir.
    Returns: list of values in FACADE_FIELDS order
    """
    return [
        ','.join(str(i) for i in classification.get('front', [])),
        ','.join(str(i) for i in classification.get('side', [])),
        ','.join(str(i) for i in classification.get('back', [])),
        classification.get('facade_count', 0),
        classification.get('is_corner', False),
        classification.get('front_direction', ''),
    ]

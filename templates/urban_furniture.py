# -*- coding: utf-8 -*-
"""
planX — Kentsel Donatı Şablonu Üretici
Yerleşim planında kullanılacak kent mobilyaları (bank, aydınlatma, çöp kovası vb.)
için QGIS sembol kütüphanesi oluşturur.

Kullanıcı bu nokta katmanından elemanları seçerek harita üzerine konumlandırır.

Geliştirici: Araş.Gör. Yusuf Eminoğlu
planX Geospatial Advanced Tools — Yerleşim Planı Araç Seti
"""

import os

# ── Kent mobilyası tanımları ──────────────────────────────────────────
URBAN_FURNITURE = [
    {
        'id': 'bank',
        'name_tr': 'Oturma Bankı',
        'name_en': 'Bench',
        'category': 'oturma',
        'svg': 'furniture_bench.svg',
        'default_size_mm': 3.0,
        'color': '#8B7355',
    },
    {
        'id': 'aydinlatma',
        'name_tr': 'Aydınlatma Direği',
        'name_en': 'Street Light',
        'category': 'aydinlatma',
        'svg': 'furniture_light.svg',
        'default_size_mm': 2.5,
        'color': '#FFD700',
    },
    {
        'id': 'cop_kovasi',
        'name_tr': 'Çöp Kovası',
        'name_en': 'Trash Bin',
        'category': 'temizlik',
        'svg': 'furniture_trash.svg',
        'default_size_mm': 2.0,
        'color': '#4A5568',
    },
    {
        'id': 'yangin_muslubu',
        'name_tr': 'Yangın Musluğu',
        'name_en': 'Fire Hydrant',
        'category': 'guvenlik',
        'svg': 'furniture_hydrant.svg',
        'default_size_mm': 2.5,
        'color': '#E53E3E',
    },
    {
        'id': 'agac',
        'name_tr': 'Ağaç',
        'name_en': 'Tree',
        'category': 'peyzaj',
        'svg': 'furniture_tree.svg',
        'default_size_mm': 4.0,
        'color': '#38A169',
    },
    {
        'id': 'bilgi_panosu',
        'name_tr': 'Bilgi Panosu',
        'name_en': 'Information Board',
        'category': 'bilgilendirme',
        'svg': 'furniture_infoboard.svg',
        'default_size_mm': 2.5,
        'color': '#4A5568',
    },
    {
        'id': 'cesme',
        'name_tr': 'Çeşme / Su Öğesi',
        'name_en': 'Fountain',
        'category': 'peyzaj',
        'svg': 'furniture_fountain.svg',
        'default_size_mm': 3.5,
        'color': '#3182CE',
    },
    {
        'id': 'bisiklet_park',
        'name_tr': 'Bisiklet Parkı',
        'name_en': 'Bike Rack',
        'category': 'ulasim',
        'svg': 'furniture_bench.svg',  # Aynı SVG, farklı renk
        'default_size_mm': 3.0,
        'color': '#DD6B20',
    },
    {
        'id': 'elektrik_sarj',
        'name_tr': 'Elektrikli Araç Şarj İstasyonu',
        'name_en': 'EV Charging Station',
        'category': 'ulasim',
        'svg': 'furniture_light.svg',
        'default_size_mm': 3.0,
        'color': '#38B2AC',
    },
    {
        'id': 'oyun_alani',
        'name_tr': 'Çocuk Oyun Alanı İşareti',
        'name_en': 'Playground Marker',
        'category': 'rekreasyon',
        'svg': 'furniture_fountain.svg',
        'default_size_mm': 5.0,
        'color': '#ED8936',
    },
    {
        'id': 'araba',
        'name_tr': 'Araba',
        'name_en': 'Car',
        'category': 'ulasim',
        'svg': 'furniture_car.svg',
        'default_size_mm': 6.0,  # Oransal olarak büyük
        'color': '#607D8B',
    },
    {
        'id': 'trafik_isigi',
        'name_tr': 'Trafik Işığı',
        'name_en': 'Traffic Light',
        'category': 'ulasim',
        'svg': 'furniture_traffic_light.svg',
        'default_size_mm': 2.5,
        'color': '#333333',
    },
]


def get_furniture_catalog():
    """Kent mobilyası kataloğunu döner."""
    return URBAN_FURNITURE


def get_icon_dir():
    """İkon dizin yolunu döner."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons')


def get_svg_path(svg_filename):
    """Tam SVG dosya yolunu döner."""
    return os.path.join(get_icon_dir(), svg_filename)

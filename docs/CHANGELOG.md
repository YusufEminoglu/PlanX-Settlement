# Changelog

## v0.3.0 (2026-04-04)
- **Güçlendirilmiş ParcelFlux Algorithm:** Sıra genişlik asimetrisi özelliği eklendi (Kuzey/Güney parsellerin bağımsız spacing aralığı). Min alan hesaplamaları düzenlendi.
- **Dinamik Prosedürel Makroform:** "Şablon" bağımlılığı kaldırılarak prosedürel yapı üretim motoru getirildi. Artık minimum kanat kalınlığı >7m olan 12 farklı kentsel parsel kütle tipolojisi (I, L, U, E vb.) hesaplanarak üretiliyor.
- **Akıllı Otopark Motoru:** Otopark motoruna "Input Roads" yeteneği eklendi. OBB'ye göre hizalamanın yanı sıra en yakın mevcut yol ağıyla otopark modülünün mantıksal ve geometrik rotasyonu sağlandı. "Otopark Giriş Çizgisi" eklendi.
- **QGIS 3.40 Uyum Optimizasyonları:** Core `Hard Surface Engine` API revizyonlarına bağlı çökme problemleri inline buffer çözümleriyle stabilize edildi.
- **Hata Giderme:** Urban Furniture (Kentsel Donatı) svg sembol limiti hataları çözümlendi ve kapasiteleri 255'e artırıldı.

## v0.2.0 (2026-04-03)
- Geliştirici kimliği ve "planX Geospatial Advanced Tools" marka referansları arayüze entegre edildi.
- QGIS API'de meydana gelen Buffer Geometry metodolojisi güncellendi. OBB yapısı parking generatorta iyileştirildi.

## v0.1.0 (2026-04-02)
- İlk sürüm: 9 aşamalı yerleşim planı üretim hattı.
- Temel ParcelFlux, FacadeDetector, Coverage footprint.

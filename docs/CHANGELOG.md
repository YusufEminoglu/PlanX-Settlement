# Changelog

## v0.5.2 (2026-05-15)
- **Release refresh:** Local workflow updates are packaged for Plugin Hub with standardized author/email metadata and stable release flags.
- **Step 3 workflow:** Detached, attached, block and FAR footprint variants are published with their dedicated icons and provider ordering.
- **Parking helpers:** Axis-layer and axis-based parking generation helpers are included in the released Processing provider.

## v0.5.0 (2026-04-11)
- **Ada ID Saklama:** Step 1 artık her parsel için `ada_id` ve `parcel_id` türevli kimlik bilgilerini sonraki adımlara taşır.
- **Ayrı Step 3 Akışları:** Ayrık, bitişik, blok ve FAR coverage footprint üretimleri ayrı algoritmalara bölündü.
- **Bitişik / Blok Grup Mantığı:** Aynı ada içindeki yan komşu parseller gruplanarak bitişik nizamda kesintisiz, blok nizamda ise ikili / gerektiğinde üçlü footprint kurgusu eklendi.
- **Ada Bazlı FAR Revizyonu:** Emsal çözümü artık ada grupları üzerinde çalışır; min / max bina alanı ve binalar arası açıklık hesabı buna göre yürütülür.

## v0.4.0 (2026-04-11)
- **Yapı Nizamı Destekli CoverageFootprint:** Step 3 artık seçilebilir `nizam` sütunundan `A / B / BL` değerlerini okuyarak ayrık, bitişik ve blok nizam için farklı setback mantıkları uygular.
- **Yeni FAR Footprint Adımı:** `step_3_coverage_footprint_far.py` ile emsal ve yençok verilerinden ada ölçeğinde parametrik footprint üretimi eklendi.
- **Ada Bazlı Yerleşim Kuralları:** FAR çözümünde adanın tüm çevresinde sabit 10m yaklaşma mesafesi, kat adedine bağlı yan bahçe hesabı ve binalar arası minimum açıklık kurgulandı.

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

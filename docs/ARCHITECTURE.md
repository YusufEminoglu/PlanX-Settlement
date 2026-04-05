# Mimari (Architecture)

## Genel Mimari
Eklenti QGIS'in yerleşik `Processing Toolbox` (İşlem Kutusu) ekosistemini kullanır. Tüm algoritmalar `QgsProcessingAlgorithm` sınıfından miras alarak yazılmıştır ve birbirini zincirleme takip eden geometrik/mekansal işlemler bütünü olarak dizayn edilmiştir. Geliştirici imzası (`Araş.Gör. Yusuf Eminoğlu - planX Geospatial Advanced Tools`) ile tüm algoritmalarda merkezi kimlik sağlanmıştır.

## Klasör Yapısı
- `algorithms/` — 9 aşamalı Processing algoritmaları ve genel donatı (urban furniture) üretim araçları
- `core/` — Motor modülleri. Çekirdek algoritmalar burada soyutlanmıştır. (geometry, facade, setback, macroform, parking, hard surface engine)
- `sketcher/` — CAD benzeri çizim araçları (Faz 1: fillet, extend)
- `sketcher_advanced/` — Gelişmiş CAD araçları (Faz 2)
- `icons/` — SVG ikonlar, kentsel donatılar (ağaçlar, banklar vs.)
- `styles/` — QML stil dosyaları, hazır semboloji şemaları
- `i18n/` — Çokdillilik

## Tasarım İlkeleri
1. **Modüler & Prosedürel**: Her algoritma tek başına çalışabileceği gibi dış girdilere de uyumlu (Örn: `Dynamic Macroform` modülü parametrik ölçüler alır ve kendi geometrik poligonlarını procedürel olarak üretir).
2. **Sıralı İşlem**: İş akışı 1→8 sırasıyla ilerler.
3. **Esnek Meta-Veri API'si**: Setback/TAKS gibi değerler kullanıcı formları yerini parselin kendi attribute (öznitelik) altyapısından organik şekilde okunarak alınır. 
4. **QGIS Versiyon Toleransı**: Python'daki API değişikliklerine (`QgsGeometry.buffer()` parametre farklılıkları vb.) karşı inline test-fallback mekanizmaları (try/except safe check) işler. 

## İşleme Motorları
- **ParcelFlux Engine**: Bölme yönünü OBB (Oriented Bounding Box) analizleriyle hesaplar, Fishbone Offset algoritmik gürültü yöntemi ile balıksırtı rastgeleliği verir ve genlik asimetrisi ile poligonları birbirinden bağımsız sıra genişliklerine göre tahsis eder.
- **Otopark Engine**: Trigometrik uzamsal koordinatları hesaplayarak poligon içerisine alan doldurur (space allocation). Çekirdek OBB ve Yol (Nearest Point) mantığına dayanır.

## CRS Desteği
- Uygulanabilir Ön Tanımlı CRS'ler: EPSG:5253, 32635, 2319
- Öntanımlı çalışma bölgesi: İzmir Bergama ölçek ve projeksiyon kuralları esas alınarak modifiye edilmiştir.

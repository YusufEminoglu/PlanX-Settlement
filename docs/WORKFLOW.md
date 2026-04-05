# İş Akışı (Workflow)

## Sıralı Adımlar

```
Ada Katmanı (Polygon)  ─→  1. ParcelFlux  ─→  Parseller
                                                  │
Yol Katmanı (Line)  ────→  2. FacadeDetector  ←──┘
                                    │
                           Cephe bilgili parseller
                                    │
                           3. CoverageFootprint  ─→  Bina taban alanları (Maximum Bbox)
                                    │
                           3C. Dinamik Macroform (Prosedürel Form Üretimi)  ─→  Formlu binalar
                                    │
                           4. BuildingOptimizer  ─→  Kontrol raporu
                                    │
                           5. HardSurface  ─→  Sert zemin
                                    │
Otopark Alanları  ───────→  6. ParkingGenerator  ─→  Otopark yerleri ve giriş çizgisi
Yol Katmanı (Opsiyonel) ───────↗
                                    │
                           7. LandscapeGenerator  ─→  Ağaçlar
                                    │
                           8. SettlementFinalizer  ─→  Rapor
```

## Gerekli Girdiler
- **Ada katmanı**: Polygon (imar adaları)
- **Yol katmanı**: Line (yol ağı - hem cephe kontrolünde hem de Adım 6 Parametrik Otopark hizalamasında kullanılır)
- **Otopark alanları**: Polygon (kullanıcı çizer)
- **Kentsel Donatı Katmanı**: Özel algoritmayla otomatik oluşturulabilir (Kataloga entegre `urban_furniture_creator.py` aracıyla svg logoları tanımlanmış nokta katmanı yaratılır)

## Öne Çıkan Süreç Detayları

1. **ParcelFlux Asimetrisi**: Her bir ada "balıksırtı (fishbone)" organik kaymalarının yanı sıra "Sıra Genişlik Asimetrisi"ne sahiptir. Yani adanın bir cephesindeki parsel sıralarının cephe genişlikleri 22 m iken tam arkasındaki sıra 18 m ayarlanabilir. Algoritma çizgileri bu oranda bağımsız üretir.
2. **Prosedürel Dinamik Kütleler (3C)**: Dış şablona (.gpkg) ihtiyaç duymaksızın oluşturulan parsel içi Maxium Bbox alanını baz alarak mimari kısıtlara uygun (En az 7m kanat genişliği) farklı mimari tipolojiler üretir. Minimum parsel boyutuna göre karmaşık şekiller atanır.
3. **Akıllı Otopark**: Verilen yol katmanı üzerinden "en yakın nokta (nearestpoint)" hesaplanarak otopark manevra güzergahları yol iziyle tutarlı doğrultuya döndürülür (Oriented Minimum Bounding Box açısı + Road Connection).

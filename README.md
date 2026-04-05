# planX — Yerleşim Planı Araç Seti

**Geliştirici:** Araş. Gör. Yusuf Eminoğlu (Dokuz Eylül Üniversitesi, Şehir ve Bölge Planlama Bölümü)  
**Versiyon:** 0.3.0  
**QGIS:** ≥ 3.28 (Önerilen: 3.40 LTR veya 3.44 LTR)

## Vizyon

planX ekosisteminin **Yerleşim Planı** üretimine özel tasarlanmış alt bileşeni. UIP çizimleri tamamlandıktan sonra **9 aşamalı sıralı iş akışı** ile parametrik ve gerçekçi bir yerleşim planı üretir.

## 9 Aşamalı İş Akışı

| # | Adım | Açıklama |
|---|---|---|
| 1 | **ParcelFlux** | Ada → Parsel bölme (Genişlik varyasyonu ve Sıra Genişlik Asimetrisi) |
| 2 | **FacadeDetector** | Cephe tespiti ve sınıflandırması (ön/yan/arka bahçe) |
| 3 | **CoverageFootprint** | Kenar bazlı setback + TAKS parametreleri ile maksimum inşaat alanı |
| 3C | **Dynamic Macroform** | Prosedürel 12 farklı gerçekçi mimari form türetimi |
| 4 | **BuildingOptimizer** | Bina-parsel uyum kontrolü |
| 5 | **Hard Surface** | Sert zemin / yürüme alanı hesaplaması |
| 6 | **ParkingGenerator** | Yol ağı bağlantılı, parametrik otopark (90°/60°/45°) motoru |
| 7 | **LandscapeGenerator** | Araziye uygun bitkilendirme ve ağaç yerleşimi |
| 8 | **SettlementFinalizer** | Nüfus projeksiyonu ve genel istatistik/raporlama aracı |

## Kurulum

1. Bu klasörü (veya ZIP dosyasını) QGIS eklentiler dizinine kopyalayın:
   ```
   C:\Users\<KULLANICI>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\
   ```
2. QGIS'i yeniden başlatın
3. **Eklentiler → Eklentileri Yönet** menüsünden aktifleştirin
4. **İşlem Kutusu** (Processing Toolbox) içinde **planX — Yerleşim Planı Araç Seti** görünecektir

## Yenilikler (v0.3.0)

### ParcelFlux İle Gerçek Zamanlı Asimetri
Adanın karşılıklı sıralarındaki parselleri istenilen asimetri katsayısına göre (Örn: Kuzey %10 daha geniş) o bölgeye tamamen rastgele ve organik bir doku vererek böler. 

### Dinamik Prosedürel Formlar
Temel kütleler (I, L, U, T, vb. toplam 12 tip) minimum 7 metrelik doğal mekan kanat derinlikleriyle, parsel yapısına uygun rastgele mimari tipolojiler üretir.

### Yol Kılavuzlu Parametrik Otopark
Verilen yol ağını analiz eden yeni otopark motoru, otoparkı optimize edip "bağlantı ve giriş çizgisi"ni en yakın yol güzergahına bağlar. 

### QGIS 3.40+ Tam Uyum 
API revizyonlarından dolayı oluşan geometri uyumsuzlukları, motor çekirdeği optimizasyonu ile aşılmıştır. 

## Lisans

GPL-3.0

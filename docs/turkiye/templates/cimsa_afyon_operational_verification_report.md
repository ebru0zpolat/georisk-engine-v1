# Bağımsız Operasyonel Doğrulama Raporu

## A. Denetim parametreleri

- **Tesis:** Çimsa Afyon Çimento Fabrikası
- **AOI (İnceleme Alanı):** 38.745°N, 30.485°E (500 m buffer)
- **Koleksiyon:** `LANDSAT/LC08/C02/T1_L2`
- **Tarih aralığı:** 2026-01-01 — 2026-05-01

## B. Analiz çıktıları

- **Maske politikası (termal):** QA_PIXEL tabanlı bulut ve gölge maskeleme (Landsat C2 L2 üretim hattında uygulanır).
- **NO₂ politikası:** Sentinel-5P **OFFL L3** troposferik sütun (`tropospheric_NO2_column_number_density`, mol/m²) — **L2 `qa_value` ile birebir aynı değildir**; birleşik metodoloji notuna bakınız.
- **Gözlemlenen maksimum ısı:** {{celsius}} °C
- **Ortalama NO₂ yoğunluğu (AOI ortalaması):** {{no2_mean_mol_m2}} mol/m²
- **Uydu görüntü ID (termal bileşik / özet):** {{img_id}}

## C. Feragat ve sınırlamalar (Disclaimer)

- **Metodolojik sınır:** Bu rapor, uydudan türetilen **yüzey sıcaklığı** ve **troposferik NO₂ sütunu** proxy özetlerine dayanır; tesis içi sensör veya düzenleyici ölçümlerle %100 örtüşme garantisi yoktur.
- **Atmosferik etki:** Ölçümler, gözlem anındaki atmosferik nem ve rüzgâr koşullarından etkilenebilir.
- **Kullanım:** Bu rapor yalnızca operasyonel şeffaflık amacıyla hazırlanmış olup yatırım tavsiyesi içermez.

## D. CCO mührü ve metodolojik bağ (üçlü doğrulama)

Bu bölüm, raporun **operasyonel mühür** çerçevesini özetler; hukuki taahhüt veya resmi denetim yerine geçmez.

1. **Fiziksel kanıt (Landsat ST_B10):** Yukarıdaki sıcaklık özeti, fırın / yüksek sıcaklık bölgesi ile ilişkilendirilebilecek **yüzey ısısı proxy’si** ile operasyonel aktiflik **olasılığını** destekler; tek başına “fırın çalışıyor” iddiası değildir.
2. **Çevresel kanıt (Sentinel-5P NO₂):** Troposferik NO₂ sütunu ortalaması, tesis izdüşümündeki **emisyon şeffaflığı** için **uydu proxy** özetidir; kaynak ayrıştırması (tesis / taşıma / bölgesel arka plan) ayrı analiz gerektirir.
3. **Metodolojik link ve yasal sınır:** Termal + emisyon birleşik metodoloji, maske politikaları ve sorumluluk reddi için tek kaynak: **`docs/turkiye/cco-audit-methodology.md`** (repo köküne göreli yol; dağıtımda URL ile değiştirilebilir).

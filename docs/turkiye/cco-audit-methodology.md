# Birleşik uydu denetim metodolojisi (Termal + Emisyon)

**Sürüm (iletişim / FM envanteri):** 1.0

Bu not, operasyonel doğrulama ve butik denetim akışlarında **ısı** ile **troposferik NO₂** sinyallerinin birlikte kullanımına ilişkin ortak metodolojik çerçeveyi özetler. Uygulama kodunda koleksiyon sürümleri ve maske politikası sürümlenmeli; aşağıdaki ifadeler tipik üretim tasarımını tanımlar.

## Veri kaynakları

| Kanal | Tipik ürün | Denetim rolü |
|--------|------------|----------------|
| **Termal** | Landsat 8/9 Collection 2 Tier 1 Level-2 (`LANDSAT/LC08/C02/T1_L2`, `LC09` ile birleştirilebilir), band **`ST_B10`** | Yüzey sıcaklığı proxy’si; tesis çekirdeği–çevre karşılaştırması ve zaman içi tutarlılık |
| **Emisyon** | Copernicus Sentinel-5P NO₂ (ör. EE’de `COPERNICUS/S5P/OFFL/L3_NO2`), **`tropospheric_NO2_column_number_density`** | Troposferik NO₂ sütunu; yanma / yüksek sıcaklık prosesleri ile ilişkili “duman” yoğunluğu proxy’si |

## Teknik maskeleme ve kalite

- **Landsat:** **`QA_PIXEL`** bitleri kullanılarak bulut, bulut gölgesi ve genişletilmiş bulut gibi sınıflar maskelenir; üretim hattında kullanılan tam bit maskesi kod ile sabitlenmeli ve sürüm notuna yazılmalıdır.
- **Sentinel-5P NO₂:** Ürün seviyesine göre kalite filtresi **aynı değildir**. **`qa_value > 0.5`** ifadesi yaygın olarak **L2** iş akışları için anılır; **L3 birleşik** ürünlerde ilgili QA bandı / bulut kesri politikası farklı olabilir. GeoRisk üretiminde S5P tarafında **bulut kesri eşiği** veya EE dokümantasyonuna uygun maske kullanımı tercih edilmeli; raporda “L3 için uygulanan kesin filtre” üretim koduyla tek kaynak olmalıdır.

Çapraz tahkimat: termal ve NO₂ **aynı takvim penceresi ve uyumlu AOI** üzerinde yorumlanmalı; revisit ve bulutluluk farkları feragatta açıklanır.

## Birleşik yorumlama (özet)

- Yüksek termal sinyal + **beklenen** NO₂ bileşeni → yoğun üretim / yanma rejimi ile uyumlu **olası** senaryo (nedensellik iddiası değil).
- Yüksek termal + düşük NO₂ → scrubbing / düşük-NOx yakma / ölçüm geometrisi dışı taşınım veya soğutma gibi **alternatif açıklamalar** literatür ve saha bağlamı ile tartışılır.
- Düşük termal + yüksek NO₂ → plüm geometrisi, çevresel NO₂, taşımacılık veya komşu kaynaklar gibi **karıştırıcılar** değerlendirilir.

## Sorumluluk reddi (Disclaimer)

Bu rapor ve türev çıktılar, **uydu gözlemlerine dayalı operasyonel tahmin ve proxy analizdir**; saha sensörleri, sürekli emisyon ölçüm sistemleri veya düzenleyici raporlama ile **%100 örtüşme garantisi vermez**. Yatırım tavsiyesi, resmi uygunluk beyanı veya tek başına hukuki delil niteliği taşımaz.

İlgili tesise özel şablon ve parametreler için: `docs/turkiye/cimsa-afyon-operational-verification-methodology.md`. Üretim betikleri: `scripts/run_integrated_audit.py` (önerilen CCO girişi), `scripts/run_audit.py`, `scripts/landsat_thermal_audit.py`, `scripts/s5p_no2_audit.py`, `scripts/report_engine.py`.

Üretilen Markdown çıktılarının sonuna (varsayılan) eklenen feragat metni tek kaynak: ``docs/turkiye/snippets/report_automatic_footer_disclaimer_tr.md``.

Abonelik ürünü için veri standardı, analitik çerçeve ve katmanlı paket tanımı (Altın standard / roadmap): **[golden-standard-subscription-and-analytics.md](./golden-standard-subscription-and-analytics.md)**.

Örnek kurumsal teklif metni (Market Alpha / Pro): **[proposals/teklif-market-alpha-sektorel-hareketlilik-kapasite-2026-05.md](./proposals/teklif-market-alpha-sektorel-hareketlilik-kapasite-2026-05.md)**.

Kamuya açık bilimsel özet (dashboard’da da gösterilir): **[whitepaper-operational-verification-public.md](./whitepaper-operational-verification-public.md)**.

# Bağımsız Operasyonel Doğrulama Raporu

## A. Denetim parametreleri

- **Tesis:** Çimsa Afyon Çimento Fabrikası
- **AOI (İnceleme Alanı):** 38.745°N, 30.485°E (500 m buffer)
- **Koleksiyon:** `LANDSAT/LC08/C02/T1_L2`
- **Tarih aralığı:** 2026-01-01 — 2026-05-01

## B. Analiz çıktıları

- **Maske politikası (termal):** QA_PIXEL tabanlı bulut ve gölge maskeleme (Landsat C2 L2 üretim hattında uygulanır).
- **NO₂ politikası:** Sentinel-5P **OFFL L3** troposferik sütun (`tropospheric_NO2_column_number_density`, mol/m²) — **L2 `qa_value` ile birebir aynı değildir**; birleşik metodoloji notuna bakınız.
- **Gözlemlenen maksimum ısı:** 35.20 °C
- **Ortalama NO₂ yoğunluğu (AOI ortalaması):** 0.000140 mol/m²
- **Uydu görüntü ID (termal bileşik / özet):** LC08_L2SP_MOCK_EXAMPLE

## C. Feragat ve sınırlamalar (Disclaimer)

- **Metodolojik sınır:** Bu rapor, uydudan türetilen **yüzey sıcaklığı** ve **troposferik NO₂ sütunu** proxy özetlerine dayanır; tesis içi sensör veya düzenleyici ölçümlerle %100 örtüşme garantisi yoktur.
- **Atmosferik etki:** Ölçümler, gözlem anındaki atmosferik nem ve rüzgâr koşullarından etkilenebilir.
- **Kullanım:** Bu rapor yalnızca operasyonel şeffaflık amacıyla hazırlanmış olup yatırım tavsiyesi içermez.

## D. CCO mührü ve metodolojik bağ (üçlü doğrulama)

Bu bölüm, raporun **operasyonel mühür** çerçevesini özetler; hukuki taahhüt veya resmi denetim yerine geçmez.

1. **Fiziksel kanıt (Landsat ST_B10):** Yukarıdaki sıcaklık özeti, fırın / yüksek sıcaklık bölgesi ile ilişkilendirilebilecek **yüzey ısısı proxy’si** ile operasyonel aktiflik **olasılığını** destekler; tek başına “fırın çalışıyor” iddiası değildir.
2. **Çevresel kanıt (Sentinel-5P NO₂):** Troposferik NO₂ sütunu ortalaması, tesis izdüşümündeki **emisyon şeffaflığı** için **uydu proxy** özetidir; kaynak ayrıştırması (tesis / taşıma / bölgesel arka plan) ayrı analiz gerektirir.
3. **Metodolojik link ve yasal sınır:** Termal + emisyon birleşik metodoloji, maske politikaları ve sorumluluk reddi için tek kaynak: **`docs/turkiye/cco-audit-methodology.md`** (repo köküne göreli yol; dağıtımda URL ile değiştirilebilir).

---

<!-- Bu blok ``docs/turkiye/cco-audit-methodology.md`` ve tesise özel metodoloji notları ile uyumludur; hukuki/metodolojik metin değişiklikleri önce o dokümanlarda yapılmalı, burası senkron güncellenmelidir. -->

## Otomatik eklenen feragat ve metodoloji referansı (CCO uyumu)

Bu bölüm, `reports/output/` altına yazılan teknik çıktıya **metodoloji belgelerindeki sorumluluk reddi** ile tutarlı bir son ek taşır; **resmi denetim, düzenleyici uygunluk veya yasal taahhüt yerine geçmez**.

- **Doğa çıktısı:** Üretilen sayılar ve grafikler, Earth Engine üzerinden türetilen **uydu proxy** özetleridir; saha sensörleri veya izleme sistemleri ile **tam örtüşme garantisi yoktur**.
- **Yatırım / hukuki kullanım:** Bu içerik **yatırım tavsiyesi**, **mahkemede tek başına delil** veya **kanuni uygunluk beyanı** değildir.
- **Yetki sınırı:** Teknik üretim ile birlikte sunulan metinler, **operasyonel şeffaflık ve iç kontrol** amaçlıdır; kuruluş içi “uyumluluk veya risk yetkilisi (CCO)” rol tanımı şirket politikasına tabidir — yazılım tek başına yetki atamaz.
- **Tam metodoloji:** Birleşik termal + NO₂ çerçevesi, maske politikaları ve birleşik yorumlama için bkz. **`docs/turkiye/cco-audit-methodology.md`**. Tesise özel parametre ve şablon için bkz. **`docs/turkiye/cimsa-afyon-operational-verification-methodology.md`** (veya ilgili tesiste özelleştirilmiş not).

---

## E. GeoRisk API — industrial verification (aynı ``audit_id``)

Bu bölüm, üstteki **operasyonel termal + NO₂ doğrulama raporu** (A–D) ile aynı AOI koordinatlarında üretilebilecek **climate-risk** yanıtındaki ``industrial_verification`` özetidir. ``linked_audit_id``, o isteğin ``audit_id`` alanı ile aynıdır; böylece operasyonel mühür / Primary Audit hatları ile çapraz referans tek kayıt altında toplanır.

**Uçlar:** ``POST /v1/reports/risk`` (rapor uçlarında bu blok varsayılan olarak açıktır) veya ``POST /v1/risk/score`` + ``include_industrial_verification_ref: true``.

*Not:* Aşağıdaki ``linked_audit_id`` değeri bu örnek dosyada **dokümantasyon tutarlılığı** için sabitlenmiştir; canlı çağrıda her seferinde yeni bir UUID üretilir.

## Industrial verification (bundled on same audit id)
- **Linked audit ID:** `aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee` (aynı istekteki climate-risk yanıtının ``audit_id`` alanı ile aynıdır; bu örnek dosyada değer dokümantasyon için sabitlenmiştir.)
- **Risk model version:** risk-score-v0.1
- Nearest Primary Audit AOI: *no facility within configured match radius*

### Operational pipelines (reference)
  - `cement_operational_audit` — Çimento — termal + NO₂ mühürlü operasyonel doğrulama (`docs/turkiye/cco-audit-methodology.md` → `scripts/run_integrated_audit.py`)
  - `transformer_primary_audit` — Trafo — emisyon + VIIRS Primary Audit (ESG Watch) (`docs/turkiye/transformers/transformer-audit-methodology.md` → `scripts/transformer_audit.py`)

*Disclaimer (TR):* Uydu proxy özetidir; düzenleyici uygunluk veya resmi beyan yerine geçmez. Mühürlü rapor üretimi ayrı betiklerle yapılır; bu nesne ürün entegrasyonu için referans taşır.

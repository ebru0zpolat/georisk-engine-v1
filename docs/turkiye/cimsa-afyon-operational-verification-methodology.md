# Bağımsız operasyonel doğrulama raporu — metodoloji (Çimsa Afyon örneği)

Bu not, çimento tesisi için **Landsat 8/9 Collection 2 Level-2** yüzey sıcaklığı (`ST_B10`) tabanlı **operasyonel doğrulama raporu** şablonunun parametrelerini ve feragatını sabitler. Termal + NO₂ birleşik çerçeve için bkz. **[cco-audit-methodology.md](./cco-audit-methodology.md)**. Üretim kodunda Earth Engine kimliği yalnızca `**GEE_PROJECT`** (veya tek tip ortam değişkeni politikası) ile okunmalıdır; proje kimliği repoya yazılmaz.

## A. Denetim parametreleri


| Alan              | Değer                                                                                               |
| ----------------- | --------------------------------------------------------------------------------------------------- |
| **Tesis**         | Çimsa Afyon Çimento Fabrikası                                                                       |
| **AOI**           | 38.745°N, 30.485°E — **500 m buffer** (yarıçap politikası üretim komut dosyasında dokümante edilir) |
| **Koleksiyon**    | `LANDSAT/LC08/C02/T1_L2` (gerekirse `LC09` ile birleştirilmiş composite ayrı notta)                 |
| **Tarih aralığı** | 2026-01-01 — 2026-05-01 (UTC takvimi; EE `filterDate` bitiş politikası ile uyumlu)                  |


## B. Analiz çıktıları (şablonda doldurulan alanlar)

- **Maske politikası:** QA_PIXEL tabanlı bulut/gölge maskeleme — iddia, gerçekten EE görüntü işleme hattında uygulanıyorsa geçerlidir; aksi halde “taslak / planlanan politika” olarak işaretlenmelidir.
- **Gözlemlenen maksimum ısı:** `{{celsius}}` °C (maskeli `ST_B10` → Kelvin ölçeklemesi → Celsius).
- **Uydu görüntü ID:** `{{img_id}}`

Şablon gövdesi: `docs/turkiye/templates/cimsa_afyon_operational_verification_report.md`

**Paylaşım örneği (operasyonel + GeoRisk industrial bundle):** `docs/turkiye/examples/cimsa_afyon_20260501_operational_plus_risk_bundle.md` — yeniden üretim: `scripts/generate_docs_operational_risk_bundle_example.py` (`docs/turkiye/examples/README.md`).

## C. Feragat ve sınırlamalar

1. **Metodolojik sınır:** Rapor, uydudan türetilen **yüzey sıcaklığı** proxy’sine dayanır; tesis içi sensör veya stack ölçümleri ile birebir örtüşmeyebilir.
2. **Atmosferik etki:** Nem, bulut kalıntısı, rüzgâr ve topoğrafya tek pikselli “maksimum” istatistikleri etkileyebilir.
3. **Kullanım:** Operasyonel şeffaflık ve izlenebilirlik amaçlıdır; yatırım tavsiyesi, resmi emisyon beyanı veya düzenleyici uygunluk belgesi değildir.
4. **Fırın aktivitesi:** Yüksek yüzey sıcaklığı tek başına **klinker fırını çalışıyor** sonucunu doğrudan ispat etmez; ΔT (çekirdek vs çevre), çoklu tarih ve mümkünse NO₂ vb. çapraz kanıt ile birlikte yorumlanmalıdır.

## Uygulama

- **Risk API sektör kaydı (genişletme):** Yeni first-class sektör id’leri için bkz. `docs/turkiye/sector-extensions.md` ve `app/core/sector_registry.py`.
- **Önerilen giriş noktası (CCO):** `python scripts/run_integrated_audit.py` — önce `.env` içinde `GEE_PROJECT` / `GEE_PROJECT_ID` kontrolü (mock hariç).  
- Uçtan uca (termal + S5P L3 NO₂ + rapor): `python scripts/run_audit.py --lat … --lon … --company …`  
  Çıktı dosyası: `reports/output/{slug}_{YYYYMMDD}.md`. Geliştirme/mock: `AUDIT_USE_MOCK=true` (Earth Engine çağrısı yapmaz).
- Yalnızca şablon doldurma: `python scripts/report_engine.py` (`--celsius`, `--img-id`) veya `scripts/report_engine.render_cimsa_afyon_report(...)`.
- **Feragat eki:** `reports/output/` altına yazılan her tam raporda (varsayılan), ``docs/turkiye/snippets/report_automatic_footer_disclaimer_tr.md`` içeriği rapor sonuna otomatik eklenir; ``--no-methodology-footer`` ile kapatılabilir (CLI).
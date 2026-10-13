# Mühürlü Trafo Primary Audit — {{facility_name_tr}}

**Denetim seviyesi:** {{audit_tier}} · **Tesis kimliği:** `{{facility_id}}`  
**Gözlem penceresi:** {{start_date}} — {{end_date}} (EE `filterDate` üst sınırı hariç)  
**Mühür (repo HEAD):** `{{seal_git_commit}}` · **Üretim zamanı (UTC):** {{generated_utc}}

> **Not:** Git commit özeti **iç süreç mührüdür**; hukuki veya düzenleyici “değiştirilemez” delil anlamına gelmez. Feragat: [transformer-audit-methodology.md](../transformer-audit-methodology.md).

## Altın Protokol Mührü — GeoRisk mühürlü operasyonel endeks (teknik referans ifadesi)

**Bu veri özeti, Landsat Collection 2 Level-2 (QA_PIXEL maskeli termal üretim hattı) ve Sentinel-5P OFFL L3 ürün çizgisi protokolleriyle üretim hattında mühürlenmiştir.** Gece ışığı için VIIRS DNB aylık bileşik (`avg_rad`) ve ürün dokümantasyonuna uygun **`cf_cvg` gözlem yoğunluğu özeti** raporda ayrıca sunulmuştur. Bu ibare **düzenleyici sertifika veya resmi uygunluk onayı** değildir; tam çerçeve: [georisk-sealed-index-closed-loop-publishing.md](../../georisk-sealed-index-closed-loop-publishing.md).

## A. AOI ve arka plan filtresi

- **Tesis notu (GeoJSON):** {{facility_notes_tr}}
- **Halka tamponu:** `ring = site.buffer({{ring_buffer_m}} m).difference(site)` — OSB içi komşu tesis **gürültü** emisyonuna karşı **basit normalizasyon** (kaynak ayırımı değildir).

## B. ESG Watch — üçlü veri özeti

| Veri kaynağı | KAFİ metriği | Denetim hedefi (proxy) |
| --- | --- | --- |
| Sentinel-5P NO₂ (L3) | Scope 2 (dolaylı enerji) | Enerji kullanım yoğunluğu ile beyanların **uydu ile çapraz** tutarlılığı |
| Sentinel-5P CO (L3) | Scope 1 (doğrudan) | Yanma / ısıl işlem çıktıları için **bağımsız bağlam sinyali** |
| VIIRS DNB (aylık `avg_rad`) | Operasyonel canlılık | Gece vardiyaları / aydınlatma ile **kapasite proxy** bağlamı |

### B.1 Sayısal özet

| Alan | NO₂ (mol/m²) | CO (mol/m²) | VIIRS `avg_rad` | Termal max (°C) |
| --- | --- | --- | --- | --- |
| **AOI (tesis)** | {{no2_aoi_mol_m2}} | {{co_aoi_mol_m2}} | {{ntl_aoi_avg_rad}} | {{thermal_celsius}} |
| **Halka (arka plan)** | {{no2_ring_mol_m2}} | {{co_ring_mol_m2}} | {{ntl_ring_avg_rad}} | — |
| **Residual (AOI − ring)** | {{no2_residual_mol_m2}} | {{co_residual_mol_m2}} | {{ntl_residual_avg_rad}} | — |

**Durum:** `{{bundle_status}}` — `{{bundle_detail}}`

**Termal kimlik:** `{{thermal_img_id}}`

### B.2 VIIRS kalite bağlamı — `cf_cvg` (bulut-özgür gözlem sayısı özeti)

| Alan | `cf_cvg` ortalaması (birim: ürün tanımı) |
| --- | --- |
| **AOI (tesis)** | {{ntl_cf_cvg_aoi_mean}} |
| **Halka (arka plan)** | {{ntl_cf_cvg_ring_mean}} |

Düşük `cf_cvg`, `avg_rad` üzerindeki yorum güvenini **düşürebilir**; bu alan **şeffaf hata payı** olarak rapora eklenmiştir (maskeleme ürün yol haritasında).

## C. CCO görüşme çerçevesi (ölçülü iletişim)

Sürdürülebilirlik raporlarındaki karbon beyanları; sahada tam sensör ağı olmadan tek başına denetlenmekte zorlanabilir. Bu üretim hattı, **uydu türevli NO₂ ve CO** (ve bu raporda VIIRS / termal) özetlerini **operasyonel olarak kısa gecikmeyle** yan yana getirerek finans ve sürdürülebilirlik ekiplerine **bağımsız bir “üçüncü taraf perspektifi”** (çapraz soru) sunar. Bu süreç **resmi uygunluk onayı veya kesin doğrulama** değildir; **Yeşil Mutabakat** uyumu için **şeffaflık hazırlığı** aracı olarak konumlanır. Tam feragat: [whitepaper-operational-verification-public.md](../whitepaper-operational-verification-public.md) **Bölüm 4**.

## D. Proprietary sınır

Sevkiyat yoğunluğundan kapasiteye giden **katsayılar** ve kurumsal kalibrasyon: [proprietary-transformer-logistics-capacity-proxy.md](../proprietary-transformer-logistics-capacity-proxy.md).

## E. Kapalı devre dağıtım — filigran / alıcı etiketi

**Filigran (metinsel):** {{watermark_label}}

Bu alan, **Market Alpha** ve üzeri kapalı devre paketlerde indiren kurumu ve sözleşme bağlamını sabitler. Üretimde `GEORISK_REPORT_WATERMARK` ortam değişkeni ile doldurulur; hukuki metin için bkz. [georisk-sealed-index-closed-loop-publishing.md](../../georisk-sealed-index-closed-loop-publishing.md) (filigranlı raporlar).

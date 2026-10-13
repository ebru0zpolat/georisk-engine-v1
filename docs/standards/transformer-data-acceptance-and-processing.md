# Trafo (Primary Audit) — veri kabul ve işleme standardı

**Sürüm notu:** Repo içi standart; düzenleyici “resmi kanıt” iddiası taşımaz.

## 1. Kabul edilen uydu ürünleri

| Katman | Ürün | Zorunlu alan | Not |
| --- | --- | --- | --- |
| Emisyon | Sentinel-5P **OFFL L3** NO₂ | `tropospheric_NO2_column_number_density` | L3 kalite politikası L2’den farklıdır |
| Emisyon | Sentinel-5P **OFFL L3** CO | `CO_column_number_density` | EE sürümüne göre bant doğrulaması |
| Aktivite | VIIRS DNB aylık **VCMSLCFG** | `avg_rad` + raporda **`cf_cvg` ortalaması** | Düşük `cf_cvg` → yorum güveni düşer |
| Termal (bağlam) | Landsat C2 L2 (QA_PIXEL) | `ST_B10` → °C; centroid + tanımlı tampon | Trafo hattında ikincil kanıt |

## 2. AOI disiplini

- Tesis poligonu: `docs/turkiye/transformers/primary_audit_facilities.geojson` (sahada doğrulanmış geometri ile güncellenir).  
- OSB gürültüsü için **halka**: `site.buffer(R).difference(site)` — `R` raporda ve manifestte yazılır.

## 3. Çıktı mührü

- Mühürlü Markdown: `docs/turkiye/transformers/sealed_reports/`  
- YAML front matter + `git rev-parse HEAD` özeti.  
- Filigran: `GEORISK_REPORT_WATERMARK` (kapalı devre).  
- Mühürlü operasyonel endeks / QOR çerçevesi: **[docs/turkiye/georisk-sealed-index-closed-loop-publishing.md](../turkiye/georisk-sealed-index-closed-loop-publishing.md)**.  
- Birincil sektör öncelikleri (SKDM): **[docs/turkiye/sectors-skdm-primary-priorities.md](../turkiye/sectors-skdm-primary-priorities.md)**.

## 4. Feragat

Trafo metodolojisi: **[docs/turkiye/transformers/transformer-audit-methodology.md](../turkiye/transformers/transformer-audit-methodology.md)**.  
Proprietary kapasite katsayıları: **[docs/turkiye/proprietary-transformer-logistics-capacity-proxy.md](../turkiye/proprietary-transformer-logistics-capacity-proxy.md)**.

## 5. Arşivleme (QOR)

Çeyrek manifestine `standards_refs` ve `product_hubs.transformer_primary_audit` eklenir: **`data/archive/YYYY-Qn/MANIFEST.yml`**.

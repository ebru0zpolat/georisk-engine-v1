# Trafo Primary Audit — metodoloji özeti (repo içi)

**Sürüm (iletişim / FM envanteri):** 1.2

Bu dosya, `scripts/transformer_audit.py` ve `docs/turkiye/transformers/sealed_reports/` çıktıları için **teknik çerçeveyi** özetler. Kamuya açık üst seviye anlatım: [whitepaper-operational-verification-public.md](../whitepaper-operational-verification-public.md) **Bölüm 3**.

## 1. Primary Audit tesileri

AOI poligonları: `primary_audit_facilities.geojson`. Koordinatlar **örnek / sahada doğrulanacak** OSB düzenindedir.

## 2. Veri hatları

| Kaynak | Ürün çizgisi | Not |
| --- | --- | --- |
| NO₂ | `COPERNICUS/S5P/OFFL/L3_NO2` — `tropospheric_NO2_column_number_density` | L3; L2 `qa_value` ile aynı değildir |
| CO | `COPERNICUS/S5P/OFFL/L3_CO` — `CO_column_number_density` | Bant adı EE sürümüne göre doğrulanmalıdır |
| Gece ışığı | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` — `avg_rad` + `cf_cvg` | Aylık bileşik; raporda **AOI ve halka ortalaması `cf_cvg`** şeffaf kalite bağlamı olarak yazılır (düşük değer: yorum güveni düşer) |
| Termal (çatı / geniş AOI) | Landsat C2 L2 QA_PIXEL maskeli median bileşik | Tesis merkezine yakın tampon; trafo hattında **ikincil** kanıt |

## 3. Arka plan (halka) filtresi

`ring = site.buffer(R).difference(site)` üzerinde aynı ürünlerin ortalaması alınır; **AOI − ring** farkı “komşu sanayi gürültüsüne” karşı **kaba normalizasyon** içindir — **kaynak ayırımı veya regülasyon uygunluğu** iddiası taşımaz.

## 4. Mühürleme

Rapor gövdesine `git rev-parse HEAD` ile **repo HEAD özeti** yazılır. Bu, iç kontrol ve rapor sürümünü eşlemek içindir; **kriptografik mühür veya zincir üstü ispat** değildir.

## 5. ESG matrisi

Tam tablo: [esg-emisyon-matrisi.md](./esg-emisyon-matrisi.md).

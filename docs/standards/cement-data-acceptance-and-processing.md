# Çimento — veri kabul ve işleme standardı

**Sürüm notu:** Bu metin repo içi standarttır; düzenleyici uygunluk veya resmi “sertifika” beyanı değildir.

## 1. Kabul edilen uydu ürünleri

| Katman | Ürün | Zorunlu band / işlem | Red / İstisna |
| --- | --- | --- | --- |
| Termal | Landsat 8/9 **Collection 2 Tier 1 Level-2** | `ST_B10` → °C; **QA_PIXEL** maskeli median bileşik | QA dışı ham L1 kullanılmaz |
| Emisyon | Sentinel-5P **OFFL L3** troposferik NO₂ | `tropospheric_NO2_column_number_density` (mol/m²) | L2 `qa_value` akışı L3 ile karıştırılmaz |

## 2. AOI ve tampon disiplini

- Termal: varsayılan **500 m** tampon (kurumsal olarak sabitlenmiş AOI ile değiştirilirse sürüm notu zorunlu).  
- NO₂: varsayılan **2000 m** tampon (plüm ölçeği); raporda yazılır.

## 3. Birimler ve raporlama

- Sıcaklık: **°C** (görüntüleme çözünürlüğü raporda tanımlı).  
- NO₂: **mol/m²**.  
- Kapasite proxy: `app/scoring/capacity_proxy.py` — **proprietary kalibrasyon** ayrı dokümanda.

## 4. Feragat ve tek kaynak

Maske politikası ve hukuki sınır: **[docs/turkiye/cco-audit-methodology.md](../turkiye/cco-audit-methodology.md)**.

## 5. Arşivleme (QOR)

Çeyrek kapanışında bu standardın referanslandığı commit, **`data/archive/YYYY-Qn/MANIFEST.yml`** içine yazılır. Operasyon: [github-archive-and-immutability.md](./github-archive-and-immutability.md).

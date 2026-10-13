# Veri kabul ve işleme standartları

Bu dizin, **sektöre göre** GeoRisk üretim hattına giren verilerin **hangi ürün çizgilerini**, **hangi birimleri** ve **hangi QA / feragat** çerçevesinde kabul ettiğimizi sabitler. Kamuya açık whitepaper ve NDA paketleri bu standartlara **referans verir**; teknik detay değişiklikleri burada veya `docs/turkiye/cco-audit-methodology.md` içinde sürümlenir.

| Belge | Kapsam |
| --- | --- |
| [cement-data-acceptance-and-processing.md](./cement-data-acceptance-and-processing.md) | Çimento / yüksek termal imza operasyonel denetim hattı |
| [transformer-data-acceptance-and-processing.md](./transformer-data-acceptance-and-processing.md) | Trafo / düşük termal imza — emisyon + gece ışığı Primary Audit |
| [github-archive-and-immutability.md](./github-archive-and-immutability.md) | `data/archive/YYYY-Qn/` Git operasyonu, tag, değişmezlik disiplini |
| [../georisk_data_source_validation_summary.md](../georisk_data_source_validation_summary.md) | Veri kaynağı kabul ve runtime doğrulama paketi (Validation Package) |
| [../georisk_data_source_loi_summary.md](../georisk_data_source_loi_summary.md) | Veri kaynağı LOI / ortaklık paketi |

Stratejik sektör önceliği (Türkiye / ihracat bağlamı): [../turkiye/sectors-skdm-primary-priorities.md](../turkiye/sectors-skdm-primary-priorities.md).

Patent vekili öncesi iç taslak (buluş bildirimi / kademeli savunma): [../turkiye/ip-bulus-bildirimi-ve-fikri-mulkiyet-stratejisi-tr.md](../turkiye/ip-bulus-bildirimi-ve-fikri-mulkiyet-stratejisi-tr.md).

Çeyrek arşiv kökü: [`data/archive/`](../../data/archive/README.md).

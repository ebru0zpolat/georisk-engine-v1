# Örnek raporlar (paylaşım / dokümantasyon)

Bu klasördeki Markdown dosyaları **repoya sabitlenmiş** örneklerdir (`reports/output/` gibi `.gitignore` altında değil). Müşteri veya iç ekip ile paylaşımda “tam çıktı nasıl görünür?” sorusuna tek kaynak olarak kullanılabilir.

| Dosya | Açıklama |
|--------|----------|
| [`cimsa_afyon_20260501_operational_plus_risk_bundle.md`](./cimsa_afyon_20260501_operational_plus_risk_bundle.md) | Çimsa Afyon AOI şablonu (A–D + otomatik feragat eki) + **Bölüm E:** GeoRisk `industrial_verification` (aynı `audit_id` çerçevesi). |

## Yeniden üretim

Operasyonel gövde, `AUDIT_USE_MOCK=true` ile `run_audit.py` çıktısıyla aynı sayısal placeholder’ları kullanır (EE gerekmez). Bölüm E’deki `linked_audit_id` dokümantasyon için **sabit UUID**’dir; canlı API’de her istekte yeni üretilir.

```bash
PYTHONPATH=. python scripts/generate_docs_operational_risk_bundle_example.py
```

Sadece stdout’ta görmek için: `python scripts/generate_docs_operational_risk_bundle_example.py --stdout`

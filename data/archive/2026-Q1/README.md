# Arşiv: 2026-Q1 (frozen reference bundle)

**Arşiv kimliği:** `2026-Q1`  
**Amaç:** Bu çeyrekte “standart GeoRisk üretim hattı” ile uyumlu **metin ve politika** anlık görüntüsü; mühürlü operasyonel çıktıların repo içi veya Release üzerinden **doğrulanabilir bağlantısı**.

## Bu çeyrekte dondurulan referanslar

Ayrıntılı makine okunur liste: [`MANIFEST.yml`](./MANIFEST.yml).

Özet:

- Birleşik denetim metodolojisi: `docs/turkiye/cco-audit-methodology.md` (tag anındaki commit ile).  
- Kapalı devre / mühürlü operasyonel endeks: `docs/turkiye/georisk-sealed-index-closed-loop-publishing.md`.  
- Birincil sektör öncelikleri (SKDM): `docs/turkiye/sectors-skdm-primary-priorities.md`.  
- Sektörel veri kabul standartları: `docs/standards/` (bu çeyrek manifestinde listelenir).

## Git operasyonu (özet)

1. QOR paketi hazırlandığında bu klasöre `MANIFEST.yml` güncellenir / eklenir.  
2. Aynı commit’e **`archive/2026-Q1`** annotated tag basılır.  
3. İsteğe bağlı: `docs/turkiye/transformers/sealed_reports/` altındaki ilgili mühürlü dosyaların **kopyası** bu arşive eklenir (repo boyutu politikasına göre).

**Feragat:** Bu yapı “tek resmi düzenleyici kaynak” iddiası taşımaz; **şeffaflık, tekrarlanabilirlik ve iç kontrol** içindir.

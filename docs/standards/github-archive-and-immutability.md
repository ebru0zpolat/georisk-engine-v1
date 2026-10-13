# GitHub operasyonu — arşivleme ve değişmezlik

Bu playbook, **`data/archive/YYYY-Qn/`** stratejisinin teknik ve süreç tarafını özetler.

## 1. Çeyrek kapanışı (QOR) checklist

1. **Standart metinleri** gözden geçir: `docs/standards/*.md` ve `docs/turkiye/cco-audit-methodology.md`.  
2. **`data/archive/YYYY-Qn/MANIFEST.yml`** güncelle: o çeyrekte referans verilen dosya yolları + ürün hub listesi.  
3. İsteğe bağlı: mühürlü çıktıları `sealed_reports/` veya `reports/output/` içinden **kopyala** → `data/archive/YYYY-Qn/artifacts/` (klasörü ilk kullanımda oluştur) — repo boyutu politikasına tabi.  
4. Tek commit mesajı örneği: `archive: freeze 2026-Q1 manifest (QOR)`.  
5. **Annotated tag** oluştur:  
   `git tag -a archive/2026-Q1 -m "QOR 2026-Q1 reference bundle"`  
   `git push origin archive/2026-Q1`

## 2. “Asla değiştirilemez” disiplini

- Arşiv klasöründeki dosyalar için **yeniden yazma (amend / force-push) yok** politikası.  
- Düzeltme gerekiyorsa: **yeni commit** ile düzeltme notu + gerekirse **yeni patch tag** (`archive/2026-Q1.1`) — eski tag silinmez.  
- GitHub’da: `main` için **force-push kapatma**, gerekirse **release** üzerinde artefact saklama.

## 3. Büyük veri

Raster / kübik ham veri repo dışında tutulacaksa `MANIFEST.yml` içine:

- `external_artifact_url` (sözleşmeli erişim)  
- `sha256`  

alanları eklenir (kurumsal şema ile genişletilebilir).

## 4. İlişkili kurumsal notlar

- [../turkiye/georisk-sealed-index-closed-loop-publishing.md](../turkiye/georisk-sealed-index-closed-loop-publishing.md)  
- [../turkiye/sectors-skdm-primary-priorities.md](../turkiye/sectors-skdm-primary-priorities.md)  
- [../turkiye/golden-standard-subscription-and-analytics.md](../turkiye/golden-standard-subscription-and-analytics.md)

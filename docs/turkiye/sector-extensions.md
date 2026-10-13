# Sektör genişletmesi (uyumlu genişleme)

`RiskScoreRequest.sector` ve yanıttaki `sector` alanı **serbest string** kalır; yeni değerler API’yi kırmadan kullanılabilir. **Kayıtlı (first-class)** sektörler tek yerde toplanır ve demo / dokümantasyon / skor kalibrasyonu ile birlikte yayınlanır.

## Kaynak dosyalar

| Ne | Nerede |
|----|--------|
| Kayıtlı id kümesi | `app/core/sector_registry.py` → `REGISTERED_SECTOR_IDS`, `DEFAULT_SECTOR_ID`, `AGRICULTURE_SECTOR_ID` |
| Demo preset listesi | `app/services/demo_service.py` → `list_preset_assets()` |
| Bileşen skorları (hash + sektör kalibrasyonu) | `app/scoring/risk_score.py` → `_raw_component_values`, `calibrate_component_vector`, `compute_component_scores` |
| Tarım GEE proxy alanları (stub) | `app/scoring/agriculture_surface.py` → `attach_agriculture_proxies_to_gee_dict`; şema: `app/schemas/gee.py` → `GeeFeatures.ndvi_mean`, `soil_moisture_proxy` |

## Yeni sektör eklerken kontrol listesi

1. **`REGISTERED_SECTOR_IDS`** içine id ekle (`sector_registry.py`).
2. Gerekirse **`DEFAULT_SECTOR_ID`** veya istemci varsayılanlarını ürün kararına göre gözden geçir (çoğu senaryoda `industrial` kalır).
3. **Skor kalibrasyonu:** Kayıtlı sektör için `app/scoring/risk_score.py` içindeki `_SECTOR_COMPONENT_MULTIPLIERS` sözlüğüne `(industrial, pollution, land, ocean, agriculture, sensitivity)` sırasıyla pozitif çarpanlar ekle; `calibrate_component_vector` ortalamayı koruyarak 0–100’e kırpar.
4. **Demo:** `list_preset_assets()` içine sektöre özel en az bir `asset_id` ekle.
5. **Industrial bundle:** `include_industrial_verification_ref` açık preset’lerde yeni AOI’ler için `primary_audit_facilities.geojson` veya eşik (`INDUSTRIAL_VERIFICATION_MAX_MATCH_KM`) ihtiyacını değerlendir.
6. **Rapor / UI:** `frontend/`, `app/reports/*` sabit metinlerinde sektör adı geçiyorsa güncelle.
7. **Dokümantasyon:** Bu dosyada sektörel kısıtlar ve veri kaynakları; SKDM / müşteri notları ve `README` özeti.
8. **Test:** Registry, kalibrasyon ve yeni preset için `TestClient` / birim testleri.

---

## `industrial` (varsayılan)

- **Kullanım:** Genel endüstriyel tesis, liman, enerji yoğun AOİ demo’ları.
- **Veri yüzeyi:** Mevcut ORAS5 + GEE (gece ışığı, NO₂) ve operasyonel audit hatları (termal + S5P L3) ile uyumlu; ayrıntı `docs/turkiye/cco-audit-methodology.md`.

---

## `agriculture` (tarım dikeyi)

### Ürün anlatısı

Büyük ölçekli tarla, silo / depolama ve işleme tesisleri için konum bazlı risk özeti; **bitki örtüsü (NDVI/yeşillik proxy)** ve **toprak nemi / kuraklık stresi** sinyalleri önceliklendirilir. Şu an üretimdeki bileşen skorları **deterministik stub + sektör çarpanları** ile tarım ağırlıklarına kalibre edilir; gerçek NDVI veya nem katmanları bağlandığında `compute_component_scores` ve ilgili connector’lar genişletilmelidir.

### Metodolojik kısıtlar

- **NDVI / yeşillik:** Landsat veya MODIS türevi endeksler bulut/bölgesel arka plan ve mevsimsel döngüden etkilenir; tek tarih “verim garantisi” değildir.
- **Toprak nemi:** ERA5-Land, SMAP veya benzeri ürünler **model / uzaktan algılama proxy**’sidir; parsel ölçeğinde yer ölçümü yerine geçmez.
- **Hukuki / düzenleyici:** Uydu türevi skorlar resmi tarım beyanı, sübvanse veya sigorta poliçesi taahhüdü değildir (genel feragat: `cco-audit-methodology.md` ile hizalı tutun).

### Veri kaynakları (hedef mimari — entegrasyon aşamalı)

| Sinyal | Örnek kaynak | Not |
|--------|----------------|-----|
| NDVI / yeşillik | Landsat L2 SR, MODIS VEG veya GEE hazır koleksiyonlar | Bulut maskesi ve bileşik pencere politikası dokümante edilmeli |
| Toprak nemi / kuraklık stresi | ERA5-Land `swvl1` vb., isteğe bağlı SMAP | Grid çözünürlüğü AOİ’den kaba olabilir; yorum metninde belirtilmeli |
| Emisyon / aktivite (yardımcı) | Mevcut NO₂ / gece ışığı | Tarım dışı kaynaklarla karışım; yorum dikkatli |

### Demo varlıklar

| `asset_id` | Anlatı |
|------------|--------|
| `anatolia_large_scale_crop` | İç Anadolu büyük ölçekli tarla |
| `thrace_grain_storage_processing` | Trakya tahıl silosu / işleme hattı |

### Skorlama (kod)

- Hash tabanı `sector` içerdiği için aynı koordinatta `industrial` vs `agriculture` farklı ham vektör üretir.
- `agriculture` için `land`, `agriculture`, `sensitivity` bileşenleri göreli **yükseltilir**, `industrial` ve `ocean` **düşürülür** (çarpan tablosu `risk_score.py`).

### API — yüzey proxy alanları (şu an)

- `RiskScoreResponse.gee_features` içinde **`ndvi_mean`** ve **`soil_moisture_proxy`** (birim: ürün içi 0–1 bandı yaklaşık proxy; resmi ölçüm değildir).
- `sector == agriculture` iken değerler **deterministik stub** (`app/scoring/agriculture_surface.py`); GEE’den gerçek NDVI / ERA5-Land nem bağlandığında aynı alanlar connector’dan doldurulur, stub devre dışı kalır.
- Markdown / PDF raporları bu alanlar doluysa **“Agriculture surface proxies”** alt başlığıyla listeler.

İleride NDVI/nem gerçekten bağlandığında: ham bileşen skorlarını bu sinyallerden türetin veya `ComponentScores` genişletmesi ile alt alanlar ekleyin; çarpan tablosu ürün kararına göre yeniden kalibre edilir.

---

## `iron_steel` (demir-çelik dikeyi)

### Ürün anlatısı

Entegre demir-çelik ve hadde tesisleri için konum bazlı risk; **endüstriyel aktivite / emisyon proxy** (VIIRS gece ışığı, S5P NO₂) ve hassasiyet bileşenleri önceliklendirilir. CBAM / SKDM müşteri anlatısıyla uyumlu; uydu skorları **düzenleyici kanıt değildir**.

### Skorlama (kod)

- `_SECTOR_COMPONENT_MULTIPLIERS["iron_steel"]`: industrial / pollution / sensitivity ↑; agriculture / ocean ↓.
- Preset: `iron_steel_v1` (`compound_weights_for_preset` — heat ağırlıklı).

### Demo varlıklar

| `asset_id` | Anlatı |
|------------|--------|
| `marmara_integrated_steel_mill` | Marmara entegre demir-çelik tesisi |

### Metodolojik kısıtlar

- NO₂ / gece ışığı **tesis sınırına özgü emisyon envanteri değildir**; bölgesel karışım ve meteoroloji etkiler.
- Thermal / CCO hissedilmiş audit hatları ayrı SKU (`cco-audit-methodology.md`); risk skoru ile karıştırılmamalı.

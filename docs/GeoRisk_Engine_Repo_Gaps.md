# GeoRisk Engine — Repo Gaps Yeniden Analizi

**Sürüm:** 2.1 (re-audit + Sprint 1–2 delivery)  
**Tarih:** 2026-07-19  
**Baz:** `main` @ `7cf418b` + bu dalın S1/S2 değişiklikleri  
**Sprint planı:** [`docs/sprints/repo-gaps-delivery.md`](sprints/repo-gaps-delivery.md)  
**Önceki belge:** `docs/turkiye/georisk-engine-repo-gaps-tr.md` (yalnızca `feature/graph-network-risk-score` dalında; `main`’de yok — BEST/SOW hizalı v1.2 taslağı)

Bu dosya önceki gap listesini **güncel koda karşı yeniden doğrular**. Eski belgedeki birkaç “çekirdek hazır” iddiası `main`’de **geçersizdi**; **Sprint 1–2** ile senkron/async batch, dual-publish şema ve hata zarfı `main` hattına geri taşındı.

---

## Yönetici özeti

| Önceki belge (v1.2) | Durum (Sprint 1–2 sonrası) | Verdict |
|---------------------|----------------------------|---------|
| Çekirdek API `confidence` + `scores.*` | Dual-publish: `risk_score` / `scores` / `confidence` / `meta` + legacy `overall_score`/`components` | **closed (S1)** |
| Senkron `POST /v1/risk/batch` | Var — kısmi başarı, max 500 | **closed (S1)** |
| Async batch | PoC: `/batch/async` + status poll (in-memory); Redis/Celery yok | **partial (S2 PoC)** |
| Bulk ORAS5/GEE fetch yok | Spatial-cell coalesce + batch prefetch | **closed (S4)**; live Zarr/`reduceRegions` credential-bound |
| Senaryo/sel/lineage `RiskScoreResponse`’ta yok | Doğru; **`POST /v1/scenario/run`** ayrı yüzey | **intentional** |
| First-class `iron_steel` | Registry + multipliers + demo + `iron_steel_v1` | **closed (S3)** |
| `preset_id` + `PRESET_NOT_FOUND` | `preset_id` default `industrial_v1`; bilinmeyen → 422 | **closed (S1)** |
| `docs/api/score.md`, `batch.md`, `errors.md` | Eklendi (lean); enterprise SOW paketinin çoğu hâlâ yok | **partial** |

**Kapanan / ilerleyen (eski gap listesinde yok veya “kopuk” denmişti):**

- Scenario Lab scoring — `POST /v1/scenario/run` + golden tests (GEO-150)
- Shared geospatial — geometry registry / spatial index / raster access (GEO-188–192)
- Validation API, cases API, risk-preview
- Snapshot UI — `/snapshot/:assetId`
- Flood/heat alanları şemada scaffold (veri bağlantısı hâlâ stub)

---

## GAP Report — güncel teknik sınırlar

Venture / kurumsal due diligence için: aşağıdakiler “MVP yok” demek değildir; **henüz teslim edilmemiş ölçek / sözleşme / veri katmanı** işleridir. Önceki belgenin pozitif çerçevesi korunur; fakat **senkron batch ve `confidence` şeması abartılmamalıdır**.

### 1) Toplu skor (batch) — senkron **landed (S1)**

| | |
|--|--|
| **Durum** | `POST /v1/risk/batch` → `risk_batch_pipeline.execute_sync_batch`; kısmi başarı; max 500. |
| **Kalan** | Satır içi connector tekrarı (bulk yok — S4). |

### 2) Asenkron uçlar — PoC **landed (S2)**; üretim kuyruğu açık

| | |
|--|--|
| **Durum** | `POST /v1/risk/batch/async` + `GET /v1/risk/batch/status/{task_id}` (in-memory store). |
| **Kalan** | Redis/Celery + kalıcı `job_id` + CSV export — üretim Phase 2. |

### 3) Bulk coğrafi fetch

| | |
|--|--|
| **Durum** | `cds_oras5.fetch_features` / `gee.fetch_features` nokta başına. Batch olsaydı bile satır içi tekrar. |
| **Etki** | Varlık sayısı × (ORAS5 + GEE) gecikmesi doğrusal. |
| **Öneri öncelik** | **P1/P2** — v4 ölçek; GEO-191 raster access iskeleti var, multi-point bulk değil |

### 4) Senaryo / sel / lineage — yüzey ayrışması

| Yüzey | Durum |
|-------|--------|
| `POST /v1/scenario/run` | **Var** — `app/api/scenario.py`, `scenario_lab_service`, GEO-150 cap pipeline, `derive_confidence` |
| `RiskScoreResponse` içinde `scenario` / `horizon` / zengin lineage | **Yok** (bilinçli ayrım — DeerFlow / Scenario Lab) |
| `components.flood` / `components.heat` | Şemada var; skor **SHA256 stub** (`app/scoring/flood_heat.py`) — HydroSAT/ERA5 bağlı değil |
| Blueprint `scores.water_stress` + üst düzey `confidence` | Risk skor yanıtında **yok** (scenario yanıtında `confidence` string band var) |

**Dokümantasyon kuralı (güncel):** Senaryo vaatleri `docs/architecture/scenario-scoring-v1.md` + `docs/01-product/SCORING_PIPELINE.md` üzerinden; Katman-3 “tek skor SOW” içine flood/lineage taşınmamalı — önceki kural geçerli, fakat “senaryo kopuk” ifadesi artık **yanlış** (ayrı API landed).

### 5) Blueprint raster hattı (GEO-51/58+ — ayrı epic)

Önceki SOW gap dosyası bunu kapsamıyordu; ürün vizyonu için hâlâ açık:

| Blueprint adımı | `main` | Gap |
|-----------------|--------|-----|
| Global normalize 0–1 grid | Yok | open |
| `GET /v1/tiles/{layer}/{z}/{x}/{y}.png` | Yok | open |
| deck.gl `TileLayer` | Yok (ScatterplotLayer var) | open |
| Point scoring ORAS5+GEE | Var (fallback’li) | intentional MVP |

---

## 1. API ve sözleşme — doğrulama tablosu

| Alan | Önceki belge | `main` (@ 7cf418b) | Verdict |
|------|--------------|--------------------|---------|
| Tekil skor | `GET`/`POST /v1/risk/score` | `POST /v1/risk/score` (`app/api/risk.py`) | ok (GET yok — dokümante etme) |
| Yanıt şeması | `risk_score`, `scores.*`, `confidence`, `meta` | `overall_score`, `components`, `audit_id`, `generated_at`, industrial/emission alanları | **şema sapması** |
| `preset_id` | Zorunlu | Yok; `sector` string + demo `asset_id` | doc_wrong |
| Batch senkron | Var | Yok | still_gap P0 |
| Batch async | Yok (Phase 2) | Yok | still_gap P1 |
| Hata zarfı | `{error:{code,message,details}}` | `ErrorEnvelope` + `code`/`message`; `details` yok; validation/HTTPException kısmen default FastAPI | partial |
| Scenario | Response’ta yok | Ayrı `/v1/scenario/run` | closed (ayrı yüzey) |
| Preview / validation / cases | — | Var | new surfaces |

**Normatif şema referansı (kod):** `app/schemas/risk.py` — müşteriye “BEST v1.52 scores+confidence” demeden önce ya şema genişletilir (GEO-53 tarzı dual publish) ya da SOW mevcut `components` sözleşmesine çekilir.

---

## 2. Pipeline ve altyapı

### A. Batch

* **Durum:** Ürün yüzeyi tanımsız.  
* **Hedef sırası:** (1) senkron batch + partial success → (2) async job API → (3) bulk connector fetch.

### B. Connector fallbacks (operasyonel gerçek)

* ORAS5: `ORAS5_ZARR_URL` yoksa `_fallback_features()` — CI/dev çalışır, canlı CDS değil (`MASTER_PLAN` WS-06: human blocked).  
* GEE: proje/kimlik yoksa fallback.  
* **Gap değil, risk:** Yatırımcı demosunda “canlı Copernicus” iddiası credential olmadan doğrulanamaz.

### C. Confidence

* **Risk score:** üst düzey `confidence` yok.  
* **Scenario:** `derive_confidence` → band + reasons (`app/scoring/scenario_confidence.py`).  
* Blueprint PDF formülü (`d*0.35 + (1-cloud)*0.33 + (1-gap)*0.32`) risk API’sine **bağlı değil**.

---

## 3. Sektör kaydı

| Id | First-class (`REGISTERED_SECTOR_IDS`) | Not |
|----|----------------------------------------|-----|
| `industrial` | Evet (default) | Çarpanlar `_SECTOR_COMPONENT_MULTIPLIERS` |
| `agriculture` | Evet | NDVI/soil **stub** (`agriculture_surface.py`) |
| `iron_steel` | Hayır | Validation/steel sinyalleri ayrı; sektör kaydı değil |
| `transformer` | Hayır | CCO/sealed audit + docs; risk `sector` id değil |

Eski belgedeki “`iron_steel` first-class” satırı **düzeltilmeli**. Genişleme checklist: `docs/turkiye/sector-extensions.md`.

---

## 4. Performans (SLA)

| Hedef | Gerçekçi mi? |
|-------|----------------|
| Tek asset skor (fallback) | Evet — testlerde hızlı |
| Tek asset skor (canlı ORAS5+GEE) | Bağlantı/credential’a bağlı; SLA yazılı değil |
| 1k asset &lt;5 sn | Batch + bulk + async olmadan **hayır** |

---

## 5. Önceliklendirilmiş backlog (yeniden sıralama)

| Öncelik | İş | Gerekçe |
|---------|----|---------|
| **Done S1** | Senkron batch + dual-publish şema + preset + error `details` + `docs/api/*` | Bu dal |
| **Done S2** | Async batch PoC (in-memory) | Bu dal |
| **P0** | Canlı ORAS5 smoke (human: CDS key) | `MASTER_PLAN` WS-06 |
| **Done S3** | `iron_steel` + GET `/v1/risk/score` | `main` #52 |
| **Done S4** | Spatial-cell bulk + flood/heat RasterAccess + soil ERA5 fixture | Bu dal |
| **Done S5** | `GET /v1/tiles/...png` Marmara pilot | Bu dal |
| **P2** | Live Zarr/`reduceRegions`, Redis/Celery, deck.gl client | Credential / frontend |

---

## 6. Bilinçli ayrışmalar (gap değil)

| Özellik | Neden ayrı |
|---------|------------|
| Industrial / pollution / CCO sealed audit | Türkiye wedge; blueprint “ESG excluded MVP” global raster içindi |
| 6-component `ComponentScores` | Mevcut demo/API sözleşmesi; blueprint `scores` yan yana taşınmalı |
| DeerFlow anlatı / VC-builder | Skor motoru dışında — `docs/architecture/deerflow-georisk-separation.md` |
| Scenario Lab vs `/v1/risk/score` | GEO-150 bilinçli ikinci yüzey |

---

## 7. Doğrulama yöntemi (bu audit)

```text
Routers:     app/main.py + app/api/*.py
Şema:        app/schemas/risk.py, scenario.py, errors.py
Sektör:      app/core/sector_registry.py
Scoring:     app/scoring/risk_score.py, flood_heat.py, agriculture_surface.py
Scenario:    app/api/scenario.py, docs/01-product/SCORING_PIPELINE.md
Batch arama: app/** — risk_batch* / /risk/batch → 0 eşleşme
Önceki doc:  git show feature/graph-network-risk-score:docs/turkiye/georisk-engine-repo-gaps-tr.md
```

---

## Revizyon

| Sürüm | Özet |
|-------|------|
| 2.1 | Sprint 1–2 teslim: dual-publish, sync/async batch PoC, error envelope, `docs/api/*`; backlog S3–S5 |
| 2.0 | `main` re-audit: senkron batch / BEST `confidence` iddiaları düzeltildi |
| 1.x | Önceki TR taslak (`georisk-engine-repo-gaps-tr.md`) — SOW dalı; `main` ile sapmış |

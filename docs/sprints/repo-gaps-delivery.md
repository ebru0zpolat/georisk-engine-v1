# Repo Gaps Delivery — Sprint Plan

**Baz:** [`docs/GeoRisk_Engine_Repo_Gaps.md`](../GeoRisk_Engine_Repo_Gaps.md)  
**Kapsam:** Eski SOW gap belgesinde “hazır” denip `main`’de olmayanlar + Phase-2 / blueprint gap’ler.

---

## Sprint map

| Sprint | Hedef | Durum |
|--------|--------|--------|
| **S1** | Dual-publish şema + hata zarfı + senkron batch + `docs/api/*` | **Done** (`main` via #52) |
| **S2** | Async batch PoC | **Done** (`main` via #52) |
| **S3** | `iron_steel` + GET `/v1/risk/score` | **Done** (`main` via #52) |
| **S4** | Spatial-cell bulk coalesce + flood/heat RasterAccess + agriculture soil via ERA5 fixture | **Done (this PR)** |
| **S5** | Blueprint `GET /v1/tiles/{layer}/{z}/{x}/{y}.png` Marmara pilot | **Done (this PR)** |

Human-only: CDS / `ORAS5_ZARR_URL` canlı smoke (`MASTER_PLAN` WS-06).

---

## S4 acceptance

- [x] `fetch_features_many` spatial-cell coalesce (`spatial_cell_coalesce` / `spatial_cell_singleton`)
- [x] Batch → prefetch → `score(..., prefetched=)`
- [x] Flood/heat via `RasterAccess` (ERA5 temp + MERIT elevation proxy; mock when no CDS key)
- [x] Agriculture `soil_moisture_proxy` via `era5_soil_moisture` fixtures
- [ ] Live GEE `reduceRegions` / Zarr multi-point window (needs credentials + store schema)

## S5 acceptance

- [x] `GET /v1/tiles/{layer}/{z}/{x}/{y}.png` (`total_risk` / `climate` / `water`)
- [x] Marmara pilot bbox + PNG via Pillow
- [x] `docs/api/tiles.md` + tests
- [ ] deck.gl `TileLayer` client wiring (frontend follow-up)

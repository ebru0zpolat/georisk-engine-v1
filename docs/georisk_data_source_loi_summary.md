# GeoRisk Engine — Data Source LOI Package (Summary)

**Version:** v1.0  
**Date:** 2026-06  
**Status:** Internal / partner-facing draft  
**Canonical registry:** `app/core/data_source_registry.py`  
**API:** `GET /v1/data-sources`  
**Full package (HTML):** [georisk_data_source_loi_package.html](./georisk_data_source_loi_package.html)

---

## Purpose

This package catalogs every external data plane GeoRisk Engine depends on — production risk API connectors, operational audit scripts, and roadmap agriculture layers — together with **Letter of Intent (LOI)** posture, fallback policy, and links to acceptance standards.

Satellite and climate proxies are **not** regulatory proof. Outputs are decision-support signals framed against climatological baselines and documented QA masks.

---

## Executive summary

| Tier | Count | Role |
|------|-------|------|
| **Production** | 3 | `POST /v1/risk/score` — ORAS5 ocean + GEE night lights + GEE NO₂ |
| **Audit** | 4 | Operational CCO / Primary Audit scripts (Landsat thermal, S5P NO₂/CO, VIIRS DNB) |
| **Roadmap** | 2 | Agriculture NDVI + soil moisture (stub until GEE wired) |

### LOI posture

| Status | Meaning |
|--------|---------|
| **active** | In production or audit pipelines today; GEE/CDS credentials required for live pulls |
| **intent** | ORAS5 Zarr URL configured when CDS analysis-ready store is provisioned |
| **planned** | Registry entry + API surface exist; connector returns deterministic stub |

### Fallback discipline (all tiers)

- **ORAS5:** `_fallback_features()` when `ORAS5_ZARR_URL` unset — CI and local dev stay green.
- **GEE risk API:** `_fallback_features()` when `gee_enabled=false` or `gee_project` missing.
- **Audit scripts:** `AUDIT_USE_MOCK=true` skips Earth Engine RPC.
- **Agriculture:** `agriculture_surface.attach_agriculture_proxies_to_gee_dict` fills NDVI/soil fields deterministically until real layers connect.

---

## Production data sources

### ORAS5 Ocean Reanalysis (CDS Zarr)

- **Provider:** Copernicus CDS / ECMWF ORAS5  
- **Delivery:** `app/connectors/cds_oras5.py`  
- **Features:** SST trend, SST anomaly z-score, sea-level trend, ocean variability index  
- **LOI:** Intent to operate under CDS terms; Zarr store URL via environment only (never committed)

### VIIRS Night-Time Lights (GEE)

- **Dataset:** `NASA/VIIRS/002/VNP46A2` — `Gap_Filled_DNB_BRDF_Corrected_NTL`  
- **Delivery:** `app/connectors/gee.py`  
- **Use:** Industrial activity proxy vs 30-year climatological baseline (configurable)

### Sentinel-5P OFFL L3 NO₂ (GEE)

- **Dataset:** `COPERNICUS/S5P/OFFL/L3_NO2`  
- **Band:** `tropospheric_NO2_column_number_density` (mol/m²)  
- **Delivery:** `app/connectors/gee.py`  
- **Standard:** [cement-data-acceptance-and-processing.md](./standards/cement-data-acceptance-and-processing.md)

---

## Audit pipeline data sources

| ID | Script | Standard |
|----|--------|----------|
| `audit_landsat_thermal` | `scripts/landsat_thermal_audit.py` | Cement CCO — QA_PIXEL mask, ST_B10 → °C |
| `audit_s5p_no2` | `scripts/s5p_no2_audit.py` | Cement CCO — OFFL L3 tropospheric NO₂ |
| `audit_s5p_co` | `scripts/s5p_co_audit.py` | Transformer Primary Audit — OFFL L3 CO |
| `audit_viirs_dnb` | `scripts/viirs_ntl_audit.py` | Transformer — `avg_rad` + **`cf_cvg`** transparency |

---

## Roadmap (agriculture)

| ID | Target | Current state |
|----|--------|---------------|
| `roadmap_ndvi` | Landsat L2 SR / MODIS via GEE | Stub in `agriculture_surface.py` |
| `roadmap_soil_moisture` | ERA5-Land `swvl1` / optional SMAP | Stub in `agriculture_surface.py` |

Sector checklist: [turkiye/sector-extensions.md](./turkiye/sector-extensions.md)

---

## Related standards index

- [standards/README.md](./standards/README.md) — sector acceptance standards  
- [turkiye/cco-audit-methodology.md](./turkiye/cco-audit-methodology.md) — mask policy and legal framing  
- [business/investor-pitch.md](./business/investor-pitch.md) — product-level data engine overview

---

## Integration checklist (engineering)

1. Add or update entry in `app/core/data_source_registry.py`.  
2. Import dataset constants in connector or audit script (no duplicated string literals).  
3. Document acceptance rules under `docs/standards/` if sector-specific.  
4. Expose via `GET /v1/data-sources`; run `pytest tests/test_data_source_registry.py`.  
5. Update this summary and HTML package when LOI status changes.

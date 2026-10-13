# GeoRisk Engine — Data Source Validation Package (Summary)

**Version:** v1.0  
**Date:** 2026-06  
**Status:** Internal / audit-ready draft  
**Canonical registry:** `app/core/data_source_registry.py`  
**Validation rules:** `app/core/data_source_validation.py`  
**API:** `GET /v1/data-sources/validation`  
**Full package (DOCX):** [GeoRisk_DataSource_Validation_Package.docx](./GeoRisk_DataSource_Validation_Package.docx)

---

## Purpose

This package defines **acceptance criteria**, **runtime validation checks**, and **delivery-mode posture** for every external data plane GeoRisk Engine depends on. It complements the [Data Source LOI Package](./georisk_data_source_loi_summary.md), which documents partner-facing Letter of Intent posture.

Satellite and climate proxies are **not** regulatory proof. Validation confirms that connectors honour documented fallback discipline and sector acceptance standards — not ground-truth accuracy against facility meters.

---

## Validation model

| Delivery mode | Meaning |
|---------------|---------|
| **live** | Credentials configured; connector may call CDS / Earth Engine |
| **fallback** | Production API returns deterministic stub (CI / local dev) |
| **mock** | Audit script uses `AUDIT_USE_MOCK=true` (no EE RPC) |
| **stub** | Roadmap layer; agriculture proxies filled deterministically |

| Check status | Meaning |
|--------------|---------|
| **pass** | Criterion satisfied |
| **warn** | Expected degraded mode (e.g. fallback when URL unset) |
| **fail** | Registry/connector mismatch or missing feature keys |
| **skip** | No runtime evaluator (should not occur in v1.0) |

---

## Registered sources (9)

| Tier | Count | Validation focus |
|------|-------|------------------|
| **Production** | 3 | ORAS5 Zarr URL, GEE credentials, dataset id alignment |
| **Audit** | 4 | OFFL L3 bands, QA_PIXEL mask, `cf_cvg` transparency, mock path |
| **Roadmap** | 2 | Agriculture stub keys present until GEE wired |

---

## Acceptance standards cross-reference

| Source id | Standard |
|-----------|----------|
| `gee_s5p_no2`, `audit_landsat_thermal`, `audit_s5p_no2` | [cement-data-acceptance-and-processing.md](./standards/cement-data-acceptance-and-processing.md) |
| `audit_s5p_co`, `audit_viirs_dnb` | [transformer-data-acceptance-and-processing.md](./standards/transformer-data-acceptance-and-processing.md) |
| `roadmap_ndvi`, `roadmap_soil_moisture` | [turkiye/sector-extensions.md](./turkiye/sector-extensions.md) |

Mask policy and legal framing: [turkiye/cco-audit-methodology.md](./turkiye/cco-audit-methodology.md).

---

## Runtime API

```http
GET /v1/data-sources/validation
GET /v1/data-sources/{source_id}/validation
```

Example: `GET /v1/data-sources/validation` returns per-source `delivery_mode`, check list, and `passed` rollup.

---

## Engineering checklist

1. Add entry to `app/core/data_source_registry.py`.  
2. Add acceptance checks to `VALIDATION_CHECKS` in `app/core/data_source_validation.py`.  
3. Import dataset constants in connector or audit script (no duplicated literals).  
4. Document sector rules under `docs/standards/` when applicable.  
5. Regenerate DOCX: `python scripts/generate_data_source_validation_docx.py`.  
6. Run `pytest tests/test_data_source_registry.py tests/test_data_source_validation.py`.

---

## Related documents

- [georisk_data_source_loi_summary.md](./georisk_data_source_loi_summary.md) — LOI / partnership posture  
- [georisk_data_source_loi_package.html](./georisk_data_source_loi_package.html) — partner HTML catalog  
- [standards/README.md](./standards/README.md) — sector acceptance index

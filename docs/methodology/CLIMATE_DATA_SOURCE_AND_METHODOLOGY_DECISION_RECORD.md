# Climate Data Source and Methodology Decision Record

**Document title:** Climate Data Source and Methodology Decision Record (Phase 1: Extreme Heat)  
**Date:** 7 August 2026  
**Document status:** **Approved (Phase 1 source + indicators)** — engineering follow-ups still open for WP-08 wiring  
**Opened:** 7 August 2026  
**Last revised:** 8 August 2026 (licence-gate closure for allowlisted MPI-ESM1-2 models)  
**Parent plan:** [`docs/GeoRisk_Engine_Technical_Validation_and_CMIP6_CORDEX_Workplan_2026-08-07.md`](../GeoRisk_Engine_Technical_Validation_and_CMIP6_CORDEX_Workplan_2026-08-07.md) §7 / §13  
**Phase 1 scope:** Narrow extreme-heat pathway only (not multi-hazard).  
**Adapter:** [`engine/climate/cmip6_heat_adapter.py`](../../engine/climate/cmip6_heat_adapter.py)

Until WP-08 is wired into the five-layer pipeline with labelled provenance, marketing must not claim CMIP-backed forward loss in demos.

---

## Purpose

Record binding choices for the first **real** climate-scenario data path that may populate 2030/2050 `HazardScenarioIntensities`.

---

## Decision checklist (approved)

| # | Topic | Status | Decision |
|---|-------|--------|----------|
| 1 | Primary product | **Approved** | Copernicus CDS — **CMIP6** Global Climate Projections |
| 2 | Scenario set | **Approved** | **SSP2-4.5 + SSP5-8.5** (both produced for the pilot; one adapter series per scenario) |
| 3 | Extreme-heat indicators | **Approved** | **Primary: WSDI** (ETCCDI); **Diagnostic: TX90p** (ETCCDI). **Not** fixed TX > 35 °C day counts |
| 4 | Baseline climatology | **Approved** | **1991–2020** (WMO). Requires historical (≤2014) + SSP (2015–2020) merged per model/member |
| 5 | Horizon definition | **Approved (working)** | Multi-year windows (e.g. 2021–2040 / 2041–2060); single years forbidden |
| 6 | Spatial method | **Approved** | Nearest-neighbour **inside domain only** — no silent edge snap |
| 7 | Licence | **Approved (closed)** | Versioned **model licence allowlist** + commercial-use check (`engine/climate/cmip6_model_licences_v1.json`, `verified: true` as of 2026-08-08). Phase 1 models **MPI-ESM1-2-HR** and **MPI-ESM1-2-LR** are **CC BY 4.0** (commercial use permitted with attribution) per [WCRP CMIP6_CVs source_id licenses](https://wcrp-cmip.github.io/CMIP6_CVs/docs/CMIP6_source_id_licenses.html) and [PCMDI ToU 6.2](https://pcmdi.llnl.gov/CMIP6/TermsOfUse/TermsOfUse6-2.html). Free-text NetCDF `licence` fields alone remain insufficient; unlisted / non-commercial models fail closed. Evidence URLs live in the allowlist JSON. |
| 8 | Missing-data policy | **Approved** | Horizons unavailable — no synthetic fill (PR #103) |
| 9 | Ensemble | **Approved (working)** | Single model/member per series; identity from manifest/attrs |
| 10 | Bias correction | **Approved** | None; stamp `bias_corrected: false` |
| 11 | Provenance | **Approved** | `DataProvenance` + adapter identity fields from file/manifest |
| 12 | File integrity | **Approved** | **SHA-256 mandatory per file** (CLIM-03) |
| 13 | File structure | **Approved** | Historical + SSP files merged **deterministically per model/member** via manifest; overlaps/duplicates rejected |
| 14 | Window completeness | **Approved** | Baseline and horizon years require **complete daily coverage**; partial years rejected |
| 15 | Calendar handling | **Approved** | cftime-safe parsing; noleap/365_day exercised in tests |

**Supersession:** Earlier CORDEX-EUR-11 draft preference, the absolute TX > 35 °C heat-day metric, and the 1961–1990 ETCCDI default baseline are **withdrawn** for Phase 1.

---

## Indicators (normative)

| Role | Index | Definition |
|------|-------|------------|
| Primary | **WSDI** | Annual count of days in spells of ≥6 consecutive days with TX > calendar-day 90th percentile (5-day window) from the baseline period; spells do not span years |
| Diagnostic | **TX90p** | Percentage of days with TX > the same calendar-day 90th percentile |

Implementation: `engine/climate/indices_etccdi.py`.

---

## CLIM-03 adapter contract

- Module: `engine.climate.cmip6_heat_adapter.Cmip6HeatAdapter`
- Mandatory SHA-256 **per file** (`expected_sha256` or manifest `files[].sha256`)
- Multi-file manifest: historical + SSP merged deterministically per model/member; time overlap, duplicate timestamps, unit/calendar/identity mismatches all fail closed
- Reject all non-finite values (NaN, ±inf)
- Reject coordinates outside the grid domain (no silent nearest-edge bind)
- Baseline (default **1991–2020**) and horizon years require complete daily coverage
- cftime-safe calendars: standard / gregorian / proleptic_gregorian / noleap / 365_day
- Licence gate: model must appear in the versioned allowlist with `commercial_use: true`
- `domain`, `dataset_id`, `model_id`, `member_id`, `scenario_id`, `licence` from manifest and/or NetCDF global attributes — **never hard-coded** in the adapter

## WP-08 status (honest)

| Slice | Status |
|-------|--------|
| CLIM-03 adapter + WSDI/TX90p core | Implemented (PR #107 — **starting slice**, not WP-08 completion) |
| Real CDS download + historical+SSP preprocessing | **Not yet** |
| Versioned 2030/2050 intensity maps | **Not yet produced** |
| Five-layer wiring | WP-09 |
| Provenance schema (PR #105) | Open on an independent branch |

---

## Explicit non-claims

- Not classical actuarial EAL.  
- Not Dutch-calibrated until pack-nl + local curves ship.  
- Not CORDEX-EUR-11 Phase 1 primary (CMIP6 approved instead).  
- Not absolute-threshold “heat days > 35 °C” as the Phase 1 indicator.  
- Not bias-corrected.  
- Not CSRD-/IFRS S2-compliant by virtue of using CMIP6.

---

## Change control

Any change to approved rows bumps this record, methodology notes, fixtures/checksums, and golden baselines if intensities change.

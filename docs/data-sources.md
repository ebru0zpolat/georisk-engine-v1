# Data source register

**Canonical code catalog:** `app/core/data_source_registry.py`  
**Landing claim rule:** [`data-claims-spec.md`](../data-claims-spec.md)  
**Count used on the public Data Infrastructure header:** **9** production, audit and roadmap entries (**3 production · 4 audit · 2 roadmap**). Must match this table and `DATA_SOURCE_REGISTRY`.

Landing marketing cards that are **not** in this table must be labelled **Roadmap** and must not claim production integration. Every numeric claim on a card must link a provider specification (or be labelled Status/Roadmap only).

| # | Registry id | Name | Provider | Tier | Delivery | Licence / access | Cadence note | Spec / collection |
|---|-------------|------|----------|------|----------|------------------|--------------|-------------------|
| 1 | `oras5_ocean` | ORAS5 Ocean Reanalysis | Copernicus CDS / ECMWF | production | CDS Zarr | [CDS licence](https://cds.climate.copernicus.eu/) | Monthly reanalysis product | CDS ORAS5 / `ORAS5_ZARR_URL` |
| 2 | `gee_viirs_ntl` | VIIRS Night-Time Lights | NASA / NOAA via GEE | production | GEE | GEE + product ToS | Daily/composite product (not optical revisit) | [VNP46A2](https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VNP46A2) |
| 3 | `gee_s5p_no2` | Sentinel-5P OFFL L3 NO₂ | Copernicus / ESA via GEE | production | GEE | Copernicus + GEE | OFFL L3 product latency | [S5P NO₂](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_NO2) |
| 4 | `audit_landsat_thermal` | Landsat 8/9 C2 L2 Thermal | USGS via GEE | audit | GEE audit | USGS / GEE | 16-day revisit (8-day with L8+L9) | [Landsat-9](https://www.usgs.gov/landsat-missions/landsat-9) · `LANDSAT/LC08/C02/T1_L2` (+ LC09) |
| 5 | `audit_s5p_no2` | Sentinel-5P OFFL L3 NO₂ (audit) | Copernicus via GEE | audit | GEE audit | Copernicus + GEE | OFFL L3 | [S5P NO₂](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_NO2) |
| 6 | `audit_s5p_co` | Sentinel-5P OFFL L3 CO | Copernicus via GEE | audit | GEE audit | Copernicus + GEE | OFFL L3 | [S5P CO](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_CO) |
| 7 | `audit_viirs_dnb` | VIIRS DNB Monthly VCMSLCFG | NOAA via GEE | audit | GEE audit | NOAA / GEE | Monthly composite | [VCMSLCFG](https://developers.google.com/earth-engine/datasets/catalog/NOAA_VIIRS_DNB_MONTHLY_V1_VCMSLCFG) |
| 8 | `roadmap_ndvi` | NDVI / greenness proxy | Landsat L2 SR / MODIS (planned) | roadmap | stub | — | Roadmap stub | See registry |
| 9 | `roadmap_soil_moisture` | Soil moisture proxy | ERA5-Land / SMAP (planned) | roadmap | stub | — | Roadmap stub | [ERA5](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5) (target) |

## Optical revisit (marketing card: Sentinel-2 / Landsat-9 — Roadmap)

| Mission | Published revisit | Native GSD | Coverage |
|---------|-------------------|------------|----------|
| Sentinel-2 (constellation) | **5 days** at equator; ~2–3 days mid/high latitudes ([ESA](https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-2)) | 10 / 20 / 60 m | Global **land** (~56°S–84°N) |
| Landsat-9 | **16 days**; **8 days** with Landsat-8 ([USGS](https://www.usgs.gov/landsat-missions/landsat-9)) | 30 m MS / 15 m pan / 100 m thermal (delivered 30 m) | Global land & coastal |

There is **no** six-hour optical pipeline-ingest job in this repository. Connectors run on demand (with labelled stub fallbacks). Do not display `PIPELINE INGEST` / `REFRESH` for optical missions.

## Spec verification

| Field | Value |
|-------|--------|
| `specVerifiedOn` | 2026-08-06 |
| Next review | Quarterly (with landing Data Infrastructure copy) |

When adding or removing a registry entry, update this table **and** the landing header tier breakdown in the same PR.

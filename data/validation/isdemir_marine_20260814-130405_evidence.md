# GeoRisk Validation Evidence — İsdemir marine context (ORAS5) 🟢 LIVE

- **Validation id:** `ISD-MARINE-20260814-130405`
- **GeoRisk version:** georisk-engine-v0.1
- **Schema version:** 1.0
- **Generated at:** 2026-08-14T13:04:05.605685+00:00

## Request metadata

- **Point:** 36.725833, 36.186111 (İsdemir / Payas, İskenderun Bay)
- **Window:** 1991-01-01 → 2020-12-31
- **Data access:** cds-arco-zarr (bearer-header)
- **Variables:** sosstsst, sossheig
- **Product types:** consolidated, operational
- **Stores:** https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr, https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/operational/geoChunked.zarr

- **Expected fixture grid index:** {"selected_latitude_index": 507, "selected_longitude_index": 865, "selected_cell": {"latitude": 36.75, "longitude": 36.25}, "snap_distance_km": 6.2955}

## Verified live grid index (read from store arrays)

- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr` → indices (507, 865), cell (36.75, 36.25), snap 6.2955 km
- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/operational/geoChunked.zarr` → indices (507, 865), cell (36.75, 36.25), snap 6.2955 km

- **Grid-index agreement:** True (verified_live_grid_index is authoritative; the fixture is reference only — a mismatch keeps both values and never forces the live index onto the fixture)

## Ocean cell selection (nearest non-masked cell)

- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr` → indices (507, 864), cell (36.75, 36.0), snap 16.8005 km · nearest non-masked cell at first time step
- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/operational/geoChunked.zarr` → indices (507, 864), cell (36.75, 36.0), snap 16.8005 km · nearest non-masked cell at first time step

## Time series

- **sst:** n=360 1991-01-01 00:00:00 → 2020-12-01 00:00:00 (15.105093 … 30.077227) · sha256 `68ee0d557f6edde8276be97a670742a40f6386fe189e1d071e8b54144fe53e35`
- **sea_surface_height:** n=360 1991-01-01 00:00:00 → 2020-12-01 00:00:00 (-0.669003 … -0.281878) · sha256 `a1f55229afc391a3f23cb44b244d657f5aa813b2623919d9af0f4b529c103d4c`

## Features and checksums

- **Features:** {"sst_trend_c_per_decade": 0.5586348079829431, "sst_anomaly_zscore": -0.3210618793964386, "sea_level_trend_mm_per_year": 3.2947225235731166, "ocean_variability_index": 1.0}
- **Ocean risk score:** 80/100
- **series_sha256:** `236676b1834bce480dd24dec66b1e1556f2067fab456e6c9bb34553c4c43a7e5`
- **features_sha256:** `80c663f07dc6c6494c648e43ab8b0b1c73370676fcffe07421524b82515d3f63`
- **record_sha256:** `305f049db16dd31de37d7a79fd51a9327a4c96a30a638602289825e0597d65b2`

## Evidence classification (canonical gate statuses)

- **declaration_integrity:** `passed`
- **offline_pipeline_parity:** `passed`
- **deterministic_fixture_selection:** `passed`
- **credential_contract:** `passed`
- **dimensionality_controls:** `passed`
- **fail_closed_behavior:** `passed`
- **verified_live_grid_index:** `pending`
- **live_source_parity:** `pending`
- **cross_product_homogeneity:** `pending`
- **scaling_calibration:** `pending`
- **production_smoke:** `pending`
- **durable_retention:** `pending`
- **asset_loss_pathway:** `not_established`
- **production_eligible:** `False`

## Operational evidence

- **authenticated_arco_data_access:** passed
- **provisional_cross_product_series:** 1991–2020 consolidated+operational merged series
- **note:** this record is operational evidence (authenticated Zarr metadata+data access); it does NOT close homogeneity / scaling-calibration / retention / asset-loss gates (see docs/validation/oras5-evidence-gates.md); ERA5 smoke is recorded separately by scripts/era5_retrieve_smoke.py

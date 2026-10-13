# GeoRisk Validation Evidence — İsdemir marine context (ORAS5) 🟢 LIVE

- **Validation id:** `ISD-MARINE-20260814-124237`
- **GeoRisk version:** georisk-engine-v0.1
- **Schema version:** 1.0
- **Generated at:** 2026-08-14T12:42:37.582583+00:00

## Request metadata

- **Point:** 36.7333, 36.2 (İsdemir / Payas, İskenderun Bay)
- **Window:** 1991-01-01 → 2020-12-31
- **Data access:** cds-arco-zarr (bearer-header)
- **Variables:** sosstsst, sossheig
- **Product types:** consolidated, operational
- **Stores:** https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr, https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/operational/geoChunked.zarr

## Grid selection (nearest-neighbour snap)

- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr` → indices (507, 865), cell (36.75, 36.25), snap 4.8268 km
- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/operational/geoChunked.zarr` → indices (507, 865), cell (36.75, 36.25), snap 4.8268 km

## Ocean cell selection (nearest non-masked cell)

- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr` → indices (507, 864), cell (36.75, 36.0), snap 17.9175 km · nearest non-masked cell at first time step
- `https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/operational/geoChunked.zarr` → indices (507, 864), cell (36.75, 36.0), snap 17.9175 km · nearest non-masked cell at first time step

## Time series

- **sst:** n=360 1991-01-01 00:00:00 → 2020-12-01 00:00:00 (15.105093 … 30.077227) · sha256 `68ee0d557f6edde8276be97a670742a40f6386fe189e1d071e8b54144fe53e35`
- **sea_surface_height:** n=360 1991-01-01 00:00:00 → 2020-12-01 00:00:00 (-0.669003 … -0.281878) · sha256 `a1f55229afc391a3f23cb44b244d657f5aa813b2623919d9af0f4b529c103d4c`

## Features and checksums

- **Features:** {"sst_trend_c_per_decade": 0.5586348079829431, "sst_anomaly_zscore": -0.3210618793964386, "sea_level_trend_mm_per_year": 3.2947225235731166, "ocean_variability_index": 1.0}
- **Ocean risk score:** 80/100
- **series_sha256:** `236676b1834bce480dd24dec66b1e1556f2067fab456e6c9bb34553c4c43a7e5`
- **features_sha256:** `80c663f07dc6c6494c648e43ab8b0b1c73370676fcffe07421524b82515d3f63`
- **record_sha256:** `8abca067ad4809f8fc8701ddfbd5a2edb4596f212654e60f32e8ad18e600354b`

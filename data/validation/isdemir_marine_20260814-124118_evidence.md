# GeoRisk Validation Evidence — İsdemir marine context (ORAS5) 🟢 LIVE

- **Validation id:** `ISD-MARINE-20260814-124118`
- **GeoRisk version:** georisk-engine-v0.1
- **Schema version:** 1.0
- **Generated at:** 2026-08-14T12:41:18.402984+00:00

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

## Time series

- **sst:** n=0 None → None (None … None) · sha256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- **sea_surface_height:** n=0 None → None (None … None) · sha256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

## Features and checksums

- **Features:** {"sst_trend_c_per_decade": 0.0, "sst_anomaly_zscore": 0.0, "sea_level_trend_mm_per_year": 0.0, "ocean_variability_index": 0.0}
- **Ocean risk score:** 30/100
- **series_sha256:** `34fcd7314ac32b1479aabee8c895515793150bca8b60d9f21826ffc823c2f1d6`
- **features_sha256:** `8a47c99e6f2d376cd5b3fad435165294831d348ad701932f2c0c24d0f83b0890`
- **record_sha256:** `8eac6bb18a749ea28468bb0d78cfb5af3f9c0a8ce6af1cb24b7c5967da7139ad`

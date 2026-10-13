"""Canonical catalog of GeoRisk Engine data sources (production, audit, roadmap).

Single source for dataset ids, delivery planes, fallback policy, and LOI posture.
Connectors and audit scripts import constants from here where applicable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DataSourceTier = Literal["production", "audit", "roadmap"]
LoiStatus = Literal["active", "intent", "planned"]
DeliveryPlane = Literal["gee", "cds_zarr", "gee_audit", "stub"]


@dataclass(frozen=True)
class DataSourceEntry:
    id: str
    name: str
    provider: str
    tier: DataSourceTier
    delivery: DeliveryPlane
    dataset_id: str | None
    bands: tuple[str, ...]
    units: dict[str, str]
    fallback_policy: str
    standards_ref: str | None
    loi_status: LoiStatus
    connector_module: str | None
    feature_keys: tuple[str, ...] = ()


# --- Dataset / collection ids (imported by connectors and audit scripts) ---

ORAS5_ZARR_PRODUCT = "ORAS5 reanalysis (CDS analysis-ready Zarr)"

GEE_VIIRS_NTL_DATASET = "NASA/VIIRS/002/VNP46A2"
GEE_VIIRS_NTL_BAND = "Gap_Filled_DNB_BRDF_Corrected_NTL"

GEE_S5P_NO2_DATASET = "COPERNICUS/S5P/OFFL/L3_NO2"
GEE_S5P_NO2_BAND = "tropospheric_NO2_column_number_density"

VIIRS_DNB_MONTHLY_COLLECTION = "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG"
VIIRS_DNB_AVG_RAD_BAND = "avg_rad"
VIIRS_DNB_CF_CVG_BAND = "cf_cvg"

S5P_L3_NO2_COLLECTION = "COPERNICUS/S5P/OFFL/L3_NO2"
S5P_L3_CO_COLLECTION = "COPERNICUS/S5P/OFFL/L3_CO"

LANDSAT_C2_L2_COLLECTION = "LANDSAT/LC08/C02/T1_L2"  # LC09 sibling in audit script
LANDSAT_ST_B10_BAND = "ST_B10"
LANDSAT_QA_PIXEL_BAND = "QA_PIXEL"

# Roadmap (agriculture / land)
ROADMAP_NDVI_DATASET = "LANDSAT/LC08/C02/T1_L2"  # SR path; GEE collection TBD at wire-up
ROADMAP_ERA5_LAND_DATASET = "ECMWF/ERA5_LAND/MONTHLY_AG"  # soil moisture proxy target


DATA_SOURCE_REGISTRY: tuple[DataSourceEntry, ...] = (
    DataSourceEntry(
        id="oras5_ocean",
        name="ORAS5 Ocean Reanalysis",
        provider="Copernicus CDS / ECMWF ORAS5",
        tier="production",
        delivery="cds_zarr",
        dataset_id=ORAS5_ZARR_PRODUCT,
        bands=("sst", "zos"),
        units={
            "sst_trend_c_per_decade": "°C/decade",
            "sst_anomaly_zscore": "z-score",
            "sea_level_trend_mm_per_year": "mm/year",
            "ocean_variability_index": "0-1 index",
        },
        fallback_policy=(
            "Deterministic stub when ORAS5_ZARR_URL unset (CI/local/demo). "
            "Production refuses the stub at startup and request time."
        ),
        standards_ref=None,
        loi_status="intent",
        connector_module="app.connectors.cds_oras5",
        feature_keys=(
            "sst_trend_c_per_decade",
            "sst_anomaly_zscore",
            "sea_level_trend_mm_per_year",
            "ocean_variability_index",
        ),
    ),
    DataSourceEntry(
        id="gee_viirs_ntl",
        name="VIIRS Night-Time Lights (GEE risk API)",
        provider="NASA / NOAA via Google Earth Engine",
        tier="production",
        delivery="gee",
        dataset_id=GEE_VIIRS_NTL_DATASET,
        bands=(GEE_VIIRS_NTL_BAND,),
        units={"night_lights_mean": "nW/cm²/sr"},
        fallback_policy=(
            "Deterministic stub when GEE disabled or project unset (CI/local/demo). "
            "Production refuses the stub at startup and request time."
        ),
        standards_ref="docs/turkiye/georisk-sealed-index-closed-loop-publishing.md",
        loi_status="active",
        connector_module="app.connectors.gee",
        feature_keys=("night_lights_mean", "night_lights_baseline_mean", "night_lights_relative_deviation"),
    ),
    DataSourceEntry(
        id="gee_s5p_no2",
        name="Sentinel-5P OFFL L3 Tropospheric NO₂ (GEE risk API)",
        provider="Copernicus / ESA via Google Earth Engine",
        tier="production",
        delivery="gee",
        dataset_id=GEE_S5P_NO2_DATASET,
        bands=(GEE_S5P_NO2_BAND,),
        units={"no2_mean": "mol/m²"},
        fallback_policy=(
            "Deterministic stub when GEE disabled or project unset (CI/local/demo). "
            "Production refuses the stub at startup and request time."
        ),
        standards_ref="docs/standards/cement-data-acceptance-and-processing.md",
        loi_status="active",
        connector_module="app.connectors.gee",
        feature_keys=("no2_mean", "no2_baseline_mean", "no2_relative_deviation"),
    ),
    DataSourceEntry(
        id="audit_landsat_thermal",
        name="Landsat 8/9 C2 L2 Thermal (operational audit)",
        provider="USGS via Google Earth Engine",
        tier="audit",
        delivery="gee_audit",
        dataset_id=LANDSAT_C2_L2_COLLECTION,
        bands=(LANDSAT_ST_B10_BAND, LANDSAT_QA_PIXEL_BAND),
        units={"thermal_max_c": "°C"},
        fallback_policy="AUDIT_USE_MOCK=true for offline demos; QA_PIXEL cloud/shadow mask required.",
        standards_ref="docs/standards/cement-data-acceptance-and-processing.md",
        loi_status="active",
        connector_module="scripts.landsat_thermal_audit",
        feature_keys=("thermal_max_c",),
    ),
    DataSourceEntry(
        id="audit_s5p_no2",
        name="Sentinel-5P OFFL L3 NO₂ (operational audit)",
        provider="Copernicus via Google Earth Engine",
        tier="audit",
        delivery="gee_audit",
        dataset_id=S5P_L3_NO2_COLLECTION,
        bands=(GEE_S5P_NO2_BAND,),
        units={"no2_mean": "mol/m²"},
        fallback_policy="AUDIT_USE_MOCK=true for offline demos.",
        standards_ref="docs/standards/cement-data-acceptance-and-processing.md",
        loi_status="active",
        connector_module="scripts.s5p_no2_audit",
        feature_keys=("no2_mean",),
    ),
    DataSourceEntry(
        id="audit_s5p_co",
        name="Sentinel-5P OFFL L3 CO (transformer Primary Audit)",
        provider="Copernicus via Google Earth Engine",
        tier="audit",
        delivery="gee_audit",
        dataset_id=S5P_L3_CO_COLLECTION,
        bands=("CO_column_number_density",),
        units={"co_mean": "mol/m²"},
        fallback_policy="AUDIT_USE_MOCK=true for offline demos.",
        standards_ref="docs/standards/transformer-data-acceptance-and-processing.md",
        loi_status="active",
        connector_module="scripts.s5p_co_audit",
        feature_keys=("co_mean",),
    ),
    DataSourceEntry(
        id="audit_viirs_dnb",
        name="VIIRS DNB Monthly VCMSLCFG (transformer Primary Audit)",
        provider="NOAA via Google Earth Engine",
        tier="audit",
        delivery="gee_audit",
        dataset_id=VIIRS_DNB_MONTHLY_COLLECTION,
        bands=(VIIRS_DNB_AVG_RAD_BAND, VIIRS_DNB_CF_CVG_BAND),
        units={"avg_rad": "nW/cm²/sr", "cf_cvg": "cloud-free observation count"},
        fallback_policy="Report cf_cvg alongside avg_rad; low cf_cvg lowers interpretation confidence.",
        standards_ref="docs/standards/transformer-data-acceptance-and-processing.md",
        loi_status="active",
        connector_module="scripts.viirs_ntl_audit",
        feature_keys=("avg_rad", "cf_cvg"),
    ),
    DataSourceEntry(
        id="roadmap_ndvi",
        name="NDVI / Greenness Proxy (agriculture)",
        provider="Landsat L2 SR / MODIS via GEE (planned)",
        tier="roadmap",
        delivery="stub",
        dataset_id=ROADMAP_NDVI_DATASET,
        bands=("NDVI",),
        units={"ndvi_mean": "0-1 index"},
        fallback_policy="Deterministic stub in agriculture_surface until GEE layer wired.",
        standards_ref="docs/turkiye/sector-extensions.md",
        loi_status="planned",
        connector_module="app.scoring.agriculture_surface",
        feature_keys=("ndvi_mean",),
    ),
    DataSourceEntry(
        id="roadmap_soil_moisture",
        name="Soil Moisture Proxy (agriculture)",
        provider="ERA5-Land / SMAP via GEE (planned)",
        tier="roadmap",
        delivery="stub",
        dataset_id=ROADMAP_ERA5_LAND_DATASET,
        bands=("swvl1",),
        units={"soil_moisture_proxy": "0-1 proxy band"},
        fallback_policy="Deterministic stub in agriculture_surface until ERA5-Land wired.",
        standards_ref="docs/turkiye/sector-extensions.md",
        loi_status="planned",
        connector_module="app.scoring.agriculture_surface",
        feature_keys=("soil_moisture_proxy",),
    ),
)


def get_data_source(source_id: str) -> DataSourceEntry | None:
    for entry in DATA_SOURCE_REGISTRY:
        if entry.id == source_id:
            return entry
    return None


def list_data_sources(*, tier: DataSourceTier | None = None) -> list[DataSourceEntry]:
    if tier is None:
        return list(DATA_SOURCE_REGISTRY)
    return [e for e in DATA_SOURCE_REGISTRY if e.tier == tier]

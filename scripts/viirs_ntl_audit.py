"""VIIRS DNB monthly stray-light-corrected average radiance mean over AOI (Earth Engine)."""

from __future__ import annotations

import os
from typing import Any

from app.core.data_source_registry import (
    VIIRS_DNB_AVG_RAD_BAND,
    VIIRS_DNB_CF_CVG_BAND,
    VIIRS_DNB_MONTHLY_COLLECTION,
)

VIIRS_DNB_COLLECTION = VIIRS_DNB_MONTHLY_COLLECTION
VIIRS_AVG_RAD_BAND = VIIRS_DNB_AVG_RAD_BAND
VIIRS_CF_CVG_BAND = VIIRS_DNB_CF_CVG_BAND
VIIRS_REDUCE_SCALE_M = 463.83


def _resolve_gee_project_id() -> str | None:
    return (os.getenv("GEE_PROJECT") or os.getenv("GEE_PROJECT_ID") or "").strip() or None


def fetch_viirs_dnb_avg_rad_mean(
    lat: float | None = None,
    lon: float | None = None,
    *,
    region_geojson: dict | None = None,
    start_date: str,
    end_date: str,
    buffer_m: float = 2000.0,
    scale_m: float = VIIRS_REDUCE_SCALE_M,
) -> dict[str, Any]:
    """Temporal mean of monthly ``avg_rad`` (nW/cm²/sr) over AOI.

    ``end_date`` is exclusive for ``filterDate``. Low ``cf_cvg`` pixels are not masked here;
    see product documentation and ``docs/turkiye/transformers/transformer-audit-methodology.md``.
    """
    if os.getenv("AUDIT_USE_MOCK", "").lower() in {"1", "true", "yes"}:
        return {
            "status": "SUCCESS",
            "ntl_avg_rad": 32.5,
            "ntl_cf_cvg_mean": 11.25,
            "detail": "AUDIT_USE_MOCK",
            "mask_policy": "mock",
        }

    if region_geojson is None and (lat is None or lon is None):
        return {
            "status": "ERROR",
            "ntl_avg_rad": None,
            "ntl_cf_cvg_mean": None,
            "detail": "Provide region_geojson or both lat and lon",
            "mask_policy": "none",
        }

    project_id = _resolve_gee_project_id()
    if not project_id:
        return {
            "status": "ERROR",
            "ntl_avg_rad": None,
            "ntl_cf_cvg_mean": None,
            "detail": "GEE_PROJECT or GEE_PROJECT_ID missing",
            "mask_policy": "none",
        }

    try:
        ee = __import__("ee")
    except ImportError as exc:
        return {
            "status": "ERROR",
            "ntl_avg_rad": None,
            "ntl_cf_cvg_mean": None,
            "detail": f"ee import failed: {exc}",
            "mask_policy": "none",
        }

    try:
        ee.Initialize(project=project_id)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "ntl_avg_rad": None,
            "ntl_cf_cvg_mean": None,
            "detail": str(exc),
            "mask_policy": "none",
        }

    if region_geojson is not None:
        region = ee.Geometry(region_geojson)
    else:
        poi = ee.Geometry.Point([float(lon), float(lat)])
        region = poi.buffer(float(buffer_m))

    col = (
        ee.ImageCollection(VIIRS_DNB_COLLECTION)
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .select([VIIRS_AVG_RAD_BAND, VIIRS_CF_CVG_BAND])
    )

    mean_img = col.mean()

    try:
        stats = mean_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=float(scale_m),
            maxPixels=1e9,
        ).getInfo()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "ntl_avg_rad": None,
            "ntl_cf_cvg_mean": None,
            "detail": str(exc),
            "mask_policy": "none",
        }

    val = stats.get(VIIRS_AVG_RAD_BAND)
    cfv = stats.get(VIIRS_CF_CVG_BAND)
    if val is None:
        return {
            "status": "PARTIAL",
            "ntl_avg_rad": None,
            "ntl_cf_cvg_mean": round(float(cfv), 4) if cfv is not None else None,
            "detail": "avg_rad missing or empty reduceRegion result",
            "mask_policy": "monthly_mean_cf_cvg_reported_unmasked",
        }

    out: dict[str, Any] = {
        "status": "SUCCESS",
        "ntl_avg_rad": round(float(val), 4),
        "ntl_cf_cvg_mean": round(float(cfv), 4) if cfv is not None else None,
        "detail": None,
        "mask_policy": "monthly_mean_cf_cvg_reported_unmasked",
    }
    return out

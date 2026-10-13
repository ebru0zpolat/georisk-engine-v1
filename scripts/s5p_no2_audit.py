"""Sentinel-5P OFFL L3 tropospheric NO₂ column mean over AOI (Earth Engine)."""

from __future__ import annotations

import os
from typing import Any

from app.core.data_source_registry import GEE_S5P_NO2_BAND, S5P_L3_NO2_COLLECTION

S5P_NO2_BAND = GEE_S5P_NO2_BAND
# EE reduceRegion scale hint (~order of product grid); not physical resolution claim.
S5P_REDUCE_SCALE_M = 1113.2


def _resolve_gee_project_id() -> str | None:
    return (os.getenv("GEE_PROJECT") or os.getenv("GEE_PROJECT_ID") or "").strip() or None


def fetch_no2_l3_mean_mol_m2(
    lat: float | None = None,
    lon: float | None = None,
    *,
    region_geojson: dict | None = None,
    start_date: str,
    end_date: str,
    buffer_m: float = 2000.0,
    scale_m: float = S5P_REDUCE_SCALE_M,
) -> dict[str, Any]:
    """Temporal mean of L3 NO₂ (mol/m²) over AOI.

    Either ``region_geojson`` (GeoJSON ``Geometry`` dict) **or** ``lat``/``lon`` with
    ``poi.buffer(buffer_m)`` is required.

    ``end_date`` is exclusive for ``filterDate``. This path uses **L3** composite;
    it does **not** apply L2-style ``qa_value`` filtering — see ``docs/turkiye/cco-audit-methodology.md``.
    """
    if os.getenv("AUDIT_USE_MOCK", "").lower() in {"1", "true", "yes"}:
        return {
            "status": "SUCCESS",
            "no2_mean_mol_m2": 0.00014,
            "detail": "AUDIT_USE_MOCK",
            "mask_policy": "mock",
        }

    if region_geojson is None and (lat is None or lon is None):
        return {
            "status": "ERROR",
            "no2_mean_mol_m2": None,
            "detail": "Provide region_geojson or both lat and lon",
            "mask_policy": "none",
        }

    project_id = _resolve_gee_project_id()
    if not project_id:
        return {
            "status": "ERROR",
            "no2_mean_mol_m2": None,
            "detail": "GEE_PROJECT or GEE_PROJECT_ID missing",
            "mask_policy": "none",
        }

    try:
        ee = __import__("ee")
    except ImportError as exc:
        return {
            "status": "ERROR",
            "no2_mean_mol_m2": None,
            "detail": f"ee import failed: {exc}",
            "mask_policy": "none",
        }

    try:
        ee.Initialize(project=project_id)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "no2_mean_mol_m2": None,
            "detail": str(exc),
            "mask_policy": "none",
        }

    if region_geojson is not None:
        region = ee.Geometry(region_geojson)
    else:
        poi = ee.Geometry.Point([float(lon), float(lat)])
        region = poi.buffer(float(buffer_m))

    col = (
        ee.ImageCollection(S5P_L3_NO2_COLLECTION)
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .select(S5P_NO2_BAND)
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
            "no2_mean_mol_m2": None,
            "detail": str(exc),
            "mask_policy": "none",
        }

    val = stats.get(S5P_NO2_BAND)
    if val is None:
        return {
            "status": "PARTIAL",
            "no2_mean_mol_m2": None,
            "detail": "NO2 band missing or empty reduceRegion result",
            "mask_policy": "none",
        }

    return {
        "status": "SUCCESS",
        "no2_mean_mol_m2": round(float(val), 6),
        "detail": None,
        "mask_policy": "l3_mean_no_per_pixel_qa_value",
    }

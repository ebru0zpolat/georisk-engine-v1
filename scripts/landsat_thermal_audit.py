"""Landsat Collection 2 Level-2 thermal extraction for operational audit (QA_PIXEL mask).

Requires authenticated Earth Engine and ``GEE_PROJECT`` or ``GEE_PROJECT_ID``.
Set ``AUDIT_USE_MOCK=true`` for offline demos without RPC.
"""

from __future__ import annotations

import os
from typing import Any

from app.core.data_source_registry import LANDSAT_QA_PIXEL_BAND, LANDSAT_ST_B10_BAND

ST_B10_MULTIPLIER = 0.00341802
ST_B10_OFFSET = 149.0


def _resolve_gee_project_id() -> str | None:
    return (os.getenv("GEE_PROJECT") or os.getenv("GEE_PROJECT_ID") or "").strip() or None


def _qa_pixel_mask_sr(image: Any) -> Any:
    """Cloud / shadow / dilated cloud mask for Landsat C2 L2 QA_PIXEL."""
    ee = __import__("ee")
    qa = image.select("QA_PIXEL")
    dilated_cloud = 1 << 1
    cloud = 1 << 3
    cloud_shadow = 1 << 4
    mask = (
        qa.bitwiseAnd(dilated_cloud)
        .eq(0)
        .And(qa.bitwiseAnd(cloud).eq(0))
        .And(qa.bitwiseAnd(cloud_shadow).eq(0))
    )
    return image.updateMask(mask)


def fetch_operational_thermal_metrics(
    lat: float,
    lon: float,
    *,
    start_date: str,
    end_date: str,
    buffer_m: float = 500.0,
    scale_m: float = 30.0,
) -> dict[str, Any]:
    """Return max masked ST_B10 as Celsius and a scene/composite label.

    ``end_date`` is passed to EE ``filterDate`` as exclusive upper bound (caller may pass +1 day).
    """
    if os.getenv("AUDIT_USE_MOCK", "").lower() in {"1", "true", "yes"}:
        return {
            "status": "SUCCESS",
            "celsius": 35.2,
            "img_id": "LC08_L2SP_MOCK_EXAMPLE",
            "detail": "AUDIT_USE_MOCK",
            "mask_policy": "mock",
        }

    project_id = _resolve_gee_project_id()
    if not project_id:
        return {
            "status": "ERROR",
            "celsius": None,
            "img_id": None,
            "detail": "GEE_PROJECT or GEE_PROJECT_ID missing",
            "mask_policy": "none",
        }

    try:
        ee = __import__("ee")
    except ImportError as exc:
        return {
            "status": "ERROR",
            "celsius": None,
            "img_id": None,
            "detail": f"ee import failed: {exc}",
            "mask_policy": "none",
        }

    try:
        ee.Initialize(project=project_id)
    except Exception as exc:  # noqa: BLE001 — EE surfaces many error types
        return {
            "status": "ERROR",
            "celsius": None,
            "img_id": None,
            "detail": str(exc),
            "mask_policy": "qa_pixel",
        }

    poi = ee.Geometry.Point([float(lon), float(lat)])
    region = poi.buffer(float(buffer_m))

    def prep(img: Any) -> Any:
        return _qa_pixel_mask_sr(img).select("ST_B10")

    lc08 = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .map(prep)
    )
    lc09 = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .map(prep)
    )
    merged = lc08.merge(lc09)
    composite = merged.median()
    thermal_k = composite.multiply(ST_B10_MULTIPLIER).add(ST_B10_OFFSET)

    try:
        stats = thermal_k.reduceRegion(
            reducer=ee.Reducer.max(),
            geometry=region,
            scale=float(scale_m),
            maxPixels=1e9,
        ).getInfo()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "celsius": None,
            "img_id": None,
            "detail": str(exc),
            "mask_policy": "qa_pixel",
        }

    kelvin = stats.get("ST_B10")
    if kelvin is None:
        return {
            "status": "PARTIAL",
            "celsius": None,
            "img_id": f"median_composite_{start_date}_{end_date}",
            "detail": "No valid ST_B10 after mask/composite in AOI",
            "mask_policy": "qa_pixel",
        }

    celsius = float(kelvin) - 273.15
    img_id = f"median_composite_LC08_LC09_{start_date}_{end_date}"
    return {
        "status": "SUCCESS",
        "celsius": round(celsius, 2),
        "img_id": img_id,
        "detail": None,
        "mask_policy": "qa_pixel",
    }

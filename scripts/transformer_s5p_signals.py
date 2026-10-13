"""NO₂ / CO / VIIRS bundle with industrial **ring** background for Primary Audit (transformers)."""

from __future__ import annotations

import os
from typing import Any

from scripts.landsat_thermal_audit import fetch_operational_thermal_metrics
from scripts.s5p_co_audit import fetch_co_l3_mean_mol_m2
from scripts.s5p_no2_audit import fetch_no2_l3_mean_mol_m2
from scripts.transformer_facilities import centroid_lat_lon
from scripts.viirs_ntl_audit import fetch_viirs_dnb_avg_rad_mean


def _ring_geojson_dict(facility_geometry: dict, *, ring_buffer_m: float) -> dict[str, Any] | None:
    """Return GeoJSON geometry dict for ``site.buffer(ring_buffer_m).difference(site)``."""
    try:
        ee = __import__("ee")
    except ImportError:
        return None
    project_id = (os.getenv("GEE_PROJECT") or os.getenv("GEE_PROJECT_ID") or "").strip()
    if not project_id:
        return None
    ee.Initialize(project=project_id)
    site = ee.Geometry(facility_geometry)
    ring = site.buffer(float(ring_buffer_m)).difference(site)
    info = ring.getInfo()
    if isinstance(info, dict) and info.get("type"):
        return info
    return None


def _num_or_none(val: Any) -> float | None:
    if isinstance(val, (int, float)):
        return float(val)
    return None


def fetch_primary_audit_signals(
    facility_geometry: dict[str, Any],
    *,
    start_date: str,
    end_date: str,
    ring_buffer_m: float = 8000.0,
    thermal_buffer_m: float = 650.0,
) -> dict[str, Any]:
    """Fetch NO₂, CO, VIIRS means on facility AOI and on surrounding ring; optional Landsat thermal.

    Ring = ``site.buffer(ring_buffer_m).difference(site)`` to approximate OSB **background**
    noise (not source apportionment). Residuals are simple AOI − ring differences.
    """
    if os.getenv("AUDIT_USE_MOCK", "").lower() in {"1", "true", "yes"}:
        lat, lon = centroid_lat_lon(facility_geometry)
        therm = fetch_operational_thermal_metrics(
            lat,
            lon,
            start_date=start_date,
            end_date=end_date,
            buffer_m=thermal_buffer_m,
        )
        return {
            "status": "SUCCESS",
            "detail": "AUDIT_USE_MOCK",
            "no2_aoi_status": "SUCCESS",
            "no2_ring_status": "SUCCESS",
            "no2_aoi_mol_m2": 0.00012,
            "no2_ring_mol_m2": 0.00007,
            "no2_residual_mol_m2": 0.00005,
            "co_aoi_status": "SUCCESS",
            "co_ring_status": "SUCCESS",
            "co_aoi_mol_m2": 0.000028,
            "co_ring_mol_m2": 0.000015,
            "co_residual_mol_m2": 0.000013,
            "ntl_aoi_status": "SUCCESS",
            "ntl_ring_status": "SUCCESS",
            "ntl_aoi_avg_rad": 36.2,
            "ntl_ring_avg_rad": 19.4,
            "ntl_residual_avg_rad": 16.8,
            "ntl_cf_cvg_aoi_mean": 10.5,
            "ntl_cf_cvg_ring_mean": 8.1,
            "thermal_status": therm.get("status"),
            "thermal_celsius": therm.get("celsius"),
            "thermal_img_id": therm.get("img_id"),
            "ring_buffer_m": float(ring_buffer_m),
            "mask_policy": "mock",
        }

    ring_geo = _ring_geojson_dict(facility_geometry, ring_buffer_m=ring_buffer_m)
    if ring_geo is None:
        return {
            "status": "ERROR",
            "detail": "Could not build ring geometry (GEE_PROJECT missing or ee import failed)",
        }

    no2_aoi = fetch_no2_l3_mean_mol_m2(
        region_geojson=facility_geometry,
        start_date=start_date,
        end_date=end_date,
    )
    no2_ring = fetch_no2_l3_mean_mol_m2(
        region_geojson=ring_geo,
        start_date=start_date,
        end_date=end_date,
    )
    co_aoi = fetch_co_l3_mean_mol_m2(
        region_geojson=facility_geometry,
        start_date=start_date,
        end_date=end_date,
    )
    co_ring = fetch_co_l3_mean_mol_m2(
        region_geojson=ring_geo,
        start_date=start_date,
        end_date=end_date,
    )
    ntl_aoi = fetch_viirs_dnb_avg_rad_mean(
        region_geojson=facility_geometry,
        start_date=start_date,
        end_date=end_date,
    )
    ntl_ring = fetch_viirs_dnb_avg_rad_mean(
        region_geojson=ring_geo,
        start_date=start_date,
        end_date=end_date,
    )

    lat, lon = centroid_lat_lon(facility_geometry)
    therm = fetch_operational_thermal_metrics(
        lat,
        lon,
        start_date=start_date,
        end_date=end_date,
        buffer_m=thermal_buffer_m,
    )

    n2a = _num_or_none(no2_aoi.get("no2_mean_mol_m2"))
    n2r = _num_or_none(no2_ring.get("no2_mean_mol_m2"))
    coa = _num_or_none(co_aoi.get("co_mean_mol_m2"))
    cor = _num_or_none(co_ring.get("co_mean_mol_m2"))
    na = _num_or_none(ntl_aoi.get("ntl_avg_rad"))
    nr = _num_or_none(ntl_ring.get("ntl_avg_rad"))
    cfa = _num_or_none(ntl_aoi.get("ntl_cf_cvg_mean"))
    cfr = _num_or_none(ntl_ring.get("ntl_cf_cvg_mean"))

    out: dict[str, Any] = {
        "no2_aoi_status": no2_aoi.get("status"),
        "no2_ring_status": no2_ring.get("status"),
        "no2_aoi_mol_m2": n2a,
        "no2_ring_mol_m2": n2r,
        "no2_residual_mol_m2": (n2a - n2r) if n2a is not None and n2r is not None else None,
        "co_aoi_status": co_aoi.get("status"),
        "co_ring_status": co_ring.get("status"),
        "co_aoi_mol_m2": coa,
        "co_ring_mol_m2": cor,
        "co_residual_mol_m2": (coa - cor) if coa is not None and cor is not None else None,
        "ntl_aoi_status": ntl_aoi.get("status"),
        "ntl_ring_status": ntl_ring.get("status"),
        "ntl_aoi_avg_rad": na,
        "ntl_ring_avg_rad": nr,
        "ntl_residual_avg_rad": (na - nr) if na is not None and nr is not None else None,
        "ntl_cf_cvg_aoi_mean": cfa,
        "ntl_cf_cvg_ring_mean": cfr,
        "thermal_status": therm.get("status"),
        "thermal_celsius": therm.get("celsius"),
        "thermal_img_id": therm.get("img_id"),
        "ring_buffer_m": float(ring_buffer_m),
        "mask_policy": "l3_no2_co_monthly_viirs_dnb_ring_residual",
    }

    statuses = [
        str(no2_aoi.get("status")),
        str(no2_ring.get("status")),
        str(co_aoi.get("status")),
        str(co_ring.get("status")),
        str(ntl_aoi.get("status")),
        str(ntl_ring.get("status")),
    ]
    if any(s not in {"SUCCESS", "PARTIAL"} for s in statuses):
        out["status"] = "ERROR"
        out["detail"] = "One or more satellite reductions failed"
    elif "PARTIAL" in statuses:
        out["status"] = "PARTIAL"
        out["detail"] = "Partial satellite coverage or empty band in AOI/ring"
    else:
        out["status"] = "SUCCESS"
        out["detail"] = None

    return out

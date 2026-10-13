"""Build ``IndustrialVerificationRef`` for risk API (nearest Primary Audit AOI, static pipeline catalog)."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.schemas.industrial_verification import (
    IndustrialVerificationRef,
    NearestPrimaryAudit,
    PipelineRef,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FACILITIES_GEOJSON = (
    _REPO_ROOT / "docs" / "turkiye" / "transformers" / "primary_audit_facilities.geojson"
)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlamb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlamb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _polygon_centroid(coords: list[list[float]]) -> tuple[float, float] | None:
    if not coords or not coords[0]:
        return None
    ring = coords[0]
    lons = [p[0] for p in ring if len(p) >= 2]
    lats = [p[1] for p in ring if len(p) >= 2]
    if not lons:
        return None
    return sum(lats) / len(lats), sum(lons) / len(lons)


@lru_cache(maxsize=1)
def _facility_centroids() -> list[tuple[str, str, float, float]]:
    out: list[tuple[str, str, float, float]] = []
    if not _FACILITIES_GEOJSON.is_file():
        return out
    try:
        raw = json.loads(_FACILITIES_GEOJSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    for feat in raw.get("features") or []:
        if feat.get("type") != "Feature":
            continue
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Polygon":
            continue
        cid = str(props.get("id") or "").strip()
        name = str(props.get("name_tr") or cid)
        coords = geom.get("coordinates")
        if not isinstance(coords, list):
            continue
        c = _polygon_centroid(coords)
        if c is None:
            continue
        lat, lon = c
        out.append((cid, name, float(lat), float(lon)))
    return out


def _nearest_primary_audit(lat: float, lon: float, max_km: float) -> NearestPrimaryAudit | None:
    best: tuple[str, str, float] | None = None
    for fid, name, flat, flon in _facility_centroids():
        d = _haversine_km(lat, lon, flat, flon)
        if d <= max_km and (best is None or d < best[2]):
            best = (fid, name, d)
    if best is None:
        return None
    return NearestPrimaryAudit(
        facility_id=best[0],
        facility_name_tr=best[1],
        distance_km=round(best[2], 2),
    )


def _static_pipelines() -> list[PipelineRef]:
    return [
        PipelineRef(
            id="cement_operational_audit",
            label_tr="Çimento — termal + NO₂ mühürlü operasyonel doğrulama",
            methodology_doc="docs/turkiye/cco-audit-methodology.md",
            production_entrypoint="scripts/run_integrated_audit.py",
        ),
        PipelineRef(
            id="transformer_primary_audit",
            label_tr="Trafo — emisyon + VIIRS Primary Audit (ESG Watch)",
            methodology_doc="docs/turkiye/transformers/transformer-audit-methodology.md",
            production_entrypoint="scripts/transformer_audit.py",
        ),
    ]


def build_industrial_verification_ref(
    *,
    audit_id: str,
    latitude: float,
    longitude: float,
    max_match_km: float | None = None,
) -> IndustrialVerificationRef:
    cap = float(max_match_km) if max_match_km is not None else settings.industrial_verification_max_match_km
    nearest = _nearest_primary_audit(latitude, longitude, cap)
    return IndustrialVerificationRef(
        linked_audit_id=audit_id,
        risk_model_version=settings.risk_score_model_version,
        nearest_primary_audit=nearest,
        pipelines=_static_pipelines(),
    )

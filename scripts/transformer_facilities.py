"""Load Primary Audit facility AOIs (GeoJSON) for transformer / ESG Watch pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_GEOJSON = (
    _REPO_ROOT / "docs" / "turkiye" / "transformers" / "primary_audit_facilities.geojson"
)


def _ring_centroid_coords(ring: list[list[float]]) -> tuple[float, float]:
    """Simple mean of exterior ring vertices (closed ring repeats first point)."""
    if not ring:
        return 0.0, 0.0
    lons = [p[0] for p in ring if len(p) >= 2]
    lats = [p[1] for p in ring if len(p) >= 2]
    if not lons:
        return 0.0, 0.0
    return sum(lats) / len(lats), sum(lons) / len(lons)


def centroid_lat_lon(geometry: dict[str, Any]) -> tuple[float, float]:
    """Approximate (lat, lon) for Point or Polygon first ring."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Point" and isinstance(coords, list) and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    if gtype == "Polygon" and isinstance(coords, list) and coords:
        return _ring_centroid_coords(coords[0])
    return 0.0, 0.0


def load_primary_audit_facilities(path: Path | None = None) -> list[dict[str, Any]]:
    """Return facility dicts: ``id``, ``name_tr``, ``audit_tier``, ``geometry``, ``notes_tr``."""
    p = path or _DEFAULT_GEOJSON
    raw = json.loads(p.read_text(encoding="utf-8"))
    feats = raw.get("features") or []
    out: list[dict[str, Any]] = []
    for feat in feats:
        if feat.get("type") != "Feature":
            continue
        props = feat.get("properties") or {}
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        fid = str(props.get("id") or "").strip()
        if not fid:
            continue
        out.append(
            {
                "id": fid,
                "name_tr": str(props.get("name_tr") or fid),
                "audit_tier": str(props.get("audit_tier") or "Primary"),
                "notes_tr": str(props.get("notes_tr") or ""),
                "geometry": geom,
            }
        )
    return out


def facility_by_id(facility_id: str, path: Path | None = None) -> dict[str, Any] | None:
    fid = facility_id.strip().lower()
    for f in load_primary_audit_facilities(path):
        if f["id"].lower() == fid:
            return f
    return None

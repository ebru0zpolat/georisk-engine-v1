"""Multi-point feature fetch with spatial-cell coalesce (Sprint 4 → live bulk).

Points that fall in the same ``cell_deg`` grid cell share one ORAS5 + one GEE
fetch (``coalesce_mode=spatial_cell_coalesce``). Isolated cells still use a
single fetch tagged ``spatial_cell_singleton``.

Cell representatives are resolved through the connectors' bulk APIs:

- ORAS5: one vectorized nearest-neighbor ``ds.sel`` over the Zarr store for
  every cell at once (``CDSOras5Connector.fetch_features_many``).
- GEE: one ``reduceRegions`` RPC per band/window covering every cell
  (``GeeConnector.fetch_baseline_features_many``).

The two data planes run in parallel. Both connectors keep their deterministic
fallbacks when credentials are absent, so CI stays offline-safe.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.connectors.cds_oras5 import (
    ORAS5_UNSCORABLE_MESSAGE,
    CDSOras5Connector,
    Oras5PointRequest,
)
from app.connectors.gee import GeeConnector, GeePointRequest
from app.core import error_codes as codes


@dataclass(frozen=True)
class BulkAssetPoint:
    asset_id: str
    latitude: float
    longitude: float
    radius_km: float = 10.0


@dataclass(frozen=True)
class BulkFeatureRow:
    asset_id: str
    oras5_features: dict[str, float]
    gee_bundle: dict[str, Any]
    coalesce_mode: str = "spatial_cell_coalesce"
    cell_id: str | None = None
    #: Per-point ORAS5 failure (e.g. unscorable series at this cell). When set,
    #: ``oras5_features`` is empty and the row must not be scored — the batch
    #: pipeline turns it into a failed row instead of aborting the request.
    error: dict[str, Any] | None = None


def _cell_key(lat: float, lon: float, *, cell_deg: float) -> tuple[int, int]:
    return (int(lat // cell_deg), int(lon // cell_deg))


def _cell_id(key: tuple[int, int], *, cell_deg: float) -> str:
    return f"cell_{cell_deg:g}_{key[0]}_{key[1]}"


def fetch_features_many(
    points: list[BulkAssetPoint],
    *,
    oras5: CDSOras5Connector | None = None,
    gee: GeeConnector | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    baseline_start_date: date | None = None,
    baseline_end_date: date | None = None,
    cell_deg: float = 0.5,
    max_workers: int = 8,
) -> list[BulkFeatureRow]:
    """Fetch ORAS5 + GEE features with spatial-cell coalesce and bulk connector calls."""
    del max_workers  # kept for call-site compatibility; bulk paths replace per-cell workers
    if not points:
        return []

    oras5_c = oras5 or CDSOras5Connector()
    gee_c = gee or GeeConnector()

    groups: dict[tuple[int, int], list[BulkAssetPoint]] = {}
    for p in points:
        groups.setdefault(_cell_key(p.latitude, p.longitude, cell_deg=cell_deg), []).append(p)

    # Representative = cell centroid of member coords (stable, not first-id biased).
    cell_keys = list(groups.keys())
    representatives: list[BulkAssetPoint] = []
    for key in cell_keys:
        members = groups[key]
        lat = sum(m.latitude for m in members) / len(members)
        lon = sum(m.longitude for m in members) / len(members)
        radius = max(m.radius_km for m in members)
        representatives.append(
            BulkAssetPoint(asset_id=f"cell:{key}", latitude=lat, longitude=lon, radius_km=radius)
        )

    oras5_payloads = [
        Oras5PointRequest(
            latitude=rep.latitude,
            longitude=rep.longitude,
            start_date=start_date,
            end_date=end_date,
        )
        for rep in representatives
    ]
    gee_payloads = [
        GeePointRequest(
            latitude=rep.latitude,
            longitude=rep.longitude,
            radius_km=rep.radius_km,
            start_date=start_date,
            end_date=end_date,
            baseline_start_date=baseline_start_date,
            baseline_end_date=baseline_end_date,
        )
        for rep in representatives
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        oras5_future = pool.submit(oras5_c.fetch_features_many, oras5_payloads)
        gee_future = pool.submit(gee_c.fetch_baseline_features_many, gee_payloads)
        oras5_results = oras5_future.result()
        gee_bundles = gee_future.result()

    cell_payload: dict[
        tuple[int, int], tuple[dict[str, float] | None, dict[str, Any]]
    ] = {key: (oras5_results[i], gee_bundles[i]) for i, key in enumerate(cell_keys)}

    rows: list[BulkFeatureRow] = []
    for p in points:
        key = _cell_key(p.latitude, p.longitude, cell_deg=cell_deg)
        oras5_features, gee_bundle = cell_payload[key]
        members = groups[key]
        mode = "spatial_cell_coalesce" if len(members) > 1 else "spatial_cell_singleton"
        rows.append(
            BulkFeatureRow(
                asset_id=p.asset_id,
                oras5_features=oras5_features if oras5_features is not None else {},
                gee_bundle=gee_bundle,
                coalesce_mode=mode,
                cell_id=_cell_id(key, cell_deg=cell_deg),
                error=(
                    {
                        "code": codes.ORAS5_SERIES_UNSCORABLE,
                        "message": ORAS5_UNSCORABLE_MESSAGE,
                    }
                    if oras5_features is None
                    else None
                ),
            )
        )
    return rows


__all__ = ["BulkAssetPoint", "BulkFeatureRow", "fetch_features_many"]

"""Sprint 4 — bulk feature fetch with spatial-cell coalesce."""

from __future__ import annotations

from app.connectors.bulk_fetch import BulkAssetPoint, fetch_features_many


def test_fetch_features_many_returns_one_row_per_point() -> None:
    points = [
        BulkAssetPoint(asset_id="A", latitude=41.0, longitude=29.0),
        BulkAssetPoint(asset_id="B", latitude=39.9, longitude=32.8, radius_km=12),
    ]
    rows = fetch_features_many(points)
    assert len(rows) == 2
    assert {r.asset_id for r in rows} == {"A", "B"}
    for r in rows:
        assert r.coalesce_mode in {"spatial_cell_coalesce", "spatial_cell_singleton"}
        assert r.cell_id is not None
        assert "sst_anomaly_zscore" in r.oras5_features or "sea_level_trend_mm_per_year" in r.oras5_features
        assert "current" in r.gee_bundle and "baseline" in r.gee_bundle


def test_fetch_features_many_coalesces_nearby_points() -> None:
    """Two points in the same 0.5° cell share one fetch (same coalesce cell_id)."""
    points = [
        BulkAssetPoint(asset_id="C1", latitude=41.01, longitude=29.01),
        BulkAssetPoint(asset_id="C2", latitude=41.02, longitude=29.02),
    ]
    rows = fetch_features_many(points, cell_deg=0.5)
    assert len(rows) == 2
    assert rows[0].cell_id == rows[1].cell_id
    assert rows[0].coalesce_mode == "spatial_cell_coalesce"
    assert rows[1].coalesce_mode == "spatial_cell_coalesce"
    # Shared cell → identical connector payloads
    assert rows[0].oras5_features == rows[1].oras5_features


def test_fetch_features_many_empty() -> None:
    assert fetch_features_many([]) == []

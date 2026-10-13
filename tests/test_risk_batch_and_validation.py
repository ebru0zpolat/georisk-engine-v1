"""Risk batch endpoint, partial success rows, dual-publish score fields, error envelope."""

from __future__ import annotations

import time

from starlette.testclient import TestClient

from app.main import app
from app.services.async_batch_poc import async_batch_task_store


def test_post_score_unknown_preset_envelope() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/risk/score",
        json={
            "asset_name": "X",
            "latitude": 41.0,
            "longitude": 29.0,
            "radius_km": 10,
            "sector": "industrial",
            "preset_id": "not_a_real_preset",
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "PRESET_NOT_FOUND"
    assert "details" in body["error"]


def test_post_score_dual_publish_fields() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/risk/score",
        json={
            "asset_name": "Dual",
            "latitude": 41.02,
            "longitude": 29.01,
            "preset_id": "industrial_v1",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "overall_score" in data
    assert "components" in data
    assert 0.0 <= data["risk_score"] <= 1.0
    assert set(data["scores"]) == {"heat", "water_stress", "climate"}
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["preset_id"] == "industrial_v1"
    assert "updated_at" in data["meta"]
    assert data["location"]["lat"] == data["latitude"]
    assert data["location"]["lon"] == data["longitude"]
    assert data["data_mode"] == "stub"
    assert data["production_eligible"] is False


def test_batch_score_success() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/risk/batch",
        json={
            "preset_id": "industrial_v1",
            "sector": "industrial",
            "assets": [
                {"id": "TR-001", "lat": 41.02, "lon": 29.01},
                {"id": "TR-002", "lat": 39.93, "lon": 32.85},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["preset_id"] == "industrial_v1"
    assert data["summary"]["total_assets"] == 2
    assert data["summary"]["success_count"] == 2
    assert data["summary"]["failed_count"] == 0
    assert data["summary"]["avg_risk"] is not None
    assert len(data["results"]) == 2
    for row in data["results"]:
        assert row["success"] is True
        assert row["error"] is None
        assert row["risk"] is not None
        assert row["risk_score"] is not None
    assert {row["id"] for row in data["results"]} == {"TR-001", "TR-002"}


def test_batch_uses_bulk_prefetch_data_version() -> None:
    """Batch path stamps meta via prefetched features (single-asset score still omits +bulk)."""
    from app.schemas.risk import RiskBatchAsset, RiskBatchRequest
    from app.services.risk_service import RiskService

    svc = RiskService()
    result = svc.batch_score(
        RiskBatchRequest(
            preset_id="industrial_v1",
            assets=[RiskBatchAsset(id="P1", lat=41.0, lon=29.0)],
        )
    )
    assert result.summary.success_count == 1
    # Prefetch stamp is on the underlying RiskScoreResponse; batch row keeps risk only.
    # Re-score with prefetch to assert the wire path.
    from app.connectors.bulk_fetch import BulkAssetPoint, fetch_features_many
    from app.schemas.risk import RiskScoreRequest

    rows = fetch_features_many([BulkAssetPoint(asset_id="P1", latitude=41.0, longitude=29.0)])
    scored = svc.score(
        RiskScoreRequest(asset_name="P1", latitude=41.0, longitude=29.0),
        prefetched=rows[0],
    )
    assert scored.meta.data_version is not None
    assert "bulk:spatial_cell_" in scored.meta.data_version


def test_batch_partial_success_invalid_coordinates_row() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/risk/batch",
        json={
            "preset_id": "transformer_v1",
            "sector": "industrial",
            "assets": [
                {"id": "GOOD", "lat": 41.02, "lon": 29.01},
                {"id": "BAD", "lat": 91.0, "lon": 0.0},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total_assets"] == 2
    assert data["summary"]["success_count"] == 1
    assert data["summary"]["failed_count"] == 1
    by_id = {row["id"]: row for row in data["results"]}
    assert by_id["GOOD"]["success"] is True
    assert by_id["BAD"]["success"] is False
    assert by_id["BAD"]["error"]["code"] == "INVALID_COORDINATES"


def test_batch_empty_assets_envelope() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/risk/batch",
        json={"preset_id": "industrial_v1", "assets": []},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "INVALID_BATCH"
    assert "details" in body["error"]


def test_async_batch_poc_completes() -> None:
    async_batch_task_store.clear_for_tests()
    client = TestClient(app)
    r = client.post(
        "/v1/risk/batch/async",
        json={
            "preset_id": "industrial_v1",
            "assets": [{"id": "A1", "lat": 41.0, "lon": 29.0}],
        },
    )
    assert r.status_code == 202
    task_id = r.json()["task_id"]
    status_path = r.json()["status_path"]
    assert status_path.endswith(task_id)

    deadline = time.time() + 30
    body = None
    while time.time() < deadline:
        s = client.get(f"/v1/risk/batch/status/{task_id}")
        assert s.status_code == 200
        body = s.json()
        if body["status"] in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.05)

    assert body is not None
    assert body["status"] == "COMPLETED"
    assert body["result"] is not None
    assert body["result"]["summary"]["success_count"] == 1


def test_async_batch_unknown_task_not_found() -> None:
    client = TestClient(app)
    r = client.get("/v1/risk/batch/status/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_get_score_success() -> None:
    client = TestClient(app)
    r = client.get(
        "/v1/risk/score",
        params={"lat": 41.02, "lon": 29.01, "preset_id": "industrial_v1", "asset_name": "GET-1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["asset_name"] == "GET-1"
    assert "risk_score" in data
    assert data["preset_id"] == "industrial_v1"


def test_get_score_unknown_preset_envelope() -> None:
    client = TestClient(app)
    r = client.get(
        "/v1/risk/score",
        params={"lat": 41.0, "lon": 29.0, "preset_id": "not_real"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PRESET_NOT_FOUND"


def test_demo_iron_steel_run() -> None:
    client = TestClient(app)
    r = client.get("/v1/demo/run?asset_id=marmara_integrated_steel_mill")
    assert r.status_code == 200
    data = r.json()
    assert data["asset"]["sector"] == "iron_steel"

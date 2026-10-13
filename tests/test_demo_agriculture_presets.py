"""Demo presets for agriculture sector."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.core.sector_registry import AGRICULTURE_SECTOR_ID
from app.main import app


def test_demo_assets_include_agriculture_presets() -> None:
    client = TestClient(app)
    r = client.get("/v1/demo/assets")
    assert r.status_code == 200
    data = r.json()
    ids = {a["id"] for a in data}
    assert "anatolia_large_scale_crop" in ids
    assert "thrace_grain_storage_processing" in ids
    ag = [a for a in data if a["sector"] == AGRICULTURE_SECTOR_ID]
    assert len(ag) == 2


def test_demo_run_anatolia_crop() -> None:
    client = TestClient(app)
    r = client.get("/v1/demo/run?asset_id=anatolia_large_scale_crop")
    assert r.status_code == 200
    body = r.json()
    assert body["asset"]["sector"] == AGRICULTURE_SECTOR_ID
    assert "components" in body

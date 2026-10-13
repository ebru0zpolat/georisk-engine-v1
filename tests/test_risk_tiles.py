"""Sprint 5 — blueprint PNG tile endpoint."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.services.risk_tiles import render_tile_png, tile_bounds_lonlat


def test_render_tile_png_nonempty_for_marmara() -> None:
    # z=6 tile covering NW Turkey roughly
    png = render_tile_png("total_risk", 6, 37, 23)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 200


def test_tile_bounds_sane() -> None:
    west, south, east, north = tile_bounds_lonlat(0, 0, 0)
    assert west == -180.0
    assert east == 180.0  # single world tile at z=0
    assert south < north


def test_tiles_http_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/v1/tiles/total_risk/6/37/23.png")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert r.headers.get("X-GeoRisk-Tile-Pilot") == "marmara-v1"


def test_tiles_unknown_layer_404() -> None:
    client = TestClient(app)
    r = client.get("/v1/tiles/not_a_layer/6/37/23.png")
    assert r.status_code == 404

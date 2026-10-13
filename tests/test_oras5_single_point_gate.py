"""Single-point ORAS5 fail-closed scoring gate (P0).

A configured live read whose series is unscorable (land-masked, outside store
coverage, or shorter than the 24-month feature minimum) must raise
``ORAS5_SERIES_UNSCORABLE`` (503) at every runtime scoring surface — the direct
``/v1/oras5/features`` endpoint and ``/v1/risk/score`` — and must never leak a
silent all-zero feature dict that looks like a valid low score. Zero features
remain reachable only through the explicitly-labelled diagnostic helper
(``production_eligible=false``) and the unconfigured stub path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from starlette.testclient import TestClient

from app.connectors.cds_oras5 import CDSOras5Connector, Oras5PointRequest
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.main import app


def _store(times: pd.DatetimeIndex) -> xr.Dataset:
    lats = np.arange(38.0, 43.0, 0.5)
    lons = np.arange(26.0, 34.0, 0.5)
    t = np.arange(len(times), dtype=float)
    sst = (
        (15.0 + 0.05 * t)[:, None, None]
        + 0.1 * lats[None, :, None]
        + 0.05 * lons[None, None, :]
    )
    zos = (0.001 * t)[:, None, None] + np.zeros((len(times), len(lats), len(lons)))
    return xr.Dataset(
        {
            "sst": (("time", "latitude", "longitude"), sst),
            "zos": (("time", "latitude", "longitude"), zos),
        },
        coords={"time": times, "latitude": lats, "longitude": lons},
    )


def _configure_live(
    monkeypatch: pytest.MonkeyPatch,
    ds: xr.Dataset,
    *,
    url: str = "memory://single-gate",
) -> None:
    monkeypatch.setattr(settings, "oras5_zarr_url", url)
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", None)
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda _u: ds))


def _land_masked_store() -> xr.Dataset:
    ds = _store(pd.date_range("1995-01-01", periods=120, freq="MS"))
    # Nearest grid point to (40.0, 30.0) = lat index 4 (40.0), lon index 8 (30.0).
    ds["sst"][:, 4, 8] = np.nan
    ds["zos"][:, 4, 8] = np.nan
    return ds


def test_single_land_masked_series_raises_typed_503(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_live(monkeypatch, _land_masked_store())

    with pytest.raises(GeoRiskApiError) as exc:
        CDSOras5Connector().fetch_features(Oras5PointRequest(latitude=40.0, longitude=30.0))
    assert exc.value.code == "ORAS5_SERIES_UNSCORABLE"
    assert exc.value.status_code == 503
    assert "land-masked" in exc.value.message


def test_single_short_series_raises_typed_503(monkeypatch: pytest.MonkeyPatch) -> None:
    # 12 observations < the 24-month feature minimum.
    _configure_live(monkeypatch, _store(pd.date_range("2013-01-01", periods=12, freq="MS")))

    with pytest.raises(GeoRiskApiError) as exc:
        CDSOras5Connector().fetch_features(Oras5PointRequest(latitude=41.0, longitude=29.0))
    assert exc.value.code == "ORAS5_SERIES_UNSCORABLE"
    assert exc.value.status_code == 503


def test_oras5_features_endpoint_returns_no_numeric_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_live(monkeypatch, _land_masked_store())
    client = TestClient(app)

    r = client.get("/v1/oras5/features", params={"latitude": 40.0, "longitude": 30.0})

    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "ORAS5_SERIES_UNSCORABLE"
    for key in (
        "sst_trend_c_per_decade",
        "sst_anomaly_zscore",
        "sea_level_trend_mm_per_year",
        "ocean_variability_index",
    ):
        assert key not in body


def test_risk_score_endpoint_returns_no_overall_or_ocean_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_live(monkeypatch, _land_masked_store())
    client = TestClient(app)

    r = client.post(
        "/v1/risk/score",
        json={
            "asset_name": "LAND",
            "latitude": 40.0,
            "longitude": 30.0,
            "preset_id": "industrial_v1",
            "sector": "industrial",
        },
    )

    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "ORAS5_SERIES_UNSCORABLE"
    assert "overall_score" not in body
    assert "risk_band" not in body
    assert "ocean_features" not in body
    assert "ocean" not in body.get("components", {})


def test_diagnostic_features_marks_production_ineligible() -> None:
    """Zero features remain reachable only via the labelled diagnostic helper."""
    empty = pd.Series(dtype=float)
    diag = CDSOras5Connector.diagnostic_features_from_series(empty, empty)
    assert diag["production_eligible"] is False
    assert diag["features"] == {
        "sst_trend_c_per_decade": 0.0,
        "sst_anomaly_zscore": 0.0,
        "sea_level_trend_mm_per_year": 0.0,
        "ocean_variability_index": 0.0,
    }

    index = pd.date_range("1995-01-01", periods=36, freq="MS")
    ok = CDSOras5Connector.diagnostic_features_from_series(
        pd.Series(15.0 + 0.05 * np.arange(36), index=index),
        pd.Series(0.001 * np.arange(36), index=index),
    )
    assert ok["production_eligible"] is True
    assert ok["features"]["sst_trend_c_per_decade"] > 0

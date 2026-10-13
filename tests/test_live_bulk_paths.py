"""Live bulk data-plane paths exercised against synthetic backends.

- ORAS5 ``fetch_features_many``: real xarray/Zarr code path over an in-memory
  dataset (vectorized nearest-neighbor select), validated against the
  single-point path.
- GEE ``fetch_features_many``: real ``reduceRegions`` assembly over a fake
  Earth Engine module implementing the fluent API.
- ``bulk_fetch.fetch_features_many``: one bulk call per data plane for all
  spatial cells.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from app.connectors.bulk_fetch import BulkAssetPoint, fetch_features_many
from app.connectors.cds_oras5 import ORAS5_UNSCORABLE_MESSAGE, CDSOras5Connector, Oras5PointRequest
from app.connectors.gee import GeeConnector, GeePointRequest
from app.core import error_codes as codes
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.schemas.risk import RiskBatchAsset, RiskBatchRequest
from app.services.risk_service import RiskService

# ---------------------------------------------------------------------------
# ORAS5: synthetic Zarr-like dataset
# ---------------------------------------------------------------------------


def _synthetic_oras5_dataset() -> xr.Dataset:
    times = pd.date_range("1995-01-01", periods=120, freq="MS")
    lats = np.arange(38.0, 43.0, 0.5)
    lons = np.arange(26.0, 34.0, 0.5)

    t = np.arange(len(times), dtype=float)
    # Warming trend + seasonal cycle, offset per grid point so points differ.
    base = 15.0 + 0.003 * t + 1.5 * np.sin(2 * np.pi * t / 12)
    sst = (
        base[:, None, None]
        + 0.1 * lats[None, :, None]
        + 0.05 * lons[None, None, :]
    )
    zos = (
        0.0002 * t[:, None, None]
        + 0.001 * lats[None, :, None]
        + np.zeros((len(times), len(lats), len(lons)))
    )
    return xr.Dataset(
        {
            "sst": (("time", "latitude", "longitude"), sst),
            "zos": (("time", "latitude", "longitude"), zos),
        },
        coords={"time": times, "latitude": lats, "longitude": lons},
    )


@pytest.fixture()
def oras5_live(monkeypatch: pytest.MonkeyPatch) -> CDSOras5Connector:
    ds = _synthetic_oras5_dataset()
    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://synthetic-oras5")
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))
    return CDSOras5Connector()


def test_oras5_bulk_matches_single_point_path(oras5_live: CDSOras5Connector) -> None:
    payloads = [
        Oras5PointRequest(latitude=41.0, longitude=29.0),
        Oras5PointRequest(latitude=40.4, longitude=27.8),
        Oras5PointRequest(latitude=39.9, longitude=32.8),
    ]
    bulk = oras5_live.fetch_features_many(payloads)
    assert len(bulk) == 3
    for payload, features in zip(payloads, bulk):
        single = oras5_live.fetch_features(payload)
        assert features == pytest.approx(single)
        # Live path must not equal the offline stub values.
        assert features != CDSOras5Connector._fallback_features()
        assert features["sst_trend_c_per_decade"] > 0


def test_oras5_bulk_respects_date_window(oras5_live: CDSOras5Connector) -> None:
    windowed = oras5_live.fetch_features_many(
        [
            Oras5PointRequest(
                latitude=41.0,
                longitude=29.0,
                start_date=date(2000, 1, 1),
                end_date=date(2004, 12, 31),
            )
        ]
    )[0]
    full = oras5_live.fetch_features_many([Oras5PointRequest(latitude=41.0, longitude=29.0)])[0]
    assert windowed != full


def test_oras5_bulk_fallback_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oras5_zarr_url", None)
    connector = CDSOras5Connector()
    out = connector.fetch_features_many([Oras5PointRequest(latitude=41.0, longitude=29.0)])
    assert out == [CDSOras5Connector._fallback_features()]


def test_oras5_bulk_unscorable_point_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A land-masked point yields ``None`` in the bulk path instead of a silent
    all-zero feature dict; valid points in the same call stay intact, and the
    single-point path keeps its existing (zero-features) semantics."""
    ds = _synthetic_oras5_dataset()
    # Nearest grid point to (40.0, 30.0) = lat index 4 (40.0), lon index 8 (30.0).
    ds["sst"][:, 4, 8] = np.nan
    ds["zos"][:, 4, 8] = np.nan

    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://synthetic-oras5-land")
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))
    connector = CDSOras5Connector()

    out = connector.fetch_features_many(
        [
            Oras5PointRequest(latitude=40.0, longitude=30.0),
            Oras5PointRequest(latitude=41.0, longitude=29.0),
        ]
    )
    assert out[0] is None
    assert out[1] is not None
    assert out[1] != CDSOras5Connector._fallback_features()

    # Single-point runtime scoring applies the same rule and fails closed with
    # a typed 503 — it must NOT return a silent all-zero feature dict.
    with pytest.raises(GeoRiskApiError) as exc:
        connector.fetch_features(Oras5PointRequest(latitude=40.0, longitude=30.0))
    assert exc.value.code == codes.ORAS5_SERIES_UNSCORABLE
    assert exc.value.status_code == 503


def test_facade_marks_unscorable_oras5_cell_as_row_error(
    monkeypatch: pytest.MonkeyPatch, gee_live: GeeConnector
) -> None:
    """Bulk facade carries a typed per-row error for unscorable cells while
    valid cells keep their features (no error)."""
    ds = _synthetic_oras5_dataset()
    ds["sst"][:, 4, 8] = np.nan
    ds["zos"][:, 4, 8] = np.nan

    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://synthetic-oras5-land")
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))

    rows = fetch_features_many(
        [
            BulkAssetPoint(asset_id="LAND", latitude=40.0, longitude=30.0),
            BulkAssetPoint(asset_id="OCEAN", latitude=41.0, longitude=29.0),
        ],
        gee=gee_live,
    )
    by_id = {r.asset_id: r for r in rows}
    assert by_id["LAND"].error == {
        "code": codes.ORAS5_SERIES_UNSCORABLE,
        "message": ORAS5_UNSCORABLE_MESSAGE,
    }
    assert by_id["LAND"].oras5_features == {}
    assert by_id["OCEAN"].error is None
    assert by_id["OCEAN"].oras5_features != {}


def test_batch_mixed_valid_and_unscorable_oras5_rows(
    monkeypatch: pytest.MonkeyPatch, gee_live: GeeConnector
) -> None:
    """P0 regression: one land-masked ORAS5 point must fail as a typed row error
    while valid points in the same /v1/risk/batch request still succeed."""
    ds = _synthetic_oras5_dataset()
    ds["sst"][:, 4, 8] = np.nan
    ds["zos"][:, 4, 8] = np.nan

    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://synthetic-oras5-land")
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))
    svc = RiskService(oras5=CDSOras5Connector(), gee=GeeConnector())

    result = svc.batch_score(
        RiskBatchRequest(
            preset_id="industrial_v1",
            assets=[
                RiskBatchAsset(id="LAND", lat=40.0, lon=30.0),
                RiskBatchAsset(id="OCEAN-A", lat=41.0, lon=29.0),
                RiskBatchAsset(id="OCEAN-B", lat=39.9, lon=32.8),
            ],
        )
    )

    assert result.summary.total_assets == 3
    assert result.summary.success_count == 2
    assert result.summary.failed_count == 1
    by_id = {r.id: r for r in result.results}
    assert by_id["LAND"].success is False
    assert by_id["LAND"].error is not None
    assert by_id["LAND"].error.code == codes.ORAS5_SERIES_UNSCORABLE
    assert "land-masked" in by_id["LAND"].error.message
    assert by_id["OCEAN-A"].success is True
    assert by_id["OCEAN-A"].risk is not None
    assert by_id["OCEAN-B"].success is True
    assert by_id["OCEAN-B"].risk is not None


def test_oras5_slow_store_returns_503_within_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung store read must degrade to DATA_SOURCE_UNAVAILABLE (503) at the
    configured timeout instead of blocking the request worker indefinitely."""
    ds = _synthetic_oras5_dataset()

    def _slow_open(_url: str) -> xr.Dataset:
        time.sleep(10)
        return ds

    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://slow-oras5")
    monkeypatch.setattr(settings, "oras5_fetch_timeout_seconds", 0.25)
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(_slow_open))
    connector = CDSOras5Connector()

    started = time.monotonic()
    with pytest.raises(GeoRiskApiError) as excinfo:
        connector.fetch_features(Oras5PointRequest(latitude=41.0, longitude=29.0))
    elapsed = time.monotonic() - started

    assert excinfo.value.code == "DATA_SOURCE_UNAVAILABLE"
    assert excinfo.value.status_code == 503
    # Prompt return: well under the 10s sleep the abandoned worker is stuck on.
    assert elapsed < 5.0


def test_oras5_store_runtime_error_degrades_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing variable / network error inside the store read must surface as
    a clean sanitized DATA_SOURCE_UNAVAILABLE (503), not a raw exception."""
    def _broken_open(_url: str) -> xr.Dataset:
        raise KeyError("sosstsst not found")

    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://broken-oras5")
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(_broken_open))
    connector = CDSOras5Connector()

    with pytest.raises(GeoRiskApiError) as excinfo:
        connector.fetch_features_many([Oras5PointRequest(latitude=41.0, longitude=29.0)])

    assert excinfo.value.code == "DATA_SOURCE_UNAVAILABLE"
    assert excinfo.value.status_code == 503
    # Sanitised surface: raw exception text (variable name) is never echoed.
    assert "sosstsst" not in excinfo.value.message
    assert "KeyError" in excinfo.value.message


# ---------------------------------------------------------------------------
# GEE: fake Earth Engine implementing the fluent reduceRegions chain
# ---------------------------------------------------------------------------


class _FakeGeometry:
    def __init__(self, coords: list[float]) -> None:
        self.coords = coords

    def buffer(self, meters: float) -> "_FakeGeometry":
        return self


class _FakeFeature:
    def __init__(self, geometry: _FakeGeometry, properties: dict[str, Any]) -> None:
        self.geometry = geometry
        self.properties = properties


class _FakeFeatureCollection:
    def __init__(self, features: list[_FakeFeature]) -> None:
        self.features = features


class _FakeReducedCollection:
    def __init__(self, base_value: float, collection: _FakeFeatureCollection) -> None:
        self.base_value = base_value
        self.collection = collection

    def getInfo(self) -> dict[str, Any]:
        return {
            "features": [
                {
                    "properties": {
                        "idx": f.properties["idx"],
                        # Distinct value per region so ordering is verifiable.
                        "mean": self.base_value + f.properties["idx"],
                    }
                }
                for f in self.collection.features
            ]
        }


class _FakeImage:
    def __init__(self, base_value: float) -> None:
        self.base_value = base_value

    def reduceRegions(self, collection: _FakeFeatureCollection, reducer: Any, scale: int) -> _FakeReducedCollection:
        return _FakeReducedCollection(self.base_value, collection)


class _FakeImageCollection:
    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        self.window: tuple[str, str] | None = None

    def filterDate(self, start: str, end: str) -> "_FakeImageCollection":
        self.window = (start, end)
        return self

    def select(self, band: str) -> "_FakeImageCollection":
        return self

    def mean(self) -> _FakeImage:
        assert self.window is not None
        # Baseline windows (pre-2021 end) return lower means than current windows.
        is_baseline = self.window[1] <= "2021-01-01"
        if "VIIRS" in self.dataset:
            return _FakeImage(10.0 if is_baseline else 20.0)
        return _FakeImage(0.0001 if is_baseline else 0.0002)


class _FakeReducer:
    @staticmethod
    def mean() -> str:
        return "mean"


class _FakeEE:
    ImageCollection = _FakeImageCollection
    Feature = _FakeFeature
    FeatureCollection = _FakeFeatureCollection
    Reducer = _FakeReducer

    class Geometry:
        @staticmethod
        def Point(coords: list[float]) -> _FakeGeometry:
            return _FakeGeometry(coords)


@pytest.fixture()
def gee_live(monkeypatch: pytest.MonkeyPatch) -> GeeConnector:
    monkeypatch.setattr(settings, "gee_enabled", True)
    monkeypatch.setattr(settings, "gee_project", "synthetic-project")
    monkeypatch.setattr(GeeConnector, "_ee", staticmethod(lambda: _FakeEE))
    return GeeConnector()


def test_gee_bulk_reduce_regions_assigns_per_region_means(gee_live: GeeConnector) -> None:
    payloads = [
        GeePointRequest(latitude=41.0, longitude=29.0),
        GeePointRequest(latitude=40.4, longitude=27.8),
    ]
    out = gee_live.fetch_features_many(payloads)
    assert len(out) == 2
    # base 20.0 + idx offset from the fake reduceRegions output
    assert out[0]["night_lights_mean"] == pytest.approx(20.0)
    assert out[1]["night_lights_mean"] == pytest.approx(21.0)
    assert out[0]["no2_mean"] == pytest.approx(0.0002)
    # No baseline window requested → deviation keys stay None
    assert out[0]["night_lights_relative_deviation"] is None


def test_gee_bulk_baseline_deviation_and_bundles(gee_live: GeeConnector) -> None:
    payloads = [
        GeePointRequest(
            latitude=41.0,
            longitude=29.0,
            baseline_start_date=date(1991, 1, 1),
            baseline_end_date=date(2020, 12, 31),
        ),
        GeePointRequest(
            latitude=40.4,
            longitude=27.8,
            baseline_start_date=date(1991, 1, 1),
            baseline_end_date=date(2020, 12, 31),
        ),
    ]
    bundles = gee_live.fetch_baseline_features_many(payloads)
    assert len(bundles) == 2
    first = bundles[0]["current"]
    assert first["night_lights_baseline_mean"] == pytest.approx(10.0)
    # (20 - 10) / 10 = 1.0
    assert first["night_lights_relative_deviation"] == pytest.approx(1.0)
    assert first["night_lights_comparison"] is not None
    assert bundles[0]["baseline"]["night_lights_mean"] == pytest.approx(10.0)


def test_gee_bulk_fallback_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gee_enabled", False)
    connector = GeeConnector()
    out = connector.fetch_features_many([GeePointRequest(latitude=41.0, longitude=29.0)])
    assert out == [GeeConnector._fallback_features()]


# ---------------------------------------------------------------------------
# Facade: one bulk call per data plane
# ---------------------------------------------------------------------------


class _CountingOras5(CDSOras5Connector):
    def __init__(self) -> None:
        self.bulk_calls: list[int] = []

    def fetch_features_many(self, payloads: list[Oras5PointRequest]) -> list[dict[str, float]]:
        self.bulk_calls.append(len(payloads))
        return [self._fallback_features() for _ in payloads]


class _CountingGee(GeeConnector):
    def __init__(self) -> None:
        self.bulk_calls: list[int] = []

    def fetch_baseline_features_many(self, payloads: list[GeePointRequest]) -> list[dict[str, Any]]:
        self.bulk_calls.append(len(payloads))
        return [
            {"current": self._fallback_features(), "baseline": {"night_lights_mean": 8.0, "no2_mean": 0.00007}}
            for _ in payloads
        ]


def test_facade_issues_single_bulk_call_per_plane() -> None:
    oras5 = _CountingOras5()
    gee = _CountingGee()
    points = [
        BulkAssetPoint(asset_id="A", latitude=41.01, longitude=29.01),
        BulkAssetPoint(asset_id="B", latitude=41.02, longitude=29.02),  # same 0.5° cell as A
        BulkAssetPoint(asset_id="C", latitude=39.9, longitude=32.8),
    ]
    rows = fetch_features_many(points, oras5=oras5, gee=gee)
    assert len(rows) == 3
    # 2 cells → exactly one bulk call per plane, each covering both cells.
    assert oras5.bulk_calls == [2]
    assert gee.bulk_calls == [2]
    by_id = {r.asset_id: r for r in rows}
    assert by_id["A"].coalesce_mode == "spatial_cell_coalesce"
    assert by_id["C"].coalesce_mode == "spatial_cell_singleton"
    assert by_id["A"].cell_id == by_id["B"].cell_id

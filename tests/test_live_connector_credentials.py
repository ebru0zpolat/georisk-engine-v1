"""Live-connector credential wiring.

- ORAS5: operational-store selection and cross-boundary merge over synthetic
  Zarr-like datasets, plus real CDS ARCO variable names (sosstsst / sossheig).
- GEE: service-account JSON is turned into ``ServiceAccountCredentials`` with
  ``key_data`` and passed to ``ee.Initialize``.
- Settings: placeholder URL / credential values normalize to ``None``.
"""

from __future__ import annotations

import sys
import types
from datetime import date

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from app.connectors.cds_oras5 import CDSOras5Connector, Oras5PointRequest
from app.connectors.gee import GeeConnector
from app.core.config import Settings, settings
from app.core.exceptions import GeoRiskApiError


# ---------------------------------------------------------------------------
# ORAS5: store selection + cross-boundary merge
# ---------------------------------------------------------------------------


def _make_store(times: pd.DatetimeIndex, prefix: float) -> xr.Dataset:
    lats = np.arange(38.0, 43.0, 0.5)
    lons = np.arange(26.0, 34.0, 0.5)
    t = np.arange(len(times), dtype=float)
    sst = (
        (prefix + 0.01 * t)[:, None, None]
        + 0.1 * lats[None, :, None]
        + 0.05 * lons[None, None, :]
    )
    zos = 0.0002 * t[:, None, None] + np.zeros((len(times), len(lats), len(lons)))
    return xr.Dataset(
        {
            "sst": (("time", "latitude", "longitude"), sst),
            "zos": (("time", "latitude", "longitude"), zos),
        },
        coords={"time": times, "latitude": lats, "longitude": lons},
    )


@pytest.fixture()
def dual_stores(monkeypatch: pytest.MonkeyPatch) -> tuple[xr.Dataset, xr.Dataset]:
    historical = _make_store(pd.date_range("2013-01-01", periods=24, freq="MS"), prefix=12.0)
    operational = _make_store(pd.date_range("2015-01-01", periods=24, freq="MS"), prefix=16.0)
    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://oras5-historical")
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", "memory://oras5-operational")

    def _open(url: str) -> xr.Dataset:
        return historical if url == "memory://oras5-historical" else operational

    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(_open))
    return historical, operational


def test_store_urls_for_window_selection(dual_stores: tuple[xr.Dataset, xr.Dataset]) -> None:
    connector = CDSOras5Connector()
    # Window fully inside historical (≤2014) → historical store only.
    assert connector._store_urls_for(date(2010, 1, 1), date(2014, 12, 31)) == [
        settings.oras5_zarr_url
    ]
    # Window fully inside operational (≥2015) → operational store only.
    assert connector._store_urls_for(date(2015, 1, 1), date(2020, 1, 1)) == [
        settings.oras5_zarr_operational_url
    ]
    # Window spanning the boundary → both stores (historical first).
    assert connector._store_urls_for(date(2013, 1, 1), date(2016, 1, 1)) == [
        settings.oras5_zarr_url,
        settings.oras5_zarr_operational_url,
    ]
    # No window → whole record, both stores.
    assert connector._store_urls_for(None, None) == [
        settings.oras5_zarr_url,
        settings.oras5_zarr_operational_url,
    ]


def test_oras5_merges_cross_boundary_window(dual_stores: tuple[xr.Dataset, xr.Dataset]) -> None:
    connector = CDSOras5Connector()
    merged = connector.fetch_features(
        Oras5PointRequest(
            latitude=41.0,
            longitude=29.0,
            start_date=date(2013, 1, 1),
            end_date=date(2016, 1, 1),
        )
    )
    # Merged 48-month series drives the trend; stub values would be 0.21/3.1.
    assert merged["sst_trend_c_per_decade"] > 0.5
    assert merged["sea_level_trend_mm_per_year"] > 0


def test_oras5_uses_operational_store_only_after_2015(
    dual_stores: tuple[xr.Dataset, xr.Dataset],
) -> None:
    connector = CDSOras5Connector()
    post_2015 = connector.fetch_features(
        Oras5PointRequest(latitude=41.0, longitude=29.0, start_date=date(2015, 1, 1))
    )
    pre_2015 = connector.fetch_features(
        Oras5PointRequest(latitude=41.0, longitude=29.0, start_date=date(2013, 1, 1), end_date=date(2014, 12, 31))
    )
    # Both windows resolve real data (not stubs) from their respective stores.
    assert post_2015["sst_trend_c_per_decade"] > 0
    assert pre_2015["sst_trend_c_per_decade"] > 0
    # Different stores → different series → different trends.
    assert post_2015["sst_trend_c_per_decade"] != pre_2015["sst_trend_c_per_decade"]


def test_concat_series_deduplicates_overlapping_coverage_keeping_first() -> None:
    """Overlapping store coverage: duplicate timestamps keep the FIRST part.

    ``_store_urls_for`` emits historical before operational, so when the two
    stores overlap (e.g. the operational store also carries the boundary months)
    the historical value must win and the result stays chronological with no
    duplicate timestamps.
    """
    index = pd.date_range("2014-06-01", periods=6, freq="MS")
    historical = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=index)
    overlap = pd.date_range("2014-10-01", periods=6, freq="MS")
    operational = pd.Series([100.0, 200.0, 300.0, 400.0, 500.0, 600.0], index=overlap)

    merged = CDSOras5Connector._concat_series([historical, operational])

    assert merged.index.is_monotonic_increasing
    assert not merged.index.duplicated().any()
    assert len(merged) == 10
    # First occurrence wins: historical values for the shared months.
    assert merged.loc["2014-10-01"] == 5.0
    assert merged.loc["2014-11-01"] == 6.0
    # Operational-only months keep their operational values.
    assert merged.loc["2014-12-01"] == 300.0
    assert merged.loc["2015-01-01"] == 400.0
    assert merged.loc["2015-03-01"] == 600.0


def test_concat_series_drops_empty_parts() -> None:
    empty = pd.Series(dtype=float)
    assert CDSOras5Connector._concat_series([empty, empty]).empty
    # A single non-empty part passes through unchanged.
    index = pd.date_range("2015-01-01", periods=3, freq="MS")
    single = pd.Series([1.0, 2.0, 3.0], index=index)
    out = CDSOras5Connector._concat_series([empty, single, empty])
    assert out.equals(single)


def test_oras5_historical_only_store_post_2015_window_unscorable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No operational store: a post-2015 window yields an empty series.

    With only ``ORAS5_ZARR_URL`` configured the historical store is always used
    (backwards compatible), so a window outside its 1958–2014 coverage has no
    scorable data and runtime scoring must fail closed with a typed 503 — never
    a silent all-zero feature dict, and never the 0.21/3.1 offline stubs. With
    the operational store configured the same window resolves real data.
    """
    historical = _make_store(pd.date_range("2013-01-01", periods=24, freq="MS"), prefix=12.0)
    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://hist-only")
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", None)
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: historical))

    payload = Oras5PointRequest(
        latitude=41.0,
        longitude=29.0,
        start_date=date(2015, 1, 1),
        end_date=date(2020, 1, 1),
    )
    with pytest.raises(GeoRiskApiError) as exc:
        CDSOras5Connector().fetch_features(payload)
    assert exc.value.code == "ORAS5_SERIES_UNSCORABLE"
    assert exc.value.status_code == 503
    assert "land-masked" in exc.value.message

    # The same window WITH the operational store is real data — the
    # historical-only degradation is the fail-closed gap, not the norm.
    operational = _make_store(pd.date_range("2015-01-01", periods=24, freq="MS"), prefix=16.0)
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", "memory://operational")

    def _open(url: str) -> xr.Dataset:
        return historical if url == "memory://hist-only" else operational

    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(_open))
    live = CDSOras5Connector().fetch_features(payload)
    assert live["sst_trend_c_per_decade"] > 0
    assert live != CDSOras5Connector._fallback_features()


def test_oras5_bulk_merges_across_stores(dual_stores: tuple[xr.Dataset, xr.Dataset]) -> None:
    connector = CDSOras5Connector()
    payloads = [
        Oras5PointRequest(latitude=41.0, longitude=29.0, start_date=date(2013, 1, 1), end_date=date(2016, 1, 1)),
        Oras5PointRequest(latitude=40.4, longitude=27.8, start_date=date(2013, 1, 1), end_date=date(2016, 1, 1)),
    ]
    bulk = connector.fetch_features_many(payloads)
    assert len(bulk) == 2
    for row, payload in zip(bulk, payloads):
        single = connector.fetch_features(payload)
        assert row == pytest.approx(single)
        assert row != CDSOras5Connector._fallback_features()


def test_oras5_bulk_heterogeneous_windows(dual_stores: tuple[xr.Dataset, xr.Dataset]) -> None:
    """A batch mixing pre-2015 and post-2015 windows must open BOTH stores.

    Regression: store selection previously used only the first payload's window,
    so a post-2015 request after a pre-2015 request returned an empty series
    (0.0 features).
    """
    connector = CDSOras5Connector()
    payloads = [
        Oras5PointRequest(latitude=41.0, longitude=29.0, start_date=date(2013, 1, 1), end_date=date(2014, 12, 31)),
        Oras5PointRequest(latitude=41.0, longitude=29.0, start_date=date(2015, 1, 1), end_date=date(2016, 12, 31)),
    ]
    bulk = connector.fetch_features_many(payloads)
    assert len(bulk) == 2
    for row, payload in zip(bulk, payloads):
        single = connector.fetch_features(payload)
        assert row == pytest.approx(single)
        # Post-2015 row must be real data, not an empty-series 0.0 fallback.
        assert row["sst_trend_c_per_decade"] != 0.0
        assert row != CDSOras5Connector._fallback_features()


def test_oras5_real_cds_variable_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """CDS ARCO stores name the surface fields sosstsst / sossheig."""
    times = pd.date_range("1995-01-01", periods=36, freq="MS")
    lats = np.arange(38.0, 43.0, 0.5)
    lons = np.arange(26.0, 34.0, 0.5)
    ds = xr.Dataset(
        {
            "sosstsst": (("time", "latitude", "longitude"), 15.0 + np.zeros((36, 10, 16))),
            "sossheig": (("time", "latitude", "longitude"), np.zeros((36, 10, 16))),
            "iicethic": (("time", "latitude", "longitude"), np.zeros((36, 10, 16))),
        },
        coords={"time": times, "latitude": lats, "longitude": lons},
    )
    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://cds-arco")
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", None)
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))

    out = CDSOras5Connector().fetch_features(Oras5PointRequest(latitude=41.0, longitude=29.0))
    # Flat series → zero trend computed from the real store (not the 0.21 stub).
    assert out["sst_trend_c_per_decade"] == pytest.approx(0.0, abs=1e-9)
    assert "sst_anomaly_zscore" in out


# ---------------------------------------------------------------------------
# ORAS5: cdsapi time-series path (reanalysis-oras5-timeseries)
# ---------------------------------------------------------------------------


# 36 monthly points (2013-01 → 2015-12) with a warming SST trend, so the
# feature extractors (which need >= 24 points) produce non-zero output.
_CDSAPI_MONTHS = pd.date_range("2013-01-01", periods=36, freq="MS")
_CDSAPI_CSV = pd.DataFrame(
    {
        "date": _CDSAPI_MONTHS.strftime("%Y-%m-%d"),
        "sea_surface_temperature": 15.0 + 0.05 * np.arange(36),
        "sea_surface_height": 0.01 + 0.0005 * np.arange(36),
    }
).to_csv(index=False).encode()


class _FakeCdsResult:
    def __init__(self, csv_bytes: bytes) -> None:
        self.csv_bytes = csv_bytes

    def download(self, target: str | None = None) -> str:
        with open(str(target), "wb") as fh:
            fh.write(self.csv_bytes)
        return str(target)


class _FakeCdsClient:
    def __init__(self, csv_bytes: bytes) -> None:
        self.csv_bytes = csv_bytes
        self.requests: list[tuple[str, dict]] = []

    def retrieve(self, name: str, request: dict) -> _FakeCdsResult:
        self.requests.append((name, request))
        return _FakeCdsResult(self.csv_bytes)


@pytest.fixture()
def cdsapi_live(monkeypatch: pytest.MonkeyPatch) -> _FakeCdsClient:
    fake = _FakeCdsClient(_CDSAPI_CSV)
    monkeypatch.setattr(settings, "oras5_zarr_url", None)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "uid:apikey")
    monkeypatch.setattr(CDSOras5Connector, "_cdsapi_client", staticmethod(lambda: fake))
    return fake


def test_oras5_cdsapi_product_type_selection() -> None:
    connector = CDSOras5Connector()
    assert connector._cdsapi_product_types_for(date(2010, 1, 1), date(2014, 12, 31)) == ["consolidated"]
    assert connector._cdsapi_product_types_for(date(2015, 1, 1), date(2020, 1, 1)) == ["operational"]
    assert connector._cdsapi_product_types_for(date(2013, 1, 1), date(2016, 1, 1)) == [
        "consolidated",
        "operational",
    ]
    assert connector._cdsapi_product_types_for(None, None) == ["consolidated", "operational"]


def test_oras5_fetch_features_via_cdsapi(cdsapi_live: _FakeCdsClient) -> None:
    out = CDSOras5Connector().fetch_features(
        Oras5PointRequest(
            latitude=41.0,
            longitude=29.0,
            start_date=date(2013, 1, 1),
            end_date=date(2015, 12, 31),
        )
    )
    assert out != CDSOras5Connector._fallback_features()
    assert out["sst_trend_c_per_decade"] > 0

    name, request = cdsapi_live.requests[0]
    assert name == "reanalysis-oras5-timeseries"
    assert request["product_type"] == ["consolidated", "operational"]
    assert request["variable"] == ["sea_surface_temperature", "sea_surface_height"]
    assert request["location"] == {"longitude": 29.0, "latitude": 41.0}
    assert request["data_format"] == "csv"


def test_oras5_cdsapi_respects_date_window(cdsapi_live: _FakeCdsClient) -> None:
    full = CDSOras5Connector().fetch_features(Oras5PointRequest(latitude=41.0, longitude=29.0))
    assert full["sst_trend_c_per_decade"] > 0

    # A short window (< 24 months) is unscorable → typed 503, never zero
    # features; the request is still submitted with the operational product type.
    with pytest.raises(GeoRiskApiError) as exc:
        CDSOras5Connector().fetch_features(
            Oras5PointRequest(latitude=41.0, longitude=29.0, start_date=date(2015, 6, 1))
        )
    assert exc.value.code == "ORAS5_SERIES_UNSCORABLE"
    assert exc.value.status_code == 503
    assert cdsapi_live.requests[-1][1]["product_type"] == ["operational"]


def test_oras5_bulk_via_cdsapi(cdsapi_live: _FakeCdsClient) -> None:
    """Bulk cdsapi fallback: one sequential retrieve per payload, in order."""
    payloads = [
        Oras5PointRequest(latitude=41.0, longitude=29.0),
        Oras5PointRequest(latitude=40.0, longitude=28.0),
    ]
    out = CDSOras5Connector().fetch_features_many(payloads)
    assert len(out) == 2
    assert len(cdsapi_live.requests) == 2
    # Each request mirrors its payload (location + full-coverage product types),
    # and results are live-parsed features, never the offline stubs.
    for request, payload in zip(cdsapi_live.requests, payloads):
        name, body = request
        assert name == "reanalysis-oras5-timeseries"
        assert body["location"] == {"longitude": payload.longitude, "latitude": payload.latitude}
        assert body["product_type"] == ["consolidated", "operational"]
    for row in out:
        assert row != CDSOras5Connector._fallback_features()
        assert all(np.isfinite(v) for v in row.values())


def test_oras5_bulk_via_cdsapi_per_point_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per-payload requests map 1:1 to per-payload results (order preserved)."""

    class _PerPointCdsClient(_FakeCdsClient):
        def __init__(self) -> None:
            super().__init__(b"")
            self.requests: list[tuple[str, dict]] = []

        def retrieve(self, name: str, request: dict) -> _FakeCdsResult:
            self.requests.append((name, request))
            # SST slope varies with the requested longitude so the two payloads
            # yield measurably different features.
            lon = request["location"]["longitude"]
            t = np.arange(len(_CDSAPI_MONTHS))
            csv_df = pd.DataFrame(
                {
                    "date": _CDSAPI_MONTHS.strftime("%Y-%m-%d"),
                    "sea_surface_temperature": 15.0 + (0.02 + 0.001 * (lon - 28.0)) * t,
                    "sea_surface_height": 0.01 + 0.0005 * t,
                }
            )
            return _FakeCdsResult(csv_df.to_csv(index=False).encode())

    fake = _PerPointCdsClient()
    monkeypatch.setattr(settings, "oras5_zarr_url", None)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "uid:apikey")
    monkeypatch.setattr(CDSOras5Connector, "_cdsapi_client", staticmethod(lambda: fake))

    payloads = [
        Oras5PointRequest(latitude=41.0, longitude=29.0),
        Oras5PointRequest(latitude=40.0, longitude=28.0),
    ]
    out = CDSOras5Connector().fetch_features_many(payloads)
    assert len(out) == 2
    assert len(fake.requests) == 2
    # Order preserved: request i corresponds to payload i.
    for (name, body), payload in zip(fake.requests, payloads):
        assert name == "reanalysis-oras5-timeseries"
        assert body["location"] == {"longitude": payload.longitude, "latitude": payload.latitude}
    # Distinct per-point series → distinct trends, both live (not stubs).
    assert out[0]["sst_trend_c_per_decade"] != out[1]["sst_trend_c_per_decade"]
    for row in out:
        assert row["sst_trend_c_per_decade"] > 0
        assert row != CDSOras5Connector._fallback_features()


def test_oras5_cdsapi_client_accepts_bare_uuid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """New-CDS single-key format (bare UUID) must build a client.

    Verified live against cds.climate.copernicus.eu: the bare UUID is accepted
    directly (legacy <UID>:<APIKEY> pairs also still work). The key below is a
    SYNTHETIC UUID — never commit a real credential in tests.
    """
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "11111111-2222-3333-4444-555555555555")
    monkeypatch.setattr(settings, "copernicus_cds_url", "https://cds.climate.copernicus.eu/api")
    CDSOras5Connector._cdsapi_client.cache_clear()
    try:
        client = CDSOras5Connector._cdsapi_client()
        assert client is not None
    finally:
        CDSOras5Connector._cdsapi_client.cache_clear()


def test_oras5_cdsapi_client_accepts_legacy_uid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy '<UID>:<APIKEY>' pairs must still build a client."""
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "12345:deadbeef-uuid")
    monkeypatch.setattr(settings, "copernicus_cds_url", "https://cds.climate.copernicus.eu/api")
    CDSOras5Connector._cdsapi_client.cache_clear()
    try:
        client = CDSOras5Connector._cdsapi_client()
        assert client is not None
    finally:
        CDSOras5Connector._cdsapi_client.cache_clear()


def test_oras5_cdsapi_client_requires_nonempty_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "   ")
    CDSOras5Connector._cdsapi_client.cache_clear()
    try:
        with pytest.raises(GeoRiskApiError) as exc:
            CDSOras5Connector._cdsapi_client()
        assert exc.value.code == "CDSAPI_CREDENTIALS_INVALID"
    finally:
        CDSOras5Connector._cdsapi_client.cache_clear()


def test_settings_copernicus_cds_url_alias() -> None:
    parsed = Settings(copernicus_cds_url="https://cds.climate.copernicus.eu/api")
    assert parsed.copernicus_cds_url == "https://cds.climate.copernicus.eu/api"


def test_oras5_build_zarr_store_uses_obstore_for_https() -> None:
    pytest.importorskip("obstore")
    store = CDSOras5Connector._build_zarr_store(
        "https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr"
    )
    assert store is not None
    assert type(store).__name__ == "ObjectStore"


def test_oras5_build_zarr_store_skips_non_http_urls() -> None:
    assert CDSOras5Connector._build_zarr_store("memory://synthetic-oras5") is None


def test_oras5_flat_series_produces_finite_features() -> None:
    """Flat series (e.g. land-snapped cell) must yield 0.0, never NaN."""
    index = pd.date_range("1995-01-01", periods=36, freq="MS")
    flat_sst = pd.Series(15.0, index=index)
    flat_ssh = pd.Series(0.0, index=index)

    assert CDSOras5Connector._variability_index(flat_sst) == 0.0
    features = CDSOras5Connector._features_from_series(flat_sst, flat_ssh)
    assert all(np.isfinite(v) for v in features.values())
    assert features["ocean_variability_index"] == 0.0
    assert features["sst_trend_c_per_decade"] == pytest.approx(0.0, abs=1e-9)


def test_oras5_csv_zarr_feature_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """CSV–Zarr parity: identical values → identical series → identical features.

    The cdsapi path (reanalysis-oras5-timeseries CSV download) and the Zarr ARCO
    path must produce the same pandas series from the same underlying values, so
    the derived risk features agree. Builds the CSV from the exact series the
    Zarr path selects (round-trip), then compares both the parsed series and the
    final features.
    """
    times = pd.date_range("1995-01-01", periods=36, freq="MS")
    lats = np.arange(38.0, 43.0, 0.5)
    lons = np.arange(26.0, 34.0, 0.5)
    t = np.arange(36, dtype=float)
    sst = (15.0 + 0.05 * t)[:, None, None] + 0.1 * lats[None, :, None] + 0.05 * lons[None, None, :]
    ssh = (0.01 + 0.0005 * t)[:, None, None] + np.zeros((36, len(lats), len(lons)))
    ds = xr.Dataset(
        {
            "sosstsst": (("time", "latitude", "longitude"), sst),
            "sossheig": (("time", "latitude", "longitude"), ssh),
        },
        coords={"time": times, "latitude": lats, "longitude": lons},
    )
    monkeypatch.setattr(settings, "oras5_zarr_url", "memory://parity")
    monkeypatch.setattr(settings, "oras5_zarr_operational_url", None)
    monkeypatch.setattr(CDSOras5Connector, "_open_dataset", staticmethod(lambda url: ds))

    payload = Oras5PointRequest(latitude=41.0, longitude=29.0)
    connector = CDSOras5Connector()
    zarr_features = connector.fetch_features(payload)
    assert zarr_features != CDSOras5Connector._fallback_features()

    # Build the CDS-style CSV from the exact series the Zarr path selected.
    sst_series = connector._point_series_from_store("memory://parity", "sosstsst", payload)
    ssh_series = connector._point_series_from_store("memory://parity", "sossheig", payload)
    csv_df = pd.DataFrame(
        {
            "date": sst_series.index.strftime("%Y-%m-%d"),
            "sea_surface_temperature": sst_series.to_numpy(),
            "sea_surface_height": ssh_series.to_numpy(),
        }
    )
    csv_bytes = csv_df.to_csv(index=False).encode()

    # Switch to the cdsapi path and feed it the same series as a CSV download.
    monkeypatch.setattr(settings, "oras5_zarr_url", None)
    monkeypatch.setattr(settings, "copernicus_cds_api_key", "uid:apikey")
    monkeypatch.setattr(
        CDSOras5Connector,
        "_cdsapi_client",
        staticmethod(lambda: _FakeCdsClient(csv_bytes)),
    )
    parsed_sst, parsed_ssh = CDSOras5Connector._parse_cdsapi_csv(
        csv_bytes,
        sst_candidates=["sea_surface_temperature", "sosstsst"],
        sea_level_candidates=["sea_surface_height", "sossheig"],
    )
    csv_features = connector.fetch_features(payload)

    # Series parity (values identical through both parsers).
    assert parsed_sst.to_numpy() == pytest.approx(sst_series.to_numpy(), rel=1e-12)
    assert parsed_ssh.to_numpy() == pytest.approx(ssh_series.to_numpy(), rel=1e-12)
    # Feature parity (same features from Zarr and CSV paths).
    assert csv_features == pytest.approx(zarr_features, rel=1e-9)
    assert csv_features != CDSOras5Connector._fallback_features()


# ---------------------------------------------------------------------------
# GEE: service-account JSON credentials
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_ee(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    class _FakeCredentials:
        def __init__(self, email: str, key_data: str | None = None) -> None:
            captured["email"] = email
            captured["key_data"] = key_data

    class _FakeEE:
        @staticmethod
        def ServiceAccountCredentials(email: str, key_data: str | None = None) -> _FakeCredentials:
            return _FakeCredentials(email, key_data=key_data)

        @staticmethod
        def Initialize(project: str | None = None, credentials: object | None = None) -> None:
            captured["project"] = project
            captured["credentials"] = credentials

    module = types.ModuleType("ee")
    module.ServiceAccountCredentials = _FakeEE.ServiceAccountCredentials
    module.Initialize = _FakeEE.Initialize
    monkeypatch.setitem(sys.modules, "ee", module)
    GeeConnector._ee.cache_clear()
    return captured


def test_gee_ee_initializes_with_service_account_json(
    fake_ee: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    key_json = '{"type": "service_account", "client_email": "info@georiskengine.com"}'
    monkeypatch.setattr(settings, "gee_service_account_json", key_json)
    monkeypatch.setattr(settings, "gee_project", "ee-proj")

    GeeConnector._ee()

    assert fake_ee["email"] == "info@georiskengine.com"
    assert fake_ee["key_data"] == key_json
    assert fake_ee["project"] == "ee-proj"
    assert fake_ee["credentials"] is not None
    GeeConnector._ee.cache_clear()


def test_gee_ee_without_service_account_json_uses_defaults(
    fake_ee: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gee_service_account_json", None)
    monkeypatch.setattr(settings, "gee_project", "ee-proj")

    GeeConnector._ee()

    assert fake_ee["project"] == "ee-proj"
    assert fake_ee["credentials"] is None
    GeeConnector._ee.cache_clear()


def test_gee_invalid_service_account_json_raises(
    fake_ee: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gee_service_account_json", "not-json")

    with pytest.raises(GeoRiskApiError) as exc:
        GeeConnector._ee()
    assert exc.value.code == "GEE_CREDENTIALS_INVALID"
    GeeConnector._ee.cache_clear()


def test_gee_service_account_json_missing_client_email_raises(
    fake_ee: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gee_service_account_json", '{"private_key": "x"}')

    with pytest.raises(GeoRiskApiError) as exc:
        GeeConnector._ee()
    assert exc.value.code == "GEE_CREDENTIALS_INVALID"
    GeeConnector._ee.cache_clear()


# ---------------------------------------------------------------------------
# Settings normalization
# ---------------------------------------------------------------------------


def test_settings_normalize_oras5_urls() -> None:
    parsed = Settings(
        oras5_zarr_url="<paste-zarr-store-url>",
        oras5_zarr_operational_url="   ",
    )
    assert parsed.oras5_zarr_url is None
    assert parsed.oras5_zarr_operational_url is None

    live = Settings(
        oras5_zarr_url="https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/consolidated/geoChunked.zarr",
        oras5_zarr_operational_url="https://arco.datastores.ecmwf.int/cadl-arco-geo-001/arco/reanalysis_oras5/operational/geoChunked.zarr",
    )
    assert live.oras5_zarr_url.startswith("https://arco.datastores.ecmwf.int")
    assert live.oras5_zarr_operational_url.endswith("operational/geoChunked.zarr")


def test_settings_normalize_gee_service_account_json() -> None:
    assert Settings(gee_service_account_json="changeme").gee_service_account_json is None
    assert Settings(gee_service_account_json="").gee_service_account_json is None
    key = '{"client_email": "info@georiskengine.com"}'
    assert Settings(gee_service_account_json=key).gee_service_account_json == key

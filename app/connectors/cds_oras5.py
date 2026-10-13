from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, TypeVar

import numpy as np
import pandas as pd
import xarray as xr

from app.core import error_codes as codes
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.core.runtime_mode import refuse_connector_stub_if_production

T = TypeVar("T")

#: Shared per-point data-gap message: surfaced on single-point 503s and on batch
#: rows (via ``bulk_fetch``), so every consumer reports the same reason.
ORAS5_UNSCORABLE_MESSAGE = (
    "No scorable ORAS5 series at this point (land-masked or outside store coverage)."
)

#: ORAS5 ARCO stores split at this boundary: the consolidated store covers
#: 1958–2014 and the operational store covers 2015–present.
_ORAS5_HISTORICAL_END = date(2014, 12, 31)
_ORAS5_OPERATIONAL_START = date(2015, 1, 1)

#: ORAS5 surface variable names (sosstsst = sea surface temperature,
#: sossheig = sea surface height) with generic CF-name fallbacks for
#: synthetic fixtures / alternate store layouts.
_SST_VAR_CANDIDATES = ["sosstsst", "sst", "sea_surface_temperature", "thetao"]
_SEA_LEVEL_VAR_CANDIDATES = ["sossheig", "zos", "sea_level", "sea_surface_height"]

#: CDS API point time-series dataset and its canonical column names
#: (reanalysis-oras5-timeseries, CSV output).
_CDSAPI_TIMESERIES_DATASET = "reanalysis-oras5-timeseries"
_CDSAPI_SST_VARS = ["sea_surface_temperature", "sosstsst"]
_CDSAPI_SEA_LEVEL_VARS = ["sea_surface_height", "sossheig"]
_CDSAPI_DATE_COLUMNS = ["date", "time", "valid_time"]


@dataclass(frozen=True)
class Oras5PointRequest:
    latitude: float
    longitude: float
    start_date: date | None = None
    end_date: date | None = None


class CDSOras5Connector:
    """
    ORAS5 connector using analysis-ready Zarr.

    This connector is designed to:
    - open the remote ORAS5 Zarr store(s) once
    - select nearest ocean grid point
    - extract monthly time series
    - compute risk features
    - score from computed features

    ``ORAS5_ZARR_URL`` (1958–2014) must be configured in .env once the CDS Zarr
    store URL is obtained from the CDS Analysis Ready Data tab. Optionally set
    ``ORAS5_ZARR_OPERATIONAL_URL`` (2015–present) so windows spanning the 2015
    boundary are merged from both stores. Both stores authenticate with a Bearer
    token derived from ``CDSAPI_KEY`` / ``COPERNICUS_CDS_API_KEY``.

    When no Zarr URL is configured but ``CDSAPI_KEY`` / ``COPERNICUS_CDS_API_KEY``
    is set, the connector falls back to the official CDS API time-series dataset
    (``reanalysis-oras5-timeseries``) via cdsapi — slower (queued jobs) but
    credential-agnostic (~/.cdsapirc or the API key env var).
    """

    def fetch_features(self, payload: Oras5PointRequest) -> dict[str, float]:
        """Features for one point.

        Not-configured → deterministic stubs in local/dev/test/demo.
        Production refuses the stub path (``CONNECTOR_STUB_PROHIBITED``).
        Configured-but-failing store reads degrade to ``DATA_SOURCE_UNAVAILABLE``
        (503) under a bounded wall-clock budget (``oras5_fetch_timeout_seconds``)
        instead of hanging the request worker or leaking raw exceptions —
        mirroring the GEE connector.

        A configured live read whose series is unscorable (land-masked, outside
        store coverage, or shorter than the 24-month feature minimum) raises
        ``ORAS5_SERIES_UNSCORABLE`` (503) — runtime scoring never returns a
        silent all-zero feature dict that looks like a valid low score. Zero
        features are only reachable through ``diagnostic_features_from_series``
        (labelled ``production_eligible=false``) or the unconfigured stub path.
        """
        if settings.oras5_zarr_url:
            # Zarr ARCO path: instant point reads (preferred for the sync API).
            return self._guarded(self._fetch_features_live, payload)
        if settings.copernicus_cds_api_key:
            # CDS API path: official reanalysis-oras5-timeseries retrieval.
            sst, sea_level = self._timeseries_via_cdsapi(payload)
            self._raise_if_unscorable(sst, sea_level)
            return self._features_from_series(sst, sea_level)
        refuse_connector_stub_if_production(
            source="oras5",
            reason="ORAS5_ZARR_URL unset",
        )
        return self._fallback_features()

    def _fetch_features_live(self, payload: Oras5PointRequest) -> dict[str, float]:
        """Zarr ARCO point read — runs inside ``_guarded`` (bounded timeout)."""
        sst_var, sea_level_var = self._resolve_vars()
        sst_parts: list[pd.Series] = []
        sea_level_parts: list[pd.Series] = []
        for url in self._store_urls_for(payload.start_date, payload.end_date):
            sst_parts.append(self._point_series_from_store(url, sst_var, payload))
            sea_level_parts.append(self._point_series_from_store(url, sea_level_var, payload))
        sst = self._concat_series(sst_parts)
        sea_level = self._concat_series(sea_level_parts)
        self._raise_if_unscorable(sst, sea_level)
        return self._features_from_series(sst, sea_level)

    @staticmethod
    def _raise_if_unscorable(sst: pd.Series, sea_level: pd.Series) -> None:
        """Fail-closed guard for single-point runtime scoring.

        Both series must meet the 24-month minimum the feature statistics need;
        otherwise the point has no scorable data and a numeric feature dict would
        be a misleading low-risk zero.
        """
        scorable = CDSOras5Connector._series_scorable(sst) and CDSOras5Connector._series_scorable(
            sea_level
        )
        if not scorable:
            raise GeoRiskApiError(
                code=codes.ORAS5_SERIES_UNSCORABLE,
                message=ORAS5_UNSCORABLE_MESSAGE,
                status_code=503,
            )

    @staticmethod
    def diagnostic_features_from_series(sst: pd.Series, sea_level: pd.Series) -> dict[str, Any]:
        """Diagnostic-only feature computation — never used by runtime scoring.

        Always returns numeric features (zeros for unscorable series) alongside
        an explicit ``production_eligible`` flag, so raw series statistics can
        be inspected without being mistaken for a scored result.
        """
        scorable = CDSOras5Connector._series_scorable(sst) and CDSOras5Connector._series_scorable(
            sea_level
        )
        return {
            "production_eligible": scorable,
            "features": CDSOras5Connector._features_from_series(sst, sea_level),
        }

    def fetch_features_many(
        self, payloads: list[Oras5PointRequest]
    ) -> list[dict[str, float] | None]:
        """Multi-point fetch: one vectorized nearest-neighbor select per store.

        All requested points are resolved in a single ``ds.sel`` call with
        point-indexed coordinate arrays per store, so the remote stores are
        windowed once per store instead of once per point. Falls back to
        per-point stub features when ``ORAS5_ZARR_URL`` is unset (CI / local /
        demo without credentials). Production refuses the stub path. The live
        read runs under the same bounded timeout / error translation as
        ``fetch_features``.

        Per-point result is ``None`` when the point has no scorable series
        (land-masked, out of coverage, or too short for the feature statistics)
        — callers decide how to surface the gap (batch prefetch turns it into a
        failed row so one bad point cannot abort the whole request).
        """
        if not payloads:
            return []
        if settings.oras5_zarr_url:
            return self._guarded(self._fetch_features_many_live, payloads)
        if settings.copernicus_cds_api_key:
            # CDS API jobs are queued server-side; one retrieve per point.
            return [self.fetch_features(payload) for payload in payloads]
        refuse_connector_stub_if_production(
            source="oras5",
            reason="ORAS5_ZARR_URL unset",
        )
        return [self._fallback_features() for _ in payloads]

    def _fetch_features_many_live(
        self, payloads: list[Oras5PointRequest]
    ) -> list[dict[str, float] | None]:
        """Zarr ARCO bulk read — runs inside ``_guarded`` (bounded timeout)."""
        sst_var, sea_level_var = self._resolve_vars()
        # Union of the stores covering ANY payload's window — a batch mixing
        # pre-2015 and post-2015 requests must open both stores, not just the
        # one the first payload needs. Order preserved (historical first).
        store_urls: list[str] = []
        for payload in payloads:
            for url in self._store_urls_for(payload.start_date, payload.end_date):
                if url not in store_urls:
                    store_urls.append(url)

        sst_parts: list[list[pd.Series]] = [[] for _ in payloads]
        sea_level_parts: list[list[pd.Series]] = [[] for _ in payloads]
        for url in store_urls:
            sst_list, sea_level_list = self._series_many_from_store(
                url, payloads, sst_var, sea_level_var
            )
            for i in range(len(payloads)):
                sst_parts[i].append(sst_list[i])
                sea_level_parts[i].append(sea_level_list[i])

        results: list[dict[str, float] | None] = []
        for sst_part, sea_level_part in zip(sst_parts, sea_level_parts):
            sst = self._concat_series(sst_part)
            sea_level = self._concat_series(sea_level_part)
            if not (self._series_scorable(sst) and self._series_scorable(sea_level)):
                results.append(None)
                continue
            results.append(self._features_from_series(sst, sea_level))
        return results

    @staticmethod
    def _series_scorable(series: pd.Series) -> bool:
        """Whether a point series is long enough for meaningful feature statistics.

        Mirrors the internal minimum: every feature statistic (trends, z-score,
        variability) returns a degenerate 0.0 below 24 monthly observations, so
        points with no data at all (land-masked / out of coverage) or fewer than
        one full seasonal cycle are treated as unscorable instead of silently
        scoring as a low-risk zero.
        """
        return len(series.dropna()) >= 24

    def _guarded(self, fn: Callable[..., T], *args: Any) -> T:
        """Run a live ORAS5 store read under a bounded wall-clock timeout.

        Both failure modes degrade to a clean ``DATA_SOURCE_UNAVAILABLE`` (503),
        matching the GEE connector's convention:

        - a slow/unreachable store read returns at ``oras5_fetch_timeout_seconds``
          instead of hanging the request worker indefinitely;
        - a missing variable / network error is translated to a sanitized 503
          (raw exception text is never echoed — it may contain URLs/headers).

        On timeout the executor is shut down with ``wait=False`` and
        ``cancel_futures=True``: a genuinely hung read leaves the worker thread
        abandoned (daemon) rather than blocking on executor exit — the subtlety
        the existing batch-row ``with ThreadPoolExecutor(...)`` pattern does not
        handle.
        """
        timeout = settings.oras5_fetch_timeout_seconds
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="oras5-fetch")
        future = pool.submit(fn, *args)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            raise GeoRiskApiError(
                code="DATA_SOURCE_UNAVAILABLE",
                message=f"ORAS5 store read exceeded the {timeout:g}s fetch timeout",
                status_code=503,
            ) from None
        except GeoRiskApiError:
            raise
        except Exception as exc:
            # Sanitised: surface only the exception type, never raw exception
            # text (may contain URLs/headers/tokens).
            raise GeoRiskApiError(
                code="DATA_SOURCE_UNAVAILABLE",
                message=f"ORAS5 store read failed: {type(exc).__name__}",
                status_code=503,
            ) from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def ocean_risk_score_from_features(self, features: dict[str, float]) -> int:
        score = 0

        if features["sst_trend_c_per_decade"] >= 0.20:
            score += 30
        elif features["sst_trend_c_per_decade"] >= 0.10:
            score += 20
        else:
            score += 10

        if features["sst_anomaly_zscore"] >= 2:
            score += 30
        elif features["sst_anomaly_zscore"] >= 1:
            score += 20
        else:
            score += 10

        if features["sea_level_trend_mm_per_year"] >= 3:
            score += 25
        elif features["sea_level_trend_mm_per_year"] >= 1.5:
            score += 15
        else:
            score += 5

        if features["ocean_variability_index"] >= 0.7:
            score += 15
        elif features["ocean_variability_index"] >= 0.4:
            score += 10
        else:
            score += 5

        return min(score, 100)

    def _timeseries_via_cdsapi(self, payload: Oras5PointRequest) -> tuple[pd.Series, pd.Series]:
        """Point time series via the CDS API ``reanalysis-oras5-timeseries`` dataset.

        Mirrors the canonical cdsapi retrieval (product_type consolidated /
        operational, location dict, CSV output). The CSV is parsed in-memory and
        sliced to the requested window. NOTE: CDS jobs are queued server-side —
        this path can take tens of seconds to minutes, so the Zarr ARCO path is
        preferred for the synchronous scoring API.
        """
        request = {
            "product_type": self._cdsapi_product_types_for(payload.start_date, payload.end_date),
            "variable": [_CDSAPI_SST_VARS[0], _CDSAPI_SEA_LEVEL_VARS[0]],
            "location": {"longitude": payload.longitude, "latitude": payload.latitude},
            "data_format": "csv",
        }
        try:
            result = self._cdsapi_client().retrieve(_CDSAPI_TIMESERIES_DATASET, request)
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                result.download(target=tmp_path)
                with open(tmp_path, "rb") as fh:
                    content = fh.read()
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except GeoRiskApiError:
            raise
        except Exception as exc:
            # Sanitised: never echo raw exception text (may contain URLs/headers)
            # into API responses; surface only the exception type (and HTTP
            # status when available) so consumers can diagnose without secrets.
            detail = type(exc).__name__
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status:
                detail = f"{detail} (HTTP {status})"
            raise GeoRiskApiError(
                code="DATA_SOURCE_UNAVAILABLE",
                message=f"ORAS5 CDS API request failed: {detail}",
                status_code=503,
            ) from exc

        sst, sea_level = self._parse_cdsapi_csv(
            content,
            sst_candidates=_CDSAPI_SST_VARS,
            sea_level_candidates=_CDSAPI_SEA_LEVEL_VARS,
        )
        if payload.start_date:
            start = str(payload.start_date)
            sst = sst.loc[start:]
            sea_level = sea_level.loc[start:]
        if payload.end_date:
            end = str(payload.end_date)
            sst = sst.loc[:end]
            sea_level = sea_level.loc[:end]
        return sst, sea_level

    def _cdsapi_product_types_for(self, start_date: date | None, end_date: date | None) -> list[str]:
        """CDS product types covering the requested window (consolidated/operational)."""
        start = start_date or date(1958, 1, 1)
        end = end_date or date.today()

        product_types: list[str] = []
        if start <= _ORAS5_HISTORICAL_END:
            product_types.append("consolidated")
        if end >= _ORAS5_OPERATIONAL_START:
            product_types.append("operational")
        return product_types or ["consolidated", "operational"]

    @staticmethod
    def _parse_cdsapi_csv(
        content: bytes,
        *,
        sst_candidates: list[str],
        sea_level_candidates: list[str],
    ) -> tuple[pd.Series, pd.Series]:
        df = pd.read_csv(io.BytesIO(content))
        date_col = next((c for c in _CDSAPI_DATE_COLUMNS if c in df.columns), None)
        if date_col is None:
            raise KeyError(
                f"ORAS5 CDS API CSV missing a date column "
                f"(expected one of {_CDSAPI_DATE_COLUMNS}); columns: {sorted(df.columns)}"
            )
        sst_col = CDSOras5Connector._find_cdsapi_col(df, sst_candidates, label="sea surface temperature")
        sea_level_col = CDSOras5Connector._find_cdsapi_col(
            df, sea_level_candidates, label="sea surface height"
        )

        dates = pd.to_datetime(df[date_col])
        sst = pd.Series(
            pd.to_numeric(df[sst_col], errors="coerce").to_numpy(), index=dates
        ).dropna()
        sea_level = pd.Series(
            pd.to_numeric(df[sea_level_col], errors="coerce").to_numpy(), index=dates
        ).dropna()
        sst.index = pd.to_datetime(sst.index)
        sea_level.index = pd.to_datetime(sea_level.index)
        return sst.sort_index(), sea_level.sort_index()

    @staticmethod
    def _find_cdsapi_col(df: pd.DataFrame, candidates: list[str], *, label: str) -> str:
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        raise KeyError(
            f"ORAS5 CDS API CSV missing {label} column "
            f"(expected one of {candidates}); columns: {sorted(df.columns)}"
        )

    @staticmethod
    @lru_cache(maxsize=1)
    def _cdsapi_client():
        key = (settings.copernicus_cds_api_key or "").strip()
        if not key:
            raise GeoRiskApiError(
                code="CDSAPI_CREDENTIALS_INVALID",
                message=(
                    "CDSAPI_KEY / COPERNICUS_CDS_API_KEY is not set; "
                    "configure it in the environment or ~/.cdsapirc"
                ),
                status_code=500,
            )
        # cdsapi 0.7 accepts both the legacy '<UID>:<APIKEY>' pair and the new
        # CDS single-key format (a bare UUID, verified live: the CDS API
        # authenticates it directly). Pass the key through unchanged.
        import cdsapi

        return cdsapi.Client(
            url=settings.copernicus_cds_url,
            key=key,
            quiet=True,
            progress=False,
        )

    @staticmethod
    def _features_from_series(sst: pd.Series, sea_level: pd.Series) -> dict[str, float]:
        return {
            "sst_trend_c_per_decade": CDSOras5Connector._linear_trend_per_decade(sst),
            "sst_anomaly_zscore": CDSOras5Connector._latest_zscore(sst),
            "sea_level_trend_mm_per_year": CDSOras5Connector._linear_trend_per_year(sea_level) * 1000,
            "ocean_variability_index": CDSOras5Connector._variability_index(sst),
        }

    def _resolve_vars(self) -> tuple[str, str]:
        """Resolve SST / sea-surface-height variable names from the primary store."""
        ds = self._open_dataset(settings.oras5_zarr_url)
        return (
            self._find_var(ds, _SST_VAR_CANDIDATES),
            self._find_var(ds, _SEA_LEVEL_VAR_CANDIDATES),
        )

    def _store_urls_for(
        self, start_date: date | None, end_date: date | None
    ) -> list[str]:
        """Ordered store URLs whose time coverage intersects the requested window.

        When only ``ORAS5_ZARR_URL`` is configured the historical store is always
        used (backwards compatible). With the operational store configured, windows
        before 2015 hit the historical store, windows from 2015 hit the operational
        store, and windows spanning the boundary hit both (merged downstream).
        """
        operational = settings.oras5_zarr_operational_url
        if not operational:
            return [settings.oras5_zarr_url]

        start = start_date or date(1958, 1, 1)
        end = end_date or date.today()

        urls: list[str] = []
        if start <= _ORAS5_HISTORICAL_END:
            urls.append(settings.oras5_zarr_url)
        if end >= _ORAS5_OPERATIONAL_START:
            urls.append(operational)
        return urls or [settings.oras5_zarr_url]

    def _point_series_from_store(
        self, url: str, var: str, payload: Oras5PointRequest
    ) -> pd.Series:
        ds = self._open_dataset(url)
        point = ds[var].sel(
            latitude=payload.latitude,
            longitude=payload.longitude,
            method="nearest",
        )
        if payload.start_date:
            point = point.sel(time=slice(str(payload.start_date), None))
        if payload.end_date:
            point = point.sel(time=slice(None, str(payload.end_date)))
        return self._to_series(point)

    def _series_many_from_store(
        self,
        url: str,
        payloads: list[Oras5PointRequest],
        sst_var: str,
        sea_level_var: str,
    ) -> tuple[list[pd.Series], list[pd.Series]]:
        """Point time series for every payload, one vectorized select per store."""
        ds = self._open_dataset(url)
        lats = xr.DataArray([p.latitude for p in payloads], dims="points")
        lons = xr.DataArray([p.longitude for p in payloads], dims="points")
        window = ds[[sst_var, sea_level_var]].sel(
            latitude=lats,
            longitude=lons,
            method="nearest",
        )

        sst_list: list[pd.Series] = []
        sea_level_list: list[pd.Series] = []
        for i, payload in enumerate(payloads):
            point = window.isel(points=i)
            if payload.start_date:
                point = point.sel(time=slice(str(payload.start_date), None))
            if payload.end_date:
                point = point.sel(time=slice(None, str(payload.end_date)))
            sst_list.append(self._to_series(point[sst_var]))
            sea_level_list.append(self._to_series(point[sea_level_var]))
        return sst_list, sea_level_list

    @staticmethod
    def _concat_series(parts: list[pd.Series]) -> pd.Series:
        """Merge per-store point series into one chronological series.

        Empty parts (window outside a store's coverage) are dropped; duplicate
        timestamps (overlapping store coverage) keep the first occurrence.
        """
        nonempty = [part for part in parts if not part.empty]
        if not nonempty:
            return pd.Series(dtype=float)
        if len(nonempty) == 1:
            return nonempty[0]
        combined = pd.concat(nonempty)
        combined = combined[~combined.index.duplicated(keep="first")]
        return combined.sort_index()

    @staticmethod
    @lru_cache(maxsize=2)
    def _open_dataset(zarr_url: str) -> xr.Dataset:
        store = CDSOras5Connector._build_zarr_store(zarr_url)
        if store is not None:
            # obstore path: retries on transient chunk reads (5xx, dropped
            # connections, timeouts). Mirrors the CDS ARCO advanced-access
            # example (plain open; consolidated metadata auto-handled by the
            # zarr v3 engine).
            return xr.open_zarr(store)
        storage_options: dict[str, Any] | None = None
        if settings.copernicus_cds_api_key:
            storage_options = {
                "headers": {"Authorization": f"Bearer {settings.copernicus_cds_api_key}"}
            }
        return xr.open_zarr(zarr_url, consolidated=True, storage_options=storage_options)

    @staticmethod
    def _build_zarr_store(zarr_url: str):
        """Retry-enabled read-only object store for http(s) Zarr URLs.

        Mirrors the CDS ARCO advanced-access pattern: obstore's ``HTTPStore``
        retries transient chunk reads with exponential backoff (5xx server
        errors, connection errors, dropped connections, timeouts), which the
        default fsspec ``storage_options`` path does not. Returns ``None`` when
        obstore is unavailable or the URL is not http(s), so the caller falls
        back to the default engine path.
        """
        if not zarr_url.startswith(("http://", "https://")):
            return None
        try:
            from obstore.store import HTTPStore
            from zarr.storage import ObjectStore
        except ImportError:
            return None

        headers: dict[str, str] = {}
        if settings.copernicus_cds_api_key:
            headers["Authorization"] = f"Bearer {settings.copernicus_cds_api_key}"

        retry_config: dict[str, Any] = {
            "max_retries": 5,
            "retry_timeout": timedelta(minutes=2),
            "backoff": {
                "init_backoff": timedelta(milliseconds=200),
                "max_backoff": timedelta(seconds=15),
                "base": 2,
            },
        }
        http_store = HTTPStore(
            zarr_url,
            client_options={"default_headers": headers},
            retry_config=retry_config,
        )
        return ObjectStore(http_store, read_only=True)

    @staticmethod
    def _find_var(ds: xr.Dataset, candidates: list[str]) -> str:
        available = set(ds.data_vars)

        for candidate in candidates:
            if candidate in available:
                return candidate

        raise KeyError(
            f"None of {candidates} found in ORAS5 dataset. "
            f"Available variables: {sorted(available)}"
        )

    @staticmethod
    def _to_series(data_array: xr.DataArray) -> pd.Series:
        series = data_array.to_series().dropna()

        if isinstance(series.index, pd.MultiIndex):
            # After point selection, only time should remain. This safely collapses
            # any remaining singleton dimensions.
            series = series.reset_index()
            time_col = "time"
            value_col = data_array.name
            series = pd.Series(series[value_col].to_numpy(), index=pd.to_datetime(series[time_col]))

        series.index = pd.to_datetime(series.index)
        return series.sort_index()

    @staticmethod
    def _linear_trend_per_decade(series: pd.Series) -> float:
        clean = series.dropna()
        if len(clean) < 24:
            return 0.0

        years = clean.index.year + (clean.index.month - 1) / 12
        slope_per_year = np.polyfit(years, clean.to_numpy(dtype=float), 1)[0]
        return float(slope_per_year * 10)

    @staticmethod
    def _linear_trend_per_year(series: pd.Series) -> float:
        clean = series.dropna()
        if len(clean) < 24:
            return 0.0

        years = clean.index.year + (clean.index.month - 1) / 12
        return float(np.polyfit(years, clean.to_numpy(dtype=float), 1)[0])

    @staticmethod
    def _latest_zscore(series: pd.Series) -> float:
        clean = series.dropna()
        if len(clean) < 24:
            return 0.0

        baseline = clean.iloc[:-1]
        latest = clean.iloc[-1]

        std = baseline.std()
        if std == 0 or np.isnan(std):
            return 0.0

        return float((latest - baseline.mean()) / std)

    @staticmethod
    def _variability_index(series: pd.Series) -> float:
        clean = series.dropna()
        if len(clean) < 24:
            return 0.0

        std = clean.std()
        if std == 0 or np.isnan(std):
            # Flat / constant series (e.g. a land-snapped cell) → no variability.
            return 0.0

        rolling = clean.rolling(window=12).std().dropna()
        if rolling.empty:
            return 0.0

        value = rolling.iloc[-1] / std
        if np.isnan(value):
            return 0.0
        return float(np.clip(value, 0, 1))

    @staticmethod
    def _fallback_features() -> dict[str, float]:
        return {
            "sst_trend_c_per_decade": 0.21,
            "sst_anomaly_zscore": 1.4,
            "sea_level_trend_mm_per_year": 3.1,
            "ocean_variability_index": 0.58,
        }

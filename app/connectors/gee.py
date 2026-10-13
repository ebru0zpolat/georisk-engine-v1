from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.core.data_source_registry import (
    GEE_S5P_NO2_BAND,
    GEE_S5P_NO2_DATASET,
    GEE_VIIRS_NTL_BAND,
    GEE_VIIRS_NTL_DATASET,
)
from app.core.exceptions import GeoRiskApiError
from app.core.runtime_mode import refuse_connector_stub_if_production
from app.schemas.baseline import baseline_comparison_from_means
from app.scoring.baseline import score_from_relative_increase


@dataclass(frozen=True)
class GeePointRequest:
    latitude: float
    longitude: float
    radius_km: float = 10
    start_date: date | None = None
    end_date: date | None = None
    baseline_start_date: date | None = None
    baseline_end_date: date | None = None


class GeeConnector:
    VIIRS_DATASET = GEE_VIIRS_NTL_DATASET
    VIIRS_BAND = GEE_VIIRS_NTL_BAND

    S5P_NO2_DATASET = GEE_S5P_NO2_DATASET
    S5P_NO2_BAND = GEE_S5P_NO2_BAND

    def _period_means(self, ee: object, region: object, start: str, end: str) -> tuple[float, float]:
        night_lights = (
            ee.ImageCollection(self.VIIRS_DATASET)
            .filterDate(start, end)
            .select(self.VIIRS_BAND)
            .mean()
            .reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=region,
                scale=500,
                maxPixels=1e9,
            )
            .get(self.VIIRS_BAND)
        )

        no2 = (
            ee.ImageCollection(self.S5P_NO2_DATASET)
            .filterDate(start, end)
            .select(self.S5P_NO2_BAND)
            .mean()
            .reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=region,
                scale=1000,
                maxPixels=1e9,
            )
            .get(self.S5P_NO2_BAND)
        )

        result = ee.Dictionary({"night_lights_mean": night_lights, "no2_mean": no2}).getInfo()

        return (
            float(result.get("night_lights_mean") or 0),
            float(result.get("no2_mean") or 0),
        )

    def _mean_image(self, ee: object, dataset: str, band: str, start: str, end: str) -> object:
        return ee.ImageCollection(dataset).filterDate(start, end).select(band).mean()

    def _reduce_regions_means(
        self,
        ee: object,
        image: object,
        collection: object,
        *,
        scale: int,
        n: int,
    ) -> list[float]:
        """One ``reduceRegions`` RPC for *n* buffered points; returns means ordered by ``idx``."""
        raw = image.reduceRegions(
            collection=collection,
            reducer=ee.Reducer.mean(),
            scale=scale,
        ).getInfo()
        means = [0.0] * n
        for feature in raw.get("features", []):
            props = feature.get("properties", {})
            idx = int(props.get("idx", -1))
            if 0 <= idx < n:
                means[idx] = float(props.get("mean") or 0)
        return means

    def _region_collection(self, ee: object, payloads: list[GeePointRequest]) -> object:
        features = [
            ee.Feature(
                ee.Geometry.Point([p.longitude, p.latitude]).buffer(p.radius_km * 1000),
                {"idx": i},
            )
            for i, p in enumerate(payloads)
        ]
        return ee.FeatureCollection(features)

    def fetch_features_many(self, payloads: list[GeePointRequest]) -> list[dict[str, Any]]:
        """Multi-point fetch via ``reduceRegions``: one RPC per band/window for the whole set.

        All payloads must share the same current/baseline date windows (the bulk
        coalesce facade guarantees this). Falls back to per-point stub features
        when GEE is disabled or the project id is missing (CI / local / demo).
        Production refuses the stub path.
        """
        if not payloads:
            return []
        if not settings.gee_enabled or not settings.gee_project:
            refuse_connector_stub_if_production(
                source="gee",
                reason="GEE_ENABLED or GEE_PROJECT unset",
            )
            return [self._fallback_features() for _ in payloads]

        try:
            ee = self._ee()
            n = len(payloads)
            collection = self._region_collection(ee, payloads)

            first = payloads[0]
            cur_start = str(first.start_date or date(2023, 1, 1))
            cur_end = str(first.end_date or date(2024, 1, 1))

            nl_image = self._mean_image(ee, self.VIIRS_DATASET, self.VIIRS_BAND, cur_start, cur_end)
            no2_image = self._mean_image(ee, self.S5P_NO2_DATASET, self.S5P_NO2_BAND, cur_start, cur_end)
            nl_cur = self._reduce_regions_means(ee, nl_image, collection, scale=500, n=n)
            no2_cur = self._reduce_regions_means(ee, no2_image, collection, scale=1000, n=n)

            has_baseline = (
                first.baseline_start_date is not None and first.baseline_end_date is not None
            )
            nl_base: list[float] | None = None
            no2_base: list[float] | None = None
            if has_baseline:
                b_start = str(first.baseline_start_date)
                b_end = str(first.baseline_end_date)
                nl_b_image = self._mean_image(ee, self.VIIRS_DATASET, self.VIIRS_BAND, b_start, b_end)
                no2_b_image = self._mean_image(ee, self.S5P_NO2_DATASET, self.S5P_NO2_BAND, b_start, b_end)
                nl_base = self._reduce_regions_means(ee, nl_b_image, collection, scale=500, n=n)
                no2_base = self._reduce_regions_means(ee, no2_b_image, collection, scale=1000, n=n)

            results: list[dict[str, Any]] = []
            for i in range(n):
                out: dict[str, Any] = {
                    "night_lights_mean": nl_cur[i],
                    "no2_mean": no2_cur[i],
                    "ndvi_mean": None,
                    "soil_moisture_proxy": None,
                    "night_lights_baseline_mean": None,
                    "no2_baseline_mean": None,
                    "night_lights_relative_deviation": None,
                    "no2_relative_deviation": None,
                    "night_lights_comparison": None,
                    "no2_comparison": None,
                }
                if nl_base is not None and no2_base is not None:
                    eps_nl = max(abs(nl_base[i]), 1e-6)
                    eps_no2 = max(abs(no2_base[i]), 1e-12)
                    out["night_lights_baseline_mean"] = nl_base[i]
                    out["no2_baseline_mean"] = no2_base[i]
                    out["night_lights_relative_deviation"] = (nl_cur[i] - nl_base[i]) / eps_nl
                    out["no2_relative_deviation"] = (no2_cur[i] - no2_base[i]) / eps_no2
                    out["night_lights_comparison"] = baseline_comparison_from_means(
                        nl_cur[i], nl_base[i], baseline_epsilon=1e-6
                    )
                    out["no2_comparison"] = baseline_comparison_from_means(
                        no2_cur[i], no2_base[i], baseline_epsilon=1e-12
                    )
                results.append(out)
            return results
        except GeoRiskApiError:
            raise
        except Exception as e:
            raise GeoRiskApiError(
                code="DATA_SOURCE_UNAVAILABLE",
                message="GEE temporarily unavailable",
                status_code=503,
            ) from e

    def fetch_baseline_features_many(self, payloads: list[GeePointRequest]) -> list[dict[str, Any]]:
        """Bulk variant of ``fetch_baseline_features`` (same {current, baseline} bundle shape)."""
        bundles: list[dict[str, Any]] = []
        for current in self.fetch_features_many(payloads):
            nl_b = current.get("night_lights_baseline_mean")
            no2_b = current.get("no2_baseline_mean")
            if nl_b is not None and no2_b is not None:
                baseline: dict[str, Any] = {
                    "night_lights_mean": float(nl_b),
                    "no2_mean": float(no2_b),
                }
            else:
                baseline = {
                    "night_lights_mean": 8.0,
                    "no2_mean": 0.00007,
                }
            bundles.append({"current": current, "baseline": baseline})
        return bundles

    def fetch_features(self, payload: GeePointRequest) -> dict[str, Any]:
        if not settings.gee_enabled or not settings.gee_project:
            refuse_connector_stub_if_production(
                source="gee",
                reason="GEE_ENABLED or GEE_PROJECT unset",
            )
            return self._fallback_features()

        try:
            ee = self._ee()
            point = ee.Geometry.Point([payload.longitude, payload.latitude])
            region = point.buffer(payload.radius_km * 1000)

            cur_start = str(payload.start_date or date(2023, 1, 1))
            cur_end = str(payload.end_date or date(2024, 1, 1))
            nl_cur, no2_cur = self._period_means(ee, region, cur_start, cur_end)

            out: dict[str, Any] = {
                "night_lights_mean": nl_cur,
                "no2_mean": no2_cur,
                "ndvi_mean": None,
                "soil_moisture_proxy": None,
                "night_lights_baseline_mean": None,
                "no2_baseline_mean": None,
                "night_lights_relative_deviation": None,
                "no2_relative_deviation": None,
                "night_lights_comparison": None,
                "no2_comparison": None,
            }

            if payload.baseline_start_date is not None and payload.baseline_end_date is not None:
                b_start = str(payload.baseline_start_date)
                b_end = str(payload.baseline_end_date)
                nl_b, no2_b = self._period_means(ee, region, b_start, b_end)
                out["night_lights_baseline_mean"] = nl_b
                out["no2_baseline_mean"] = no2_b
                eps_nl = max(abs(nl_b), 1e-6)
                eps_no2 = max(abs(no2_b), 1e-12)
                out["night_lights_relative_deviation"] = (nl_cur - nl_b) / eps_nl
                out["no2_relative_deviation"] = (no2_cur - no2_b) / eps_no2
                out["night_lights_comparison"] = baseline_comparison_from_means(
                    nl_cur, nl_b, baseline_epsilon=1e-6
                )
                out["no2_comparison"] = baseline_comparison_from_means(
                    no2_cur, no2_b, baseline_epsilon=1e-12
                )

            return out
        except GeoRiskApiError:
            raise
        except Exception as e:
            raise GeoRiskApiError(
                code="DATA_SOURCE_UNAVAILABLE",
                message="GEE temporarily unavailable",
                status_code=503,
            ) from e

    def fetch_baseline_features(self, payload: GeePointRequest) -> dict[str, Any]:
        current = self.fetch_features(payload)
        nl_b = current.get("night_lights_baseline_mean")
        no2_b = current.get("no2_baseline_mean")
        if nl_b is not None and no2_b is not None:
            baseline: dict[str, Any] = {
                "night_lights_mean": float(nl_b),
                "no2_mean": float(no2_b),
            }
        else:
            baseline = {
                "night_lights_mean": 8.0,
                "no2_mean": 0.00007,
            }

        return {
            "current": current,
            "baseline": baseline,
        }

    def industrial_activity_score_from_features(self, features: dict[str, Any]) -> int:
        dev = features.get("night_lights_relative_deviation")
        if dev is not None:
            return score_from_relative_increase(float(dev))

        value = float(features["night_lights_mean"] or 0)

        if value >= 20:
            return 85
        if value >= 10:
            return 70
        if value >= 3:
            return 50
        if value >= 1:
            return 30
        return 15

    def pollution_proxy_score_from_features(self, features: dict[str, Any]) -> int:
        dev = features.get("no2_relative_deviation")
        if dev is not None:
            return score_from_relative_increase(float(dev))

        value = float(features["no2_mean"] or 0)

        if value >= 0.0002:
            return 85
        if value >= 0.0001:
            return 70
        if value >= 0.00005:
            return 50
        if value > 0:
            return 30
        return 15

    @staticmethod
    @lru_cache(maxsize=1)
    def _ee():
        import ee

        credentials = None
        if settings.gee_service_account_json:
            try:
                account = json.loads(settings.gee_service_account_json)
            except json.JSONDecodeError as exc:
                raise GeoRiskApiError(
                    code="GEE_CREDENTIALS_INVALID",
                    message="GEE_SERVICE_ACCOUNT_JSON is not valid JSON",
                    status_code=500,
                ) from exc
            email = account.get("client_email")
            if not email:
                raise GeoRiskApiError(
                    code="GEE_CREDENTIALS_INVALID",
                    message="GEE_SERVICE_ACCOUNT_JSON is missing client_email",
                    status_code=500,
                ) from None
            credentials = ee.ServiceAccountCredentials(email, key_data=settings.gee_service_account_json)

        ee.Initialize(project=settings.gee_project, credentials=credentials)
        return ee

    @staticmethod
    def _fallback_features() -> dict[str, Any]:
        return {
            "night_lights_mean": 12.5,
            "no2_mean": 0.00011,
            "ndvi_mean": None,
            "soil_moisture_proxy": None,
            "night_lights_baseline_mean": None,
            "no2_baseline_mean": None,
            "night_lights_relative_deviation": None,
            "no2_relative_deviation": None,
            "night_lights_comparison": None,
            "no2_comparison": None,
        }

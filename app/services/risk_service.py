import uuid
from datetime import datetime, timezone

from app.connectors import (
    CDSOras5Connector,
    GeeConnector,
    GeePointRequest,
    Oras5PointRequest,
)
from app.connectors.bulk_fetch import BulkAssetPoint, BulkFeatureRow, fetch_features_many
from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.core.runtime_mode import connector_data_mode, production_eligible_for_response
from app.schemas.baseline import baseline_comparison_from_means
from app.schemas.gee import GeeBaselineFeatures, GeeFeatures
from app.schemas.ocean import OceanFeatures
from app.schemas.risk import (
    CompoundDriverScores,
    RiskBatchRequest,
    RiskBatchResponse,
    RiskScoreMeta,
    RiskScoreRequest,
    RiskScoreResponse,
)
from app.services.audit_service import AuditService
from app.services.industrial_verification_ref import build_industrial_verification_ref
from app.services.risk_batch_pipeline import execute_sync_batch
from app.services.snapshot_from_score import register_score_snapshot
from app.scoring.agriculture_surface import attach_agriculture_proxies_to_gee_dict
from app.scoring.baseline import (
    coastal_exposure_score,
    emission_zscore_from_percent_change,
    is_emission_anomaly,
    percent_change,
    score_change,
)
from app.scoring.risk_score import (
    compute_component_scores,
    compute_overall_score,
    confidence_from_drivers,
    derive_flags,
    interpretation_text,
    risk_band,
    weighted_risk_from_components,
)


class RiskService:
    def __init__(
        self,
        audit: AuditService | None = None,
        oras5: CDSOras5Connector | None = None,
        gee: GeeConnector | None = None,
    ) -> None:
        self.audit = audit or AuditService()
        self.oras5 = oras5 or CDSOras5Connector()
        self.gee = gee or GeeConnector()

    def score(
        self,
        payload: RiskScoreRequest,
        *,
        prefetched: BulkFeatureRow | None = None,
    ) -> RiskScoreResponse:
        if prefetched is not None:
            if prefetched.error is not None:
                # Per-point data gap detected during bulk prefetch (e.g. no
                # scorable ORAS5 series at this cell). Fail this row only; the
                # batch pipeline catches it into the row-level partial-success
                # contract so valid rows in the same request still succeed.
                raise GeoRiskApiError(
                    code=str(prefetched.error.get("code") or "DATA_SOURCE_UNAVAILABLE"),
                    message=str(prefetched.error.get("message") or "ORAS5 data unavailable"),
                    status_code=503,
                )
            features_dict = prefetched.oras5_features
            gee_bundle = prefetched.gee_bundle
        else:
            oras5_request = Oras5PointRequest(
                latitude=payload.latitude,
                longitude=payload.longitude,
                start_date=payload.start_date,
                end_date=payload.end_date,
            )
            features_dict = self.oras5.fetch_features(oras5_request)
            gee_request = GeePointRequest(
                latitude=payload.latitude,
                longitude=payload.longitude,
                radius_km=payload.radius_km,
                start_date=payload.start_date,
                end_date=payload.end_date,
                baseline_start_date=payload.baseline_start_date or settings.climate_baseline_start,
                baseline_end_date=payload.baseline_end_date or settings.climate_baseline_end,
            )
            gee_bundle = self.gee.fetch_baseline_features(gee_request)

        ocean = self.oras5.ocean_risk_score_from_features(features_dict)
        ocean_features = OceanFeatures.model_validate(features_dict)
        gee_raw = attach_agriculture_proxies_to_gee_dict(dict(gee_bundle["current"]), payload)
        stub = gee_bundle["baseline"]
        gee_baseline = GeeBaselineFeatures(
            night_lights=baseline_comparison_from_means(
                float(gee_raw["night_lights_mean"] or 0),
                float(stub["night_lights_mean"] or 0),
                baseline_epsilon=1e-6,
            ),
            no2=baseline_comparison_from_means(
                float(gee_raw["no2_mean"] or 0),
                float(stub["no2_mean"] or 0),
                baseline_epsilon=1e-12,
            ),
        )
        industrial_change = percent_change(
            float(gee_raw["night_lights_mean"] or 0),
            float(stub["night_lights_mean"] or 0),
        )
        industrial = score_change(industrial_change)
        pollution = self.gee.pollution_proxy_score_from_features(gee_raw)
        gee_features = GeeFeatures.model_validate(gee_raw)

        base_components = compute_component_scores(payload)
        components = base_components.model_copy(
            update={
                "ocean": ocean,
                "industrial": industrial,
                "pollution": pollution,
            }
        )
        overall = compute_overall_score(components)
        risk_score, heat, water_stress, climate = weighted_risk_from_components(
            components, payload.preset_id
        )
        compound_scores = CompoundDriverScores(
            heat=heat, water_stress=water_stress, climate=climate
        )
        confidence = confidence_from_drivers(heat, water_stress, climate)
        band = risk_band(overall)
        flags = derive_flags(components)
        interpretation = interpretation_text(overall, band, flags)
        no2_zscore = emission_zscore_from_percent_change(gee_baseline.no2.percent_change)
        gee_baseline = gee_baseline.model_copy(
            update={"no2": gee_baseline.no2.model_copy(update={"z_score": no2_zscore})}
        )
        anomaly_flag = is_emission_anomaly(no2_zscore)
        coastal_exposure = coastal_exposure_score(
            ocean_features.sea_level_trend_mm_per_year,
            ocean_features.sst_anomaly_zscore,
        )
        audit_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc)
        industrial_verification = (
            build_industrial_verification_ref(
                audit_id=audit_id,
                latitude=payload.latitude,
                longitude=payload.longitude,
            )
            if payload.include_industrial_verification_ref
            else None
        )
        data_version = settings.risk_score_model_version
        if prefetched is not None:
            data_version = f"{data_version}+bulk:{prefetched.coalesce_mode}"
        response = RiskScoreResponse(
            asset_name=payload.asset_name,
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius_km=payload.radius_km,
            sector=payload.sector,
            preset_id=payload.preset_id,
            overall_score=overall,
            risk_score=risk_score,
            scores=compound_scores,
            confidence=confidence,
            risk_band=band,
            components=components,
            ocean_features=ocean_features,
            gee_features=gee_features,
            gee_baseline=gee_baseline,
            flags=flags,
            interpretation=interpretation,
            audit_id=audit_id,
            generated_at=generated_at,
            meta=RiskScoreMeta(
                updated_at=generated_at,
                resolution_km=payload.radius_km,
                data_version=data_version,
            ),
            industrial_verification=industrial_verification,
            emission_zscore=no2_zscore,
            anomaly_flag=anomaly_flag,
            coastal_exposure_score=coastal_exposure,
            data_mode=connector_data_mode(settings),
            production_eligible=production_eligible_for_response(settings),
        )
        self.audit.log(
            audit_id=response.audit_id,
            endpoint="/v1/risk/score",
            request=payload.model_dump_json(),
            response=response.model_dump_json(),
        )
        register_score_snapshot(response)
        return response

    def batch_score(self, payload: RiskBatchRequest) -> RiskBatchResponse:
        """Prefetch connector features once per batch, then score rows without re-fetching."""
        valid_assets = [
            a for a in payload.assets if -90.0 <= a.lat <= 90.0 and -180.0 <= a.lon <= 180.0
        ]
        prefetch_rows = fetch_features_many(
            [
                BulkAssetPoint(
                    asset_id=a.id,
                    latitude=a.lat,
                    longitude=a.lon,
                    radius_km=payload.radius_km,
                )
                for a in valid_assets
            ],
            oras5=self.oras5,
            gee=self.gee,
            baseline_start_date=settings.climate_baseline_start,
            baseline_end_date=settings.climate_baseline_end,
        )
        by_id: dict[str, BulkFeatureRow] = {r.asset_id: r for r in prefetch_rows}

        def score_one(req: RiskScoreRequest) -> RiskScoreResponse:
            return self.score(req, prefetched=by_id.get(req.asset_name))

        return execute_sync_batch(
            payload,
            score_one,
            row_timeout_seconds=settings.risk_score_row_timeout_seconds,
        )

    def score_location(self, payload: RiskScoreRequest) -> RiskScoreResponse:
        return self.score(payload)

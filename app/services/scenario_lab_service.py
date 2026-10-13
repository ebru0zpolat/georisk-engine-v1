from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from app.core.exceptions import GeoRiskApiError
from app.schemas.scenario import (
    HazardResultDetail,
    ScenarioAuditContext,
    ScenarioHazard,
    ScenarioPropagation,
    ScenarioRunRequest,
    ScenarioRunResponse,
    ScenarioRunStatus,
    ScenarioScoringSummary,
    ScenarioShocks,
)
from app.geo.interfaces import derive_point_geometry_hash
from app.scoring.scenario_coefficients import lookup_hazard_multiplier
from app.scoring.actor_graph_loader import get_default_actor_graph, resolve_origin_node_id
from app.scoring.propagation import propagate_actor_tree
from app.scoring.propagation_adapter import propagation_to_scenario_response
from app.scoring.scenario_score import ScenarioScoreResult, compute_scenario_score
from app.services.asset_snapshot_store import AssetSnapshot, get_snapshot

AUDIT_DISCLAIMER = (
    "v1 Deterministic Engine - Results based on core baseline snapshot."
)


class ScenarioLabService:
    def run(self, body: ScenarioRunRequest) -> ScenarioRunResponse:
        asset_key = str(body.asset_id)
        snapshot = get_snapshot(asset_key)
        if snapshot is None:
            raise GeoRiskApiError(
                "asset_not_found",
                (
                    f"No GeoRisk snapshot for asset_id {body.asset_id}. "
                    "Run POST /v1/risk/preview or POST /v1/risk/score first; "
                    "use the returned audit_id as asset_id."
                ),
                status_code=404,
            )

        pathway = body.scenario_config.pathway.value
        horizon = body.scenario_config.target_year
        hazard_ids = [h.value for h in body.scenario_config.hazards]

        geometry_hash = snapshot.asset_geometry_hash or derive_point_geometry_hash(
            latitude=snapshot.latitude,
            longitude=snapshot.longitude,
        )
        if body.asset_geometry_hash and body.asset_geometry_hash != geometry_hash:
            raise GeoRiskApiError(
                "geometry_hash_mismatch",
                "asset_geometry_hash does not match Core snapshot.",
                status_code=422,
            )
        if body.data_snapshot_id and body.data_snapshot_id != snapshot.data_snapshot_id:
            raise GeoRiskApiError(
                "data_snapshot_mismatch",
                "data_snapshot_id does not match Core snapshot.",
                status_code=422,
            )

        score_result = compute_scenario_score(
            asset_id=asset_key,
            model_version=snapshot.model_version,
            data_snapshot_id=snapshot.data_snapshot_id,
            baseline_score=snapshot.overall_score,
            components=snapshot.components,
            pathway=pathway,
            horizon=horizon,
            hazards=hazard_ids,
            latitude=snapshot.latitude,
            longitude=snapshot.longitude,
            radius_km=snapshot.radius_km,
            sector=snapshot.sector,
            uses_connector_fallback=snapshot.uses_connector_fallback,
            geometry_hash_verified=True,
        )
        scenario_scoring = ScenarioScoringSummary.model_validate(score_result.__dict__)

        hazard_results: dict[str, HazardResultDetail] = {}
        hazard_severities: list[float] = []

        for hazard in body.scenario_config.hazards:
            rp_map: dict[str, float] = {}
            severities: list[float] = []
            affected_values: list[float] = []

            for rp in body.parameters.return_period:
                severity, affected = self._indicative_metrics(
                    snapshot=snapshot,
                    hazard=hazard,
                    pathway=pathway,
                    target_year=horizon,
                    return_period=rp,
                )
                severities.append(severity)
                affected_values.append(affected)
                rp_map[f"{rp}y"] = round(
                    min(1.0, severity * (0.55 + 0.45 * min(1.0, rp / 100.0))),
                    2,
                )

            peak_severity = max(severities) if severities else 0.0
            hazard_severities.append(peak_severity)
            hazard_results[hazard.value] = HazardResultDetail(
                severity_index=round(peak_severity, 2),
                affected_fraction=round(
                    sum(affected_values) / max(len(affected_values), 1),
                    2,
                ),
                return_periods=rp_map,
            )

        shocks = self._correlated_shocks(
            snapshot,
            body.scenario_config.hazards,
            hazard_severities,
            pathway,
            scenario_scoring.scenario_delta_points,
        )
        propagation = self._impact_propagation(snapshot, score_result)
        scenario_id = self._scenario_id(snapshot.audit_id, horizon)

        return ScenarioRunResponse(
            scenario_id=scenario_id,
            status=ScenarioRunStatus.COMPLETED,
            scenario_scoring=scenario_scoring,
            hazard_results=hazard_results,
            shocks=shocks,
            propagation=propagation,
            audit_context=ScenarioAuditContext(
                linked_audit_ids=[self._audit_label(snapshot.audit_id)],
                disclaimer=AUDIT_DISCLAIMER,
            ),
        )

    @staticmethod
    def _scenario_id(audit_id: str, target_year: int) -> str:
        digest = hashlib.sha256(f"{audit_id}|{target_year}".encode()).hexdigest()
        suffix = chr(ord("a") + (int(digest[:2], 16) % 26))
        return f"scen_{int(digest[2:6], 16) % 10000:04d}_{suffix}"

    @staticmethod
    def _audit_label(audit_id: str) -> str:
        year = datetime.now(timezone.utc).year
        short = audit_id.replace("-", "")[:6].upper()
        return f"AUD-{year}-{short}"

    @staticmethod
    def _facility_node_id(snapshot: AssetSnapshot) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", snapshot.asset_name.lower()).strip("_")
        return slug[:40] or "facility_a"

    @staticmethod
    def _seed(*parts: str) -> float:
        digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF

    def _indicative_metrics(
        self,
        *,
        snapshot: AssetSnapshot,
        hazard: ScenarioHazard,
        pathway: str,
        target_year: int,
        return_period: int,
    ) -> tuple[float, float]:
        hazard_bias = {
            ScenarioHazard.FLOOD: snapshot.components.get("ocean", 50),
            ScenarioHazard.DROUGHT: snapshot.components.get("agriculture", 50),
            ScenarioHazard.WILDFIRE: snapshot.components.get("land", 50),
            ScenarioHazard.HEAT: snapshot.components.get("pollution", 50),
            ScenarioHazard.STORM_SURGE: snapshot.components.get("ocean", 50),
            ScenarioHazard.CYCLONE: snapshot.components.get("ocean", 50),
        }.get(hazard, snapshot.overall_score)

        mult = lookup_hazard_multiplier(hazard.value, pathway, target_year)
        rp_factor = 0.55 + 0.45 * min(1.0, return_period / 100.0)
        severity = min(1.0, (hazard_bias / 100.0) * mult * rp_factor * 0.95)
        affected = min(1.0, 0.08 + 0.5 * severity * (return_period / 100.0))
        return severity, affected

    def _correlated_shocks(
        self,
        snapshot: AssetSnapshot,
        hazards: list[ScenarioHazard],
        severities: list[float],
        pathway: str,
        scenario_delta_points: int,
    ) -> ScenarioShocks:
        events: list[str] = []
        if any(s > 0.55 for s in severities):
            events.append("supply_chain_disruption")
        if ScenarioHazard.DROUGHT in hazards or ScenarioHazard.HEAT in hazards:
            events.append("energy_price_spike")
        if ScenarioHazard.FLOOD in hazards or ScenarioHazard.STORM_SURGE in hazards:
            events.append("logistics_corridor_stress")
        if "SSP5" in pathway and not events:
            events.append("climate_tail_risk_amplification")
        if not events:
            events.append("operational_stress_monitoring")

        systemic = min(
            1.0,
            round(
                (sum(severities) / max(len(severities), 1)) * 0.5
                + max(0, scenario_delta_points) / 40.0
                + 0.05 * self._seed(snapshot.audit_id, "systemic", pathway),
                2,
            ),
        )
        return ScenarioShocks(correlated_events=events, systemic_risk_score=systemic)

    def _impact_propagation(
        self,
        snapshot: AssetSnapshot,
        score_result: ScenarioScoreResult,
    ) -> ScenarioPropagation:
        loaded = get_default_actor_graph()
        facility_node = self._facility_node_id(snapshot)
        origin_node_id = resolve_origin_node_id(
            snapshot,
            loaded.metadata,
            facility_slug=facility_node,
        )
        propagation_result = propagate_actor_tree(
            origin=score_result,
            origin_node_id=origin_node_id,
            graph=loaded.graph,
            node_baselines=loaded.metadata.baselines,
        )
        return propagation_to_scenario_response(
            propagation_result,
            facility_node=facility_node,
            node_labels=loaded.metadata.labels,
        )

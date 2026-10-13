"""Admission and release gates (spec §7.2, §13).

Two layers:

* :func:`evaluate_kpi_gates` — the KPI admission gate that lets a candidate KPI reach
  ``reviewer_ready`` only if the mandatory gates pass (spec §7.2).
* :func:`evaluate_release_gates` — the fail-closed release gate that blocks a whole pack
  from reaching ``reviewer_ready`` (spec §13).

Both fail closed: uncertainty resolves to a blocking outcome, never a silent pass.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.packs.tr.sustainable_finance import regulatory_source as rs
from app.packs.tr.sustainable_finance.claims import ClaimScanResult
from app.packs.tr.sustainable_finance.physical_risk import (
    KPISuitability,
    is_available_for_trigger_use,
    lookup_kpi_suitability,
)
from app.packs.tr.sustainable_finance.routes import RegulatoryRoute, role_separation_ok
from app.packs.tr.sustainable_finance.schemas import EvidencePackInput, KPIRecord


class GateOutcome(str, Enum):
    passed = "pass"
    conditional = "conditional"
    failed = "fail"


class KPIGateResult(BaseModel):
    kpi_id: str
    gates: dict[str, GateOutcome] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @property
    def reviewer_ready(self) -> bool:
        return all(o is not GateOutcome.failed for o in self.gates.values())

    @property
    def has_conditional(self) -> bool:
        return any(o is GateOutcome.conditional for o in self.gates.values())

    def failed_gates(self) -> list[str]:
        return [name for name, o in self.gates.items() if o is GateOutcome.failed]


def evaluate_kpi_gates(kpi: KPIRecord) -> KPIGateResult:
    """Evaluate the seven KPI admission gates (spec §7.2)."""
    gates: dict[str, GateOutcome] = {}
    notes: list[str] = []

    # 1. Materiality — link to core business + material sector issue.
    if (
        (kpi.strategy_materiality_link and kpi.strategy_materiality_link.strip())
        and (kpi.material_sector_issue and kpi.material_sector_issue.strip())
    ):
        gates["materiality"] = GateOutcome.passed
    else:
        gates["materiality"] = GateOutcome.failed
        notes.append("materiality: missing strategy link or material sector issue")

    # 2. Issuer control — documented management lever; reject a pure external hazard metric.
    if kpi.is_pure_external_hazard:
        gates["issuer_control"] = GateOutcome.failed
        notes.append("issuer_control: pure external hazard metric is not issuer-controlled")
    elif kpi.controlled_management_lever and kpi.controlled_management_lever.strip():
        gates["issuer_control"] = GateOutcome.passed
    else:
        gates["issuer_control"] = GateOutcome.failed
        notes.append("issuer_control: no documented management lever")

    # 3. Measurement — stable unit / boundary / numerator (+ denominator for intensity).
    gates["measurement"] = (
        GateOutcome.passed if kpi.has_measurement_definition() else GateOutcome.failed
    )
    if gates["measurement"] is GateOutcome.failed:
        notes.append("measurement: ambiguous or incomplete unit/boundary/numerator definition")

    # 4. Verification — source records / reproducible computation available to a reviewer.
    if (kpi.verification_evidence and kpi.verification_evidence.strip()) or (
        kpi.responsible_external_reviewer and kpi.responsible_external_reviewer.strip()
    ):
        gates["verification"] = GateOutcome.passed
    else:
        gates["verification"] = GateOutcome.failed
        notes.append("verification: no source records / responsible reviewer for reproduction")

    # 5. Comparability — external reference/peer/sector or stable internal series (conditional).
    if kpi.external_benchmark and kpi.external_benchmark.strip():
        gates["comparability"] = GateOutcome.passed
    else:
        gates["comparability"] = GateOutcome.conditional
        notes.append("comparability: no defensible external comparison — marked conditional")

    # 6. Historical evidence — prefer disclosed; else ≥3y externally verified (conditional gap).
    verified_years = kpi.externally_verified_history_years()
    if verified_years >= rs.MIN_HISTORICAL_KPI_YEARS:
        gates["historical_evidence"] = GateOutcome.passed
    else:
        gates["historical_evidence"] = GateOutcome.conditional
        notes.append(
            f"historical_evidence: only {verified_years} externally verified year(s) "
            f"(< {rs.MIN_HISTORICAL_KPI_YEARS}) — disclose the gap"
        )

    # 7. Data & model stability — version-locked source/scenario/methodology + recalculation.
    stable = (
        bool(kpi.methodology_versions)
        and bool(kpi.dataset_versions)
        and bool(kpi.recalculation_policy and kpi.recalculation_policy.strip())
    )
    gates["data_and_model_stability"] = GateOutcome.passed if stable else GateOutcome.failed
    if not stable:
        notes.append(
            "data_and_model_stability: missing methodology/dataset version lock or recalculation policy"
        )

    # Physical-risk policy overlay (spec §8): trigger use of a non-eligible metric fails.
    if kpi.physical_risk_candidate_id:
        row = lookup_kpi_suitability(kpi.physical_risk_candidate_id)
        if row is None:
            gates["physical_risk_policy"] = GateOutcome.failed
            notes.append(
                f"physical_risk_policy: unknown candidate '{kpi.physical_risk_candidate_id}' — fail closed"
            )
        else:
            status = row["status"]
            if status == KPISuitability.reject.value:
                gates["physical_risk_policy"] = GateOutcome.failed
                notes.append(f"physical_risk_policy: {row['reason']}")
            elif kpi.proposed_as_trigger and not is_available_for_trigger_use(
                kpi.physical_risk_candidate_id
            ):
                gates["physical_risk_policy"] = GateOutcome.failed
                notes.append(
                    "physical_risk_policy: metric not available for trigger use "
                    f"({row['reason']})"
                )
            else:
                gates["physical_risk_policy"] = GateOutcome.passed

    return KPIGateResult(kpi_id=kpi.kpi_id, gates=gates, notes=notes)


class ReleaseGateResult(BaseModel):
    """Aggregate fail-closed result for a whole pack (spec §13)."""

    blocking_reasons: list[str] = Field(default_factory=list)
    kpi_results: list[KPIGateResult] = Field(default_factory=list)

    @property
    def reviewer_ready(self) -> bool:
        return not self.blocking_reasons

    def summary(self) -> str:
        if self.reviewer_ready:
            return "release gates: reviewer_ready"
        return "release gates BLOCKED: " + "; ".join(self.blocking_reasons)


def evaluate_release_gates(
    pack: EvidencePackInput,
    *,
    claim_scan: ClaimScanResult | None = None,
) -> ReleaseGateResult:
    """Fail-closed release gate (spec §13). Empty ``blocking_reasons`` == reviewer_ready."""
    reasons: list[str] = []
    manifest = pack.manifest

    # Guideline version / regulatory cut-off, and mandatory issuer/responsibility fields.
    if not (manifest.regulatory_source_id and manifest.regulatory_source_id.strip()):
        reasons.append("missing regulatory_source_id / guideline version")
    for field in manifest.missing_mandatory_fields():
        reasons.append(f"missing mandatory manifest field: {field}")

    # Route resolved?
    if manifest.regulatory_route is None:  # pragma: no cover - enum is required
        reasons.append("regulatory route unresolved")

    # Provenance: labelling, licence, hashes, scenario source.
    provenance_ids = {p.analysis_run_id for p in pack.provenance}
    for record in pack.provenance:
        reasons.extend(record.gate_problems())

    # Every manifest run id must resolve to a provenance record (reproducibility).
    for run_id in manifest.analysis_run_ids:
        if run_id not in provenance_ids:
            reasons.append(f"analysis_run_id '{run_id}' has no provenance record (not reproducible)")

    # External numbers (impact conclusions, project-eligibility evidence figures) must be
    # backed by a run that is *usable* for an external number — never synthetic, fallback or
    # unlicensed data, even when labelled (spec §9, §14). Labelling clears the honesty gate,
    # not this one, so an externally used run is re-checked with usable_in_external_number().
    provenance_by_id = {p.analysis_run_id: p for p in pack.provenance}

    def _external_run_problem(run_id: str, context: str) -> str | None:
        record = provenance_by_id.get(run_id)
        if record is None:
            return f"{context} references run '{run_id}' with no provenance record"
        if not record.usable_in_external_number():
            return (
                f"{context} uses run '{run_id}' that is not usable for an external number "
                "(synthetic, fallback, unlicensed, unhashed, or forward-looking without a "
                "real versioned scenario source)"
            )
        return None

    for metric in pack.impact_metrics:
        # A quantitative impact measure is an external number; a purely qualitative one is not.
        if metric.qualitative and metric.value is None:
            continue
        if not metric.evidence_run_id:
            reasons.append(
                f"impact metric '{metric.metric_id}' states a quantitative measure with no evidence_run_id"
            )
            continue
        problem = _external_run_problem(
            metric.evidence_run_id, f"impact metric '{metric.metric_id}'"
        )
        if problem:
            reasons.append(problem)

    for project in pack.projects:
        for run_id in project.evidence_run_ids:
            problem = _external_run_problem(run_id, f"project '{project.project_id}' evidence")
            if problem:
                reasons.append(problem)

    # Recalculation bridges must be valid where present.
    for bridge in pack.recalculation_bridges:
        ok, problems = bridge.is_valid()
        if not ok:
            reasons.extend(f"recalculation bridge invalid: {p}" for p in problems)

    # Uncertainty / limitations must not be suppressed.
    if not pack.uncertainty_and_limitations.strip():
        reasons.append("uncertainty or material limitations suppressed (empty limitations section)")

    # Prohibited claims.
    if claim_scan is not None and not claim_scan.ok:
        reasons.append(f"prohibited claims remain: {claim_scan.summary()}")

    # Review-role separation.
    roles = manifest.external_review_roles
    ok, violations = role_separation_ok(
        framework_adviser=roles.framework_adviser,
        second_party_opinion_provider=roles.second_party_opinion_provider,
        verifier=roles.verifier,
    )
    reasons.extend(f"review role separation: {v}" for v in violations)

    # Route-specific evidence.
    kpi_results: list[KPIGateResult] = []
    if manifest.regulatory_route is RegulatoryRoute.use_of_proceeds:
        if not pack.projects:
            reasons.append("use-of-proceeds route has no project register entries")
        for adaptation in pack.adaptation_evidence:
            if adaptation.attributes_hazard_reduction_to_issuer:
                reasons.append(
                    f"project '{adaptation.project_id}': hazard reduction wrongly attributed to issuer"
                )
    elif manifest.regulatory_route is RegulatoryRoute.sustainability_linked:
        if not pack.kpis:
            reasons.append("sustainability-linked route has no KPI register entries")
        # SPT calibration is a mandatory component of this route (spec §7.4): a KPI with no
        # SPT must not seal. Without this, an empty SPT list passes the loop below vacuously.
        if not pack.spts:
            reasons.append("sustainability-linked route has no SPT register entries")
        kpi_ids = {k.kpi_id for k in pack.kpis}
        for kpi in pack.kpis:
            result = evaluate_kpi_gates(kpi)
            kpi_results.append(result)
            if not result.reviewer_ready:
                reasons.append(
                    f"KPI '{kpi.kpi_id}' fails admission gate(s): {', '.join(result.failed_gates())}"
                )
            # A declared physical-risk metric (EAL/downtime/loss) must not be a financial
            # trigger before validation (spec §8, §13). This policy applies only to KPIs that
            # declare a physical-risk candidate id; an ordinary non-physical KPI used as an
            # instrument trigger is outside it, matching the admission-gate scoping.
            if (
                kpi.proposed_as_trigger
                and kpi.physical_risk_candidate_id
                and not is_available_for_trigger_use(kpi.physical_risk_candidate_id)
            ):
                reasons.append(
                    f"KPI '{kpi.kpi_id}' proposed as a trigger but not trigger-eligible under physical-risk policy"
                )
        for spt in pack.spts:
            if spt.linked_kpi_id not in kpi_ids:
                reasons.append(f"SPT '{spt.spt_id}' links to unknown KPI '{spt.linked_kpi_id}'")
            for field in spt.missing_required_fields():
                reasons.append(f"SPT '{spt.spt_id}' missing required field: {field}")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            deduped.append(reason)

    return ReleaseGateResult(blocking_reasons=deduped, kpi_results=kpi_results)


__all__ = [
    "GateOutcome",
    "KPIGateResult",
    "ReleaseGateResult",
    "evaluate_kpi_gates",
    "evaluate_release_gates",
]

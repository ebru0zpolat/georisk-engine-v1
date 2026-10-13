"""Machine-readable report and RAP-010 adapter."""

from dataclasses import dataclass
from typing import Any

from benchmarks.vera_rap.models import SystemCaseResult, SystemOutcome
from .models import DemonstratorOutcome, DemonstratorRunResult, fingerprint

LIMITATIONS = (
    "fixture-based",
    "not production calibrated",
    "not loss estimation",
    "not insurance pricing",
    "not regulatory certification",
    "not real-time hazard engine",
)


@dataclass(frozen=True, slots=True)
class DemonstratorReport:
    run_id: str
    asset_id: str
    question_id: str
    outcome: str
    material_claims: tuple[str, ...]
    blockers: tuple[str, ...]
    contradictions: tuple[str, ...]
    uncertainty_summary: dict[str, Any]
    plans: tuple[str, ...]
    trace_fingerprint: str
    benchmark_summary: dict[str, Any]
    evidence_summary: dict[str, Any]
    limitations: tuple[str, ...]
    fingerprint: str


def build_report(run: DemonstratorRunResult) -> DemonstratorReport:
    from app.research.vera_rap import VerificationStatus

    summary = {
        "admissible_evidence_count": sum(
            e.verification_status is VerificationStatus.VERIFIED
            for e in run.evidence_objects
        ),
        "rejected_evidence_count": sum(
            e.verification_status is VerificationStatus.REJECTED
            for e in run.evidence_objects
        ),
        "stale_evidence_count": sum(
            e.verification_status is VerificationStatus.STALE
            for e in run.evidence_objects
        ),
        "contradicted_evidence_count": len(
            {x for c in run.contradictions for x in c.evidence_ids}
        ),
        "missing_evidence_requirements": list(run.blockers),
        "provenance_complete_count": sum(
            bool(e.metadata.get("provenance_complete")) for e in run.evidence_objects
        ),
    }
    payload = {
        "run": run.run_id,
        "outcome": run.final_outcome.value,
        "summary": summary,
    }
    return DemonstratorReport(
        run.run_id,
        run.asset.asset_id,
        run.question.question_id,
        run.final_outcome.value,
        tuple(
            c.claim_id
            for c in run.claims
            if c.epistemic_state.value in {"SUPPORTED", "CONDITIONALLY_SUPPORTED"}
        ),
        run.blockers,
        tuple(c.contradiction_id for c in run.contradictions),
        {"profiles": len(run.uncertainty_profiles)},
        tuple(p.plan_id for p in run.plans),
        run.trace.fingerprint,
        {"evidenceboundbench_compatible": True},
        summary,
        LIMITATIONS,
        fingerprint(payload),
    )


def to_system_case_result(run: DemonstratorRunResult) -> SystemCaseResult:
    concluded = run.final_outcome in {
        DemonstratorOutcome.SUPPORTED,
        DemonstratorOutcome.CONDITIONALLY_SUPPORTED,
    }
    outcome = (
        SystemOutcome.CONCLUDED
        if concluded
        else (
            SystemOutcome.REPLANNED
            if run.final_outcome is DemonstratorOutcome.REPLAN_REQUIRED
            else SystemOutcome.BLOCKED
        )
    )
    return SystemCaseResult(
        run.question.question_id,
        "vera-rap-georisk",
        "1",
        outcome,
        tuple(c.claim_id for c in run.claims) if concluded else (),
        {x.transition_id: x.status.value for x in run.transition_evaluations},
        {f"a{i}": x.status.value for i, x in enumerate(run.abstraction_verifications)},
        False,
        tuple(p.plan_id for p in run.plans),
        (),
        run.trace,
        {"deterministic": True},
        blocker_types=run.blockers,
    )

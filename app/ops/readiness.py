"""WP-E: Pure readiness evaluator for controlled-pilot eligibility (GEO-62).

Independent gates: config_complete, authenticated_smoke_passed,
transport_verified, application_response_verified, evidence_hash_verified,
durable_retention_verified, source_tree_clean, exact_release_sha_verified,
human_release_approval.

human_release_approval is never settable by environment variable or API
request.  controlled_pilot_eligible and production_eligible remain false
until every gate passes including an independent human approval.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReadinessGate(BaseModel, frozen=True):
    """One readiness gate."""

    name: str
    passed: bool
    reason: str = ""


class ReadinessResult(BaseModel, frozen=True):
    """Aggregated readiness evaluation."""

    complete: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evaluated_release_sha: str = ""
    controlled_pilot_eligible: Literal[False] = False
    runtime_live_verified: Literal[False] = False
    production_eligible: Literal[False] = False
    gates: list[ReadinessGate] = Field(default_factory=list)


from typing import Literal  # noqa: E402


def evaluate_readiness(
    *,
    config_complete: bool = False,
    authenticated_smoke_passed: bool = False,
    transport_verified: bool = False,
    application_response_verified: bool = False,
    evidence_hash_verified: bool = False,
    durable_retention_verified: bool = False,
    source_tree_clean: bool = True,
    exact_release_sha: str = "",
    actual_release_sha: str = "",
    evidence_ids: list[str] | None = None,
    human_release_approval: bool = False,
) -> ReadinessResult:
    """Evaluate controlled-pilot readiness from explicit gate values.

    ``human_release_approval`` must come from an independent human
    review process — never from a request parameter, environment
    variable or automated test.
    """
    gates = [
        ReadinessGate(
            name="config_complete",
            passed=config_complete,
            reason="" if config_complete else "Deployment config incomplete",
        ),
        ReadinessGate(
            name="authenticated_smoke_passed",
            passed=authenticated_smoke_passed,
            reason="" if authenticated_smoke_passed else "Authenticated smoke not passed",
        ),
        ReadinessGate(
            name="transport_verified",
            passed=transport_verified,
            reason="" if transport_verified else "Transport not verified",
        ),
        ReadinessGate(
            name="application_response_verified",
            passed=application_response_verified,
            reason="" if application_response_verified else "Application response not verified",
        ),
        ReadinessGate(
            name="evidence_hash_verified",
            passed=evidence_hash_verified,
            reason="" if evidence_hash_verified else "Evidence hash not verified",
        ),
        ReadinessGate(
            name="durable_retention_verified",
            passed=durable_retention_verified,
            reason="" if durable_retention_verified else "Durable retention not verified",
        ),
        ReadinessGate(
            name="source_tree_clean",
            passed=source_tree_clean,
            reason="" if source_tree_clean else "Source tree is dirty",
        ),
        ReadinessGate(
            name="exact_release_sha_verified",
            passed=(exact_release_sha and exact_release_sha == actual_release_sha),
            reason=(
                ""
                if (exact_release_sha and exact_release_sha == actual_release_sha)
                else "Release SHA mismatch or missing"
            ),
        ),
        ReadinessGate(
            name="human_release_approval",
            passed=human_release_approval,
            reason="" if human_release_approval else "Human release approval pending",
        ),
    ]

    blocking = [g.reason for g in gates if not g.passed]
    all_pass = len(blocking) == 0

    return ReadinessResult(
        complete=all_pass,
        blocking_reasons=blocking,
        evidence_ids=evidence_ids or [],
        evaluated_release_sha=actual_release_sha,
        controlled_pilot_eligible=False,  # always false in this WP
        runtime_live_verified=False,
        production_eligible=False,
        gates=gates,
    )

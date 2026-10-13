"""Trusted authorization for GitHub native auto-merge."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.automation.artifacts import ArtifactManifest
from app.automation.circuit_breaker import CircuitState
from app.automation.models import ActionClass, Classification, StrictModel


class PullRequestFacts(StrictModel):
    number: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    actor: str
    head_repository: str
    base_repository: str
    draft: bool
    dependency_or_lockfile_change: bool = False
    artifact_upload_succeeded: bool = True
    issue_write_succeeded: bool = True


class AutoMergeAuthorization(StrictModel):
    allowed: bool
    reasons: list[str]
    mechanism: str = "github_native_auto_merge"


def authorize_native_auto_merge(
    *, facts: PullRequestFacts, classification: Classification,
    manifest: ArtifactManifest, policy: dict[str, Any], circuit: CircuitState,
) -> AutoMergeAuthorization:
    reasons: list[str] = []
    trusted = set(policy["phase2"]["trusted_automation_actors"])
    if facts.actor not in trusted:
        reasons.append("actor is not a configured repository automation identity")
    if facts.head_repository != facts.base_repository:
        reasons.append("fork pull requests are ineligible")
    if facts.draft:
        reasons.append("draft pull requests are ineligible")
    if facts.dependency_or_lockfile_change:
        reasons.append("dependency or lockfile changes are excluded")
    if classification.action_class != ActionClass.AUTO_PASS:
        reasons.append(f"classification is {classification.action_class.value}, not AUTO-PASS")
    if manifest.commit_sha != facts.head_sha:
        reasons.append("classification artifact is stale or for the wrong SHA")
    if any(check.commit_sha != facts.head_sha or check.state != "pass" for check in manifest.checks_observed):
        reasons.append("required-check evidence is incomplete or has wrong provenance")
    required = set(policy["phase2"]["required_pr_checks"])
    passed = {check.name for check in manifest.checks_observed if check.state == "pass"}
    if not required <= passed:
        reasons.append("policy-required checks are missing")
    if circuit != CircuitState.CLOSED:
        reasons.append("automation circuit breaker is open or unavailable")
    if not facts.artifact_upload_succeeded:
        reasons.append("classification artifact upload failed")
    if not facts.issue_write_succeeded:
        reasons.append("required issue write failed")
    return AutoMergeAuthorization(allowed=not reasons, reasons=reasons or ["eligible for GitHub native auto-merge"])

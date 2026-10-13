"""Fail-closed release-readiness contract for named GeoRisk releases."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.data_centres.contracts import GIT_SHA_PATTERN

ReleaseDecision = Literal[
    "demo_only",
    "controlled_pilot",
    "validated_decision_support",
    "production_eligible",
]


def _as_utc(value: datetime) -> datetime:
    """Normalize Pydantic's accepted naive datetimes for reliable comparisons."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ReleaseGateStates(BaseModel):
    """Independent evidence gates; no gate implies another gate."""

    model_config = ConfigDict(protected_namespaces=("model_dump",))

    platform_operational: bool = False
    data_source_operational: bool = False
    model_validated_for_use_case: bool = False
    commercially_validated: bool = False
    runtime_live_verified: bool = False


class ReleaseApproval(BaseModel):
    approval_type: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    approved_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def expiration_follows_approval(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.approved_at:
            raise ValueError("expires_at must be later than approved_at")
        return self


class ReleaseManifest(BaseModel):
    """Auditable, bounded release decision.

    ``production_eligible`` is derived from the independent gates and cannot be
    asserted directly. This prevents a green build or one live source call from
    silently promoting an otherwise unvalidated release.
    """

    schema_version: Literal["1.0"] = "1.0"
    release_version: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)
    geography: str = Field(min_length=1)
    hazards: list[str] = Field(min_length=1)
    asset_class: str = Field(min_length=1)
    permitted_user_decision: str = Field(min_length=1)
    source_versions: dict[str, str] = Field(default_factory=dict)
    model_versions: dict[str, str] = Field(default_factory=dict)
    gates: ReleaseGateStates = Field(default_factory=ReleaseGateStates)
    decision: ReleaseDecision = "demo_only"
    production_eligible: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    approvals: list[ReleaseApproval] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=1)
    prohibited_uses: list[str] = Field(min_length=1)
    rollback_owner: str | None = None
    incident_contact: str | None = None

    @model_validator(mode="after")
    def enforce_fail_closed_decision(self) -> Self:
        all_gates_pass = all(
            (
                self.gates.platform_operational,
                self.gates.data_source_operational,
                self.gates.model_validated_for_use_case,
                self.gates.commercially_validated,
                self.gates.runtime_live_verified,
            )
        )
        now = datetime.now(timezone.utc)
        valid_approval_evidence = any(
            approval.evidence_id in self.evidence_ids
            and _as_utc(approval.approved_at) <= now
            and (
                approval.expires_at is None or _as_utc(approval.expires_at) > now
            )
            for approval in self.approvals
        )
        expected_eligible = (
            self.decision == "production_eligible"
            and all_gates_pass
            and valid_approval_evidence
        )
        if self.production_eligible != expected_eligible:
            raise ValueError(
                "production_eligible must be true only when the decision and every gate "
                "pass and a current approval has linked evidence"
            )
        if self.decision != "demo_only" and not re.fullmatch(
            GIT_SHA_PATTERN, self.commit_sha
        ):
            raise ValueError("a non-demo release requires an exact commit SHA")
        if self.decision != "demo_only" and (
            not self.rollback_owner or not self.incident_contact
        ):
            raise ValueError(
                "a non-demo release requires a rollback owner and incident contact"
            )
        return self

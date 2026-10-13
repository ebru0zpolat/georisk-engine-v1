"""Strict contracts for repository evidence and the weekly founder digest."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=("model_dump",))


class ActionClass(StrEnum):
    AUTO_PASS = "AUTO-PASS"
    AUTO_BLOCK = "AUTO-BLOCK"
    FOUNDER_DECISION = "FOUNDER-DECISION"


class CheckResult(StrictModel):
    name: str = Field(min_length=1)
    state: Literal["pass", "fail", "skip", "unavailable"]
    source: str = Field(min_length=1)
    evidence_kind: Literal["local", "ci", "deployment", "external"]
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")

    @model_validator(mode="after")
    def local_is_not_ci(self) -> "CheckResult":
        if self.evidence_kind == "local" and "github ci" in self.source.lower():
            raise ValueError("local evidence cannot claim to be GitHub CI evidence")
        return self


class DiffStatistics(StrictModel):
    files: int = Field(ge=0)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)

    @property
    def lines(self) -> int:
        return self.additions + self.deletions


class ClassificationInput(StrictModel):
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    changed_paths: list[str]
    diff: DiffStatistics
    required_checks: list[str]
    observed_checks: list[CheckResult]
    dependency_change: bool = False
    readiness_change: bool = False
    workflow_or_policy_change: bool = False
    database_migration: bool = False
    scientific_change: bool = False
    legal_regulatory_customer_content: bool = False
    customer_or_personal_data: bool = False
    production_credential_or_access: bool = False
    security_exception: bool = False
    external_send_intent: bool = False
    production_write_intent: bool = False
    destructive_or_irreversible: bool = False


class Classification(StrictModel):
    action_class: ActionClass
    reasons: list[str] = Field(min_length=1)


class Blocker(StrictModel):
    blocker_id: str = Field(pattern=r"^blk_[0-9a-f]{16}$")
    workflow_id: str
    category: str
    resource: str
    evidence_version: str
    summary: str
    status: Literal["open", "resolved"] = "open"
    first_seen: datetime
    last_seen: datetime
    occurrences: int = Field(ge=1)
    history: list[dict[str, str]]
    material: bool = True


class ReadinessSnapshot(StrictModel):
    platform_operational: bool = False
    data_source_operational: bool = False
    model_validated_for_use_case: bool = False
    commercially_validated: bool = False
    runtime_live_verified: bool = False
    controlled_pilot_eligible: bool = False
    production_eligible: bool = False
    scientific_validation_status: str = "unchanged"
    licence_verification_status: str = "unchanged"


class EvidenceRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    repository: str
    branch: str
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    changed_paths: list[str]
    diff: DiffStatistics
    classification: Classification
    checks_required: list[str]
    checks_observed: list[CheckResult]
    evidence_timestamp: datetime
    evidence_kind: Literal["local", "ci", "deployment", "external"]
    blockers: list[Blocker]
    readiness: ReadinessSnapshot

    @model_validator(mode="after")
    def checks_match_record_kind(self) -> "EvidenceRecord":
        if any(check.evidence_kind != self.evidence_kind for check in self.checks_observed):
            raise ValueError("check evidence kind must match its containing record")
        if any(check.commit_sha != self.commit_sha for check in self.checks_observed):
            raise ValueError("check evidence must be for the record's exact commit SHA")
        return self


class FounderDecision(StrictModel):
    decision_id: str
    priority: int = Field(ge=0)
    title: str
    recommended_option: str
    alternatives: list[str]
    consequence_of_no_action: str
    deadline: datetime
    estimated_minutes: int = Field(ge=0)
    evidence_reference: str
    urgent_event: str | None = None


class DatedDigestItem(StrictModel):
    item_id: str
    summary: str
    due_at: datetime


class DigestInput(StrictModel):
    period_start: datetime
    period_end: datetime
    decisions: list[FounderDecision] = Field(default_factory=list)
    blockers: list[Blocker] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    deadlines: list[DatedDigestItem] = Field(default_factory=list)
    expiring_exceptions: list[DatedDigestItem] = Field(default_factory=list)
    deferred: list[str] = Field(default_factory=list)

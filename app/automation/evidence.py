"""Exact-SHA evidence creation and deterministic serialization."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.automation.models import (
    Blocker, CheckResult, Classification, DiffStatistics, EvidenceRecord, ReadinessSnapshot,
)


def build_evidence_record(
    *, repository: str, branch: str, commit_sha: str, changed_paths: list[str],
    diff: DiffStatistics, classification: Classification, checks_required: list[str],
    checks_observed: list[CheckResult], timestamp: datetime, evidence_kind: str,
    blockers: list[Blocker], readiness: ReadinessSnapshot,
) -> EvidenceRecord:
    return EvidenceRecord(
        repository=repository, branch=branch, commit_sha=commit_sha,
        changed_paths=sorted(changed_paths), diff=diff, classification=classification,
        checks_required=sorted(checks_required), checks_observed=sorted(checks_observed, key=lambda item: item.name),
        evidence_timestamp=timestamp, evidence_kind=evidence_kind, blockers=blockers,
        readiness=readiness,
    )


def write_evidence(record: EvidenceRecord, path: str | Path) -> None:
    """Write stable JSON; validation occurs again on every read."""
    Path(path).write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")


def read_evidence(path: str | Path) -> EvidenceRecord:
    return EvidenceRecord.model_validate_json(Path(path).read_text())

"""Read-only roadmap, policy, evidence, readiness, and Git-state reconciliation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from app.automation.models import ActionClass, EvidenceRecord, ReadinessSnapshot, StrictModel


class ReconciliationItem(StrictModel):
    item_id: str
    title: str
    status: Literal[
        "completed_with_evidence", "implemented_but_unverified", "blocked", "deferred",
        "stale", "policy_only_not_implemented", "awaiting_founder_decision",
    ]
    evidence_references: list[str] = Field(default_factory=list)
    reason: str


class ReconciliationReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_dirty: bool
    items: list[ReconciliationItem]
    readiness: ReadinessSnapshot


def roadmap_phases(path: str | Path) -> dict[str, str]:
    """Read canonical phase rows; prose alone never supplies completion state."""
    phases: dict[str, str] = {}
    pattern = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|")
    in_phase_table = False
    for line in Path(path).read_text().splitlines():
        if line.startswith("## 7. Phased implementation plan"):
            in_phase_table = True
            continue
        if in_phase_table and line.startswith("## 8."):
            break
        if not in_phase_table:
            continue
        match = pattern.match(line)
        if match:
            phases[f"phase-{match.group(1)}"] = match.group(2).strip()
    return phases


def reconcile(
    *, policy: dict[str, Any], roadmap_path: str | Path,
    evidence: list[tuple[str, EvidenceRecord]], commit_sha: str, git_dirty: bool,
    readiness: ReadinessSnapshot,
) -> ReconciliationReport:
    evidence_by_workflow: dict[str, list[tuple[str, EvidenceRecord]]] = {}
    for reference, record in evidence:
        for blocker in record.blockers:
            evidence_by_workflow.setdefault(blocker.workflow_id, []).append((reference, record))
        # Evidence producers use a required check named workflow:<id>.
        for check in record.checks_observed:
            if check.name.startswith("workflow:"):
                evidence_by_workflow.setdefault(check.name.removeprefix("workflow:"), []).append((reference, record))

    items: list[ReconciliationItem] = []
    workflows = policy["workflows"]
    for workflow in workflows:
        wid = workflow["id"]
        records = evidence_by_workflow.get(wid, [])
        latest = records[-1][1] if records else None
        refs = sorted({reference for reference, _ in records})
        if latest is None:
            status, reason = "policy_only_not_implemented", "policy exists but no validated execution evidence exists"
        elif latest.commit_sha != commit_sha:
            status, reason = "stale", "latest evidence is not for the applicable exact Git SHA"
        elif latest.classification.action_class == ActionClass.FOUNDER_DECISION:
            status, reason = "awaiting_founder_decision", "classification queued a decision but did not approve it"
        elif any(blocker.status == "open" and blocker.workflow_id == wid for blocker in latest.blockers):
            status, reason = "blocked", "current evidence contains an open blocker"
        else:
            relevant = [check for check in latest.checks_observed if check.name == f"workflow:{wid}"]
            if relevant and all(check.state == "pass" for check in relevant):
                status, reason = "completed_with_evidence", "validated exact-SHA workflow evidence passed"
            else:
                status, reason = "implemented_but_unverified", "evidence exists but required workflow verification did not pass"
        items.append(ReconciliationItem(item_id=wid, title=wid.replace("_", " ").title(), status=status, evidence_references=refs, reason=reason))

    # Roadmap phases are planning containers. They remain policy-only unless a workflow with the
    # same ordinal has verified evidence; documentation language is deliberately ignored.
    for phase_id, title in roadmap_phases(roadmap_path).items():
        items.append(ReconciliationItem(
            item_id=phase_id, title=title, status="policy_only_not_implemented",
            reason="canonical roadmap phase has no independent completion-evidence mapping",
        ))
    return ReconciliationReport(commit_sha=commit_sha, git_dirty=git_dirty, items=items, readiness=readiness)

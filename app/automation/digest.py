"""Deterministic Markdown-only founder digest generation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.automation.models import DigestInput, FounderDecision
from app.automation.reconciliation import ReconciliationItem, ReconciliationReport

# One scheduled digest covers the week that ended at its period end.
DIGEST_PERIOD = timedelta(days=7)
# Reconciliation states that need founder visibility but do not themselves carry a decision.
DEFERRED_STATUSES = ("blocked", "deferred", "implemented_but_unverified", "stale")


def is_urgent(decision: FounderDecision, policy: dict[str, Any]) -> bool:
    return decision.urgent_event in set(policy["urgent_notifications"])


def _decision_from_item(item: ReconciliationItem, *, now: datetime, policy: dict[str, Any]) -> FounderDecision:
    budget = policy["founder_budget"]
    return FounderDecision(
        decision_id=item.item_id,
        priority=1,
        title=f"Record an explicit decision for {item.title}",
        recommended_option="Review the referenced exact-SHA evidence, then approve or reject it",
        alternatives=["Defer without changing any gate"],
        consequence_of_no_action=policy["defaults"]["no_founder_response"].replace("_", " "),
        deadline=now + timedelta(days=policy["digest_horizons"]["external_deadline_days"]),
        estimated_minutes=budget["max_repository_minutes"] // max(budget["max_decisions"], 1),
        evidence_reference=", ".join(item.evidence_references) or item.item_id,
    )


def reconciliation_digest_sections(
    report: ReconciliationReport, *, now: datetime, policy: dict[str, Any],
) -> tuple[list[FounderDecision], list[str], list[str]]:
    """Project a reconciliation report onto the digest's decision, completed and deferred inputs.

    Without this projection the report is retained as a sidecar artifact only, and the founder-facing
    Markdown reports `None.` for every section even when the reconciliation found actionable work.
    """
    decisions = [
        _decision_from_item(item, now=now, policy=policy)
        for item in report.items
        if item.status == "awaiting_founder_decision"
    ]
    completed = [
        f"{item.title} — {item.reason}"
        + (f" (evidence: {', '.join(item.evidence_references)})" if item.evidence_references else "")
        for item in report.items
        if item.status == "completed_with_evidence"
    ]
    deferred = [
        f"{item.title} — {item.status.replace('_', ' ')}: {item.reason}"
        for item in report.items
        if item.status in DEFERRED_STATUSES
    ]
    # The policy-only backlog is every roadmap phase and unimplemented workflow. It is summarized
    # rather than enumerated so a routine digest cannot bury the items that need attention.
    policy_only = sum(1 for item in report.items if item.status == "policy_only_not_implemented")
    if policy_only:
        deferred.append(f"{policy_only} roadmap or workflow items remain policy-only with no validated execution evidence")
    return decisions, completed, deferred


def generate_digest(data: DigestInput, policy: dict[str, Any]) -> str:
    """Generate an artifact only; this function performs no notification or write."""
    ordered = sorted(data.decisions, key=lambda item: (-item.priority, item.deadline, item.decision_id))
    urgent = [item for item in ordered if is_urgent(item, policy)]
    ordinary = [item for item in ordered if not is_urgent(item, policy)]
    selected_ordinary: list[FounderDecision] = []
    overflow: list[FounderDecision] = []
    minute_budget = policy["founder_budget"]["max_repository_minutes"]
    for item in ordinary:
        fits_count = len(selected_ordinary) < policy["founder_budget"]["max_decisions"]
        fits_minutes = sum(value.estimated_minutes for value in selected_ordinary) + item.estimated_minutes <= minute_budget
        (selected_ordinary if fits_count and fits_minutes else overflow).append(item)
    selected = [*urgent, *selected_ordinary]
    blockers = sorted(
        (item for item in data.blockers if item.status == "open" and item.material),
        key=lambda item: (item.workflow_id, item.category, item.blocker_id),
    )[: policy["founder_budget"]["max_material_blockers"]]
    minutes = sum(item.estimated_minutes for item in selected)
    lines = [
        "# GeoRisk Founder Digest", "",
        f"**Period:** {data.period_start.isoformat()} — {data.period_end.isoformat()}",
        f"**Estimated founder time:** {minutes} minutes", "",
        "## Required decisions", "",
    ]
    if not selected:
        lines.append("None.")
    for item in selected:
        urgency = " — **URGENT**" if is_urgent(item, policy) else ""
        lines.extend([
            f"### {item.title}{urgency}",
            f"- **Recommended:** {item.recommended_option}",
            f"- **Alternatives:** {', '.join(item.alternatives) if item.alternatives else 'None'}",
            f"- **No action:** {item.consequence_of_no_action}",
            f"- **Deadline:** {item.deadline.isoformat()}",
            f"- **Founder time:** {item.estimated_minutes} minutes",
            f"- **Evidence:** {item.evidence_reference}", "",
        ])
    lines.extend(["## Material blockers", ""])
    lines.extend(
        [f"- `{item.blocker_id}` — {item.summary} ({item.workflow_id}/{item.category})" for item in blockers]
        or ["None."]
    )
    deadline_cutoff = data.period_end + timedelta(days=policy["digest_horizons"]["external_deadline_days"])
    exception_cutoff = data.period_end + timedelta(days=policy["digest_horizons"]["exception_expiry_days"])
    deadlines = [f"{item.summary} — {item.due_at.isoformat()}" for item in data.deadlines if data.period_end <= item.due_at <= deadline_cutoff]
    exceptions = [f"{item.summary} — {item.due_at.isoformat()}" for item in data.expiring_exceptions if data.period_end <= item.due_at <= exception_cutoff]
    sections = (
        ("Autonomous work completed", data.completed),
        ("Upcoming external deadlines", deadlines),
        ("Exceptions nearing expiry", exceptions),
        ("Deferred — no current action", [*data.deferred, *[f"Decision deferred: {item.title}" for item in overflow]]),
    )
    for title, values in sections:
        lines.extend(["", f"## {title}", ""])
        lines.extend([f"- {value}" for value in values] or ["None."])
    lines.extend(["", "_Artifact only: no email, issue, comment, message, deployment, or production write was performed._", ""])
    return "\n".join(lines)

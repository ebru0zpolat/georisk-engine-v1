"""Trusted-provenance, idempotent plans for canonical GitHub issues."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field

from app.automation.models import Blocker, StrictModel

MARKER_RE = re.compile(r"<!-- georisk-automation:([a-z0-9:_-]+) -->")
SENSITIVE = re.compile(r"(?i)((token|password|secret|credential)\s*[:=]\s*\S+|x-amz-signature=|[?&]sig=)")


class IssueAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    NOOP = "noop"


class ExistingIssue(StrictModel):
    number: int = Field(gt=0)
    title: str
    body: str
    state: str
    repository: str = ""
    author_login: str = ""
    labels: list[str] = Field(default_factory=list)


class IssueInventory(StrictModel):
    repository: str
    complete: bool
    issues: list[ExistingIssue]


class IssuePlan(StrictModel):
    action: IssueAction
    marker: str
    title: str
    body: str
    labels: list[str]
    issue_number: int | None = None


def marker(kind: str, identifier: str) -> str:
    safe = re.sub(r"[^a-z0-9_-]", "-", identifier.lower())
    return f"<!-- georisk-automation:{kind}:{safe} -->"


def trusted_issue(issue: ExistingIssue, *, repository: str, creators: set[str], label: str) -> bool:
    return issue.repository == repository and issue.author_login in creators and label in issue.labels


def plan_issue(
    inventory: IssueInventory, *, kind: str, identifier: str, title: str, body: str,
    trusted_creators: set[str], trusted_label: str, resolved: bool = False,
) -> IssuePlan:
    if not inventory.complete:
        raise ValueError("canonical issue enumeration is incomplete")
    stable_marker = marker(kind, identifier)
    clean_body = f"{stable_marker}\n\n{body.strip()}\n"
    if SENSITIVE.search(clean_body):
        raise ValueError("issue body contains a sensitive-data indicator")
    marker_matches = [item for item in inventory.issues if stable_marker in item.body]
    trusted = [item for item in marker_matches if trusted_issue(item, repository=inventory.repository, creators=trusted_creators, label=trusted_label)]
    contaminated = [item for item in marker_matches if item not in trusted]
    if contaminated:
        raise ValueError("canonical marker contamination requires founder reconciliation")
    if len(trusted) > 1:
        raise ValueError("duplicate trusted canonical issues require founder reconciliation")
    labels = [trusted_label]
    if not trusted:
        return IssuePlan(action=IssueAction.NOOP if resolved else IssueAction.CREATE, marker=stable_marker, title=title, body=clean_body, labels=labels)
    current = trusted[0]
    if resolved:
        return IssuePlan(action=IssueAction.CLOSE, marker=stable_marker, title=title, body=clean_body, labels=labels, issue_number=current.number)
    if current.title == title and current.body == clean_body and current.state == "open":
        return IssuePlan(action=IssueAction.NOOP, marker=stable_marker, title=title, body=clean_body, labels=labels, issue_number=current.number)
    return IssuePlan(action=IssueAction.UPDATE, marker=stable_marker, title=title, body=clean_body, labels=labels, issue_number=current.number)


def blocker_issue_plan(inventory: IssueInventory, blocker: Blocker, *, trusted_creators: set[str], trusted_label: str) -> IssuePlan:
    return plan_issue(
        inventory, kind="blocker", identifier=blocker.blocker_id,
        title=f"[AUTO-BLOCK] {blocker.workflow_id}: {blocker.category}",
        body=f"{blocker.summary}\n\nAffected resource: `{blocker.resource}`\nEvidence: `{blocker.evidence_version}`",
        trusted_creators=trusted_creators, trusted_label=trusted_label,
        resolved=blocker.status == "resolved",
    )


def urgent_issue_plan(
    inventory: IssueInventory, *, event: str, summary: str, evidence_reference: str,
    urgent_events: list[str], trusted_creators: set[str], trusted_label: str,
) -> IssuePlan | None:
    if event not in set(urgent_events):
        return None
    return plan_issue(
        inventory, kind="urgent", identifier=event,
        title=f"[URGENT] {event.replace('_', ' ')}", body=f"{summary}\n\nEvidence: `{evidence_reference}`",
        trusted_creators=trusted_creators, trusted_label=trusted_label,
    )

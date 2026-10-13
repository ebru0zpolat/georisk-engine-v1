"""Stable blocker identities and append-only resolution history."""

from __future__ import annotations

import hashlib
from datetime import datetime

from app.automation.models import Blocker

SYSTEM_WORKFLOW_ID = "system"


def blocker_id(workflow_id: str, category: str, resource: str, evidence_version: str) -> str:
    material = "\x1f".join((workflow_id, category, resource, evidence_version)).encode()
    return "blk_" + hashlib.sha256(material).hexdigest()[:16]


def system_blocker_id(identifier: str) -> str:
    """Map a readable system blocker identifier onto the canonical `blk_<hex16>` contract.

    Trusted workflows raise their own blockers under readable marker identifiers (for example
    `digest-artifact-verification`). Those markers stay readable in GitHub, but the digest models
    every blocker under one identity contract, so the readable name is hashed deterministically.
    """
    return "blk_" + hashlib.sha256(f"{SYSTEM_WORKFLOW_ID}:{identifier}".encode()).hexdigest()[:16]


def upsert_blocker(
    blockers: list[Blocker], *, workflow_id: str, category: str, resource: str,
    evidence_version: str, summary: str, observed_at: datetime, material: bool = True,
) -> list[Blocker]:
    """Return a new list with one logical blocker and no sensitive payload fields."""
    identifier = blocker_id(workflow_id, category, resource, evidence_version)
    result = [item.model_copy(deep=True) for item in blockers]
    for index, item in enumerate(result):
        if item.blocker_id == identifier:
            history = [*item.history, {"at": observed_at.isoformat(), "status": "open"}]
            result[index] = item.model_copy(update={
                "summary": summary, "status": "open", "last_seen": observed_at,
                "occurrences": item.occurrences + 1, "history": history,
            })
            return result
    result.append(Blocker(
        blocker_id=identifier, workflow_id=workflow_id, category=category,
        resource=resource, evidence_version=evidence_version, summary=summary,
        first_seen=observed_at, last_seen=observed_at, occurrences=1,
        history=[{"at": observed_at.isoformat(), "status": "open"}], material=material,
    ))
    return result


def resolve_blocker(blockers: list[Blocker], identifier: str, resolved_at: datetime) -> list[Blocker]:
    result = [item.model_copy(deep=True) for item in blockers]
    for index, item in enumerate(result):
        if item.blocker_id == identifier:
            result[index] = item.model_copy(update={
                "status": "resolved", "last_seen": resolved_at,
                "history": [*item.history, {"at": resolved_at.isoformat(), "status": "resolved"}],
            })
    return result

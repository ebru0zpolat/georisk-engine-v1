"""Shared fail-closed GitHub check-run normalization."""

from __future__ import annotations

import re
from typing import Any

from app.automation.github import GitHubAPIError
from app.automation.models import CheckResult

_STATE = {"success": "pass", "failure": "fail", "cancelled": "fail", "timed_out": "fail", "skipped": "skip", "neutral": "unavailable", "stale": "unavailable", "action_required": "unavailable"}


def normalize_check_runs(raw: list[dict[str, Any]], requested_sha: str) -> list[CheckResult]:
    if not re.fullmatch(r"[0-9a-f]{40}", requested_sha):
        raise GitHubAPIError("exact requested check SHA is malformed")
    normalized: dict[str, CheckResult] = {}
    for item in raw:
        name, actual_sha = item.get("name"), item.get("head_sha")
        if not isinstance(name, str) or not name or not isinstance(actual_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", actual_sha):
            raise GitHubAPIError("check name or API-reported head_sha is missing or malformed")
        if actual_sha != requested_sha:
            raise GitHubAPIError("check-run head_sha does not match requested exact commit")
        state = _STATE.get(item.get("conclusion"), "unavailable")
        result = CheckResult(name=name, state=state, source=f"GitHub check-run {item.get('id')}", evidence_kind="ci", commit_sha=actual_sha)
        previous = normalized.get(name)
        if previous is not None and (previous.state != result.state or previous.commit_sha != result.commit_sha):
            raise GitHubAPIError("duplicate check name has conflicting result or provenance")
        if previous is None:
            normalized[name] = result
    return sorted(normalized.values(), key=lambda value: value.name)

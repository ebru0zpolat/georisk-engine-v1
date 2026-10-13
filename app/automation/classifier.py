"""Deterministic, fail-closed classification of repository actions."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from app.automation.models import ActionClass, Classification, ClassificationInput

FOUNDER_FLAGS = {
    "security_exception": "security exception creation or extension",
    "workflow_or_policy_change": "workflow, policy, or approving-gate modification",
    "readiness_change": "readiness-state modification",
    "production_credential_or_access": "production credential or privileged-access change",
    "database_migration": "database migration",
    "scientific_change": "scientific formula or methodology change",
    "customer_or_personal_data": "customer or personal-data handling",
    "legal_regulatory_customer_content": "pricing, contract, legal, regulatory, or customer content",
    "external_send_intent": "external communication intent",
    "destructive_or_irreversible": "destructive or irreversible action",
}


def _matches(path: str, patterns: list[str]) -> bool:
    return any(
        fnmatch(path, pattern) or ("/**/" in pattern and fnmatch(path, pattern.replace("/**/", "/")))
        for pattern in patterns
    )


def classify_action(data: ClassificationInput, policy: dict[str, Any]) -> Classification:
    """Classify an action; classification never grants founder approval."""
    founder_reasons = [reason for flag, reason in FOUNDER_FLAGS.items() if getattr(data, flag)]
    protected = policy["protected_resources"]
    protected_paths = sorted(path for path in data.changed_paths if _matches(path, protected))
    if protected_paths:
        founder_reasons.append(f"protected files changed: {', '.join(protected_paths)}")
    if founder_reasons:
        return Classification(action_class=ActionClass.FOUNDER_DECISION, reasons=sorted(set(founder_reasons)))

    if data.production_write_intent:
        return Classification(
            action_class=ActionClass.AUTO_BLOCK,
            reasons=["production writes are prohibited in Phase 1"],
        )
    auto = policy["auto_merge"]
    if not data.changed_paths:
        return Classification(action_class=ActionClass.AUTO_BLOCK, reasons=["no changed paths supplied"])
    if data.diff.files != len(data.changed_paths):
        return Classification(action_class=ActionClass.AUTO_BLOCK, reasons=["diff file count is ambiguous"])
    if data.diff.files > auto["max_files"] or data.diff.lines > auto["max_diff_lines"]:
        return Classification(action_class=ActionClass.AUTO_BLOCK, reasons=["change exceeds bounded file or diff limit"])
    if data.dependency_change:
        return Classification(action_class=ActionClass.AUTO_BLOCK, reasons=["dependency change requires separate policy evidence"])
    outside = sorted(path for path in data.changed_paths if not _matches(path, auto["allowed_resources"]))
    if outside:
        return Classification(action_class=ActionClass.AUTO_BLOCK, reasons=[f"paths are outside the low-risk allowlist: {', '.join(outside)}"])

    observed = {check.name: check for check in data.observed_checks}
    missing = sorted(set(data.required_checks) - observed.keys())
    if missing:
        return Classification(action_class=ActionClass.AUTO_BLOCK, reasons=[f"required exact-head evidence missing: {', '.join(missing)}"])
    invalid = sorted(
        name for name in data.required_checks
        if observed[name].state != "pass" or observed[name].commit_sha != data.commit_sha
    )
    if invalid:
        return Classification(action_class=ActionClass.AUTO_BLOCK, reasons=[f"required checks did not pass at exact head: {', '.join(invalid)}"])
    return Classification(
        action_class=ActionClass.AUTO_PASS,
        reasons=["allowlisted bounded change with all required exact-head checks passing"],
    )

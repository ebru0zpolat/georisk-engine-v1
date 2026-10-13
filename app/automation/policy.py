"""Repository-native, fail-closed automation-policy validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.automation.models import ActionClass

MANDATORY_WORKFLOW_FIELDS = {
    "id", "action_class", "trigger", "allowed_resources", "required_checks",
    "maximum_retries", "timeout_minutes", "concurrency_rule",
    "rollback_or_safe_stop", "evidence_artifact", "notification_policy",
    "prohibited_actions", "circuit_breaker_condition", "depends_on",
}
EXPECTED_URGENT = {
    "credible_security_compromise", "unintended_public_disclosure",
    "customer_impacting_production_failure", "cost_anomaly_above_configured_threshold",
    "external_deadline_within_48_hours",
}
REQUIRED_PROTECTED = {
    ".github/workflows/**", "config/automation-policy.yml",
    "config/*.schema.json", "app/automation/**", "scripts/founder_ops.py",
    "tests/automation/**", "alembic/**", "migrations/**",
    "docs/legal/**", "docs/methodology/**", "**/*readiness*",
    "**/*security-exception*", "**/*secret*", "**/*credential*",
    "requirements.txt", "requirements-dev.txt", "pyproject.toml",
    "frontend/package.json", "frontend/package-lock.json", "**/*lock*",
    "frontend/vercel.json", "Procfile", "app/hazards/**", "app/scoring/**",
    "app/loss/**", "app/schemas/release_manifest.py", "app/services/release_manifest.py",
}
NOTIFICATIONS = {
    "weekly_digest_only",
    "weekly digest; urgent router only for enumerated conditions",
}


class PolicyValidationError(ValueError):
    """Policy is incomplete, contradictory, or unsafe."""


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load JSON-compatible YAML without an unpinned parser dependency."""
    try:
        policy_path = Path(path)
        data = json.loads(policy_path.read_text())
        schema = json.loads(policy_path.with_name("automation-policy.schema.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyValidationError(f"policy is unreadable or malformed: {exc}") from exc
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda item: list(item.path))
    if schema_errors:
        details = "; ".join(f"{'.'.join(map(str, item.path)) or '<root>'}: {item.message}" for item in schema_errors)
        raise PolicyValidationError(f"policy schema validation failed: {details}")
    validate_policy(data)
    return data


def validate_policy(policy: dict[str, Any]) -> None:
    errors: list[str] = []
    classes = policy.get("execution_classes")
    expected_classes = [item.value for item in ActionClass]
    if classes != expected_classes:
        errors.append("execution_classes must contain exactly the supported classes")
    defaults = policy.get("defaults", {})
    if defaults.get("unknown_action") != "AUTO-BLOCK" or defaults.get("action_class") != "AUTO-BLOCK":
        errors.append("unknown and default actions must fail closed as AUTO-BLOCK")
    budget = policy.get("founder_budget", {})
    if not isinstance(budget.get("max_decisions"), int) or not 0 <= budget.get("max_decisions", -1) <= 3:
        errors.append("founder max_decisions must be an integer from 0 to 3")
    if not isinstance(budget.get("max_repository_minutes"), int) or not 0 <= budget.get("max_repository_minutes", -1) <= 60:
        errors.append("founder max_repository_minutes must be an integer from 0 to 60")
    if set(policy.get("urgent_notifications", [])) != EXPECTED_URGENT:
        errors.append("urgent notification definitions must match the approved closed set")
    horizons = policy.get("digest_horizons", {})
    for key in ("external_deadline_days", "exception_expiry_days"):
        if not isinstance(horizons.get(key), int) or not 1 <= horizons.get(key, 0) <= 90:
            errors.append(f"digest horizon {key} must be an integer from 1 to 90 days")
    retention = policy.get("artifact_retention_days")
    if not isinstance(retention, int) or not 1 <= retention <= 90:
        errors.append("artifact retention must be an integer from 1 to 90 days")
    phase2 = policy.get("phase2", {})
    if phase2.get("bootstrap_required") is not True:
        errors.append("Phase 2 protected bootstrap must require one manual merge")
    if phase2.get("istanbul_digest_cron") != "0 6 * * 5":
        errors.append("Istanbul Friday 09:00 schedule must be explicit UTC cron 0 6 * * 5")
    if not phase2.get("trusted_automation_actors") or not phase2.get("required_pr_checks"):
        errors.append("Phase 2 requires trusted actors and exact required check names")
    if not phase2.get("trusted_issue_creators") or phase2.get("trusted_issue_label") != "georisk-automation-state":
        errors.append("Phase 2 requires default-branch trusted issue creators and label")
    if phase2.get("github_pagination") != {"maximum_pages": 10, "maximum_items": 1000, "page_size": 100}:
        errors.append("GitHub pagination bounds must match the fail-closed client contract")
    dependency_policy = phase2.get("dependency_policy", {})
    if dependency_policy != {
        "maximum_high": 0, "maximum_critical": 0, "audit_evidence_required": True,
        "exceptions_must_be_independently_approved_scoped_and_expiring": True,
    }:
        errors.append("dependency policy must fail closed on high/critical or missing audit evidence")
    protected = set(policy.get("protected_resources", []))
    if not REQUIRED_PROTECTED <= protected:
        errors.append("protected_resources does not cover every mandatory protected file family")
    auto = policy.get("auto_merge", {})
    allowed, prohibited = set(auto.get("allowed_resources", [])), set(auto.get("prohibited_resources", []))
    if allowed & prohibited:
        errors.append("auto-merge allowlist and exclusions conflict")
    if not protected <= prohibited:
        errors.append("every protected resource must be excluded from auto-merge")
    if not isinstance(auto.get("max_files"), int) or auto.get("max_files", 0) < 1:
        errors.append("auto-merge max_files is malformed")
    if not isinstance(auto.get("max_diff_lines"), int) or auto.get("max_diff_lines", 0) < 1:
        errors.append("auto-merge max_diff_lines is malformed")

    workflows = policy.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        errors.append("workflows must be a non-empty list")
        workflows = []
    ids = [workflow.get("id") for workflow in workflows if isinstance(workflow, dict)]
    if len(ids) != len(set(ids)):
        errors.append("workflow IDs must be unique")
    known_ids = set(ids)
    prefixes = tuple(policy.get("valid_trigger_prefixes", []))
    for index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            errors.append(f"workflow {index} must be an object")
            continue
        wid = workflow.get("id", f"index-{index}")
        missing = MANDATORY_WORKFLOW_FIELDS - workflow.keys()
        if missing:
            errors.append(f"workflow {wid} missing fields: {sorted(missing)}")
        unknown = set(workflow) - MANDATORY_WORKFLOW_FIELDS
        if unknown:
            errors.append(f"workflow {wid} has unknown fields: {sorted(unknown)}")
        if workflow.get("action_class") not in expected_classes:
            errors.append(f"workflow {wid} has unknown action class")
        trigger = workflow.get("trigger")
        trigger_parts = trigger.split(";") if isinstance(trigger, str) else []
        if not trigger_parts or not prefixes or not all(part.strip().startswith(prefixes) for part in trigger_parts):
            errors.append(f"workflow {wid} has invalid trigger")
        retries, timeout = workflow.get("maximum_retries"), workflow.get("timeout_minutes")
        if not isinstance(retries, int) or not 0 <= retries <= 3:
            errors.append(f"workflow {wid} retry bound is invalid")
        if not isinstance(timeout, int) or not 1 <= timeout <= 60:
            errors.append(f"workflow {wid} timeout is invalid")
        if workflow.get("notification_policy") not in NOTIFICATIONS:
            errors.append(f"workflow {wid} notification policy is invalid")
        if not isinstance(workflow.get("circuit_breaker_condition"), str) or not workflow.get("circuit_breaker_condition", "").strip():
            errors.append(f"workflow {wid} requires a circuit breaker")
        resource_conflict = set(workflow.get("allowed_resources", [])) & set(workflow.get("prohibited_actions", []))
        if resource_conflict:
            errors.append(f"workflow {wid} has contradictory allowed/prohibited entries")
        dependencies = workflow.get("depends_on", [])
        if not isinstance(dependencies, list) or any(dep not in known_ids or dep == wid for dep in dependencies):
            errors.append(f"workflow {wid} has invalid dependency reference")
    dependency_map = {
        workflow.get("id"): workflow.get("depends_on", []) for workflow in workflows if isinstance(workflow, dict)
    }
    def has_cycle(node: str, visiting: set[str], visited: set[str]) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        cyclic = any(dep in dependency_map and has_cycle(dep, visiting, visited) for dep in dependency_map.get(node, []))
        visiting.remove(node)
        visited.add(node)
        return cyclic
    visited: set[str] = set()
    if any(has_cycle(node, set(), visited) for node in dependency_map):
        errors.append("workflow dependencies must be acyclic")
    if errors:
        raise PolicyValidationError("; ".join(errors))

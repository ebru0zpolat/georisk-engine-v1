from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.automation.blockers import resolve_blocker, upsert_blocker
from app.automation.classifier import classify_action
from app.automation.digest import generate_digest
from app.automation.evidence import build_evidence_record, read_evidence, write_evidence
from app.automation.models import (
    ActionClass, CheckResult, ClassificationInput, DigestInput, DiffStatistics,
    DatedDigestItem, FounderDecision, ReadinessSnapshot,
)
from app.automation.policy import PolicyValidationError, load_policy, validate_policy
from app.automation.reconciliation import reconcile

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


@pytest.fixture()
def policy() -> dict:
    return load_policy(ROOT / "config/automation-policy.yml")


def check(name: str = "exact_head_ci", state: str = "pass", *, sha: str = SHA, kind: str = "local") -> CheckResult:
    return CheckResult(name=name, state=state, source="local pytest", evidence_kind=kind, commit_sha=sha)


def action(**updates: object) -> ClassificationInput:
    values = dict(
        commit_sha=SHA, changed_paths=["docs/guide.md"],
        diff=DiffStatistics(files=1, additions=4, deletions=1),
        required_checks=["exact_head_ci"], observed_checks=[check()],
    )
    values.update(updates)
    return ClassificationInput(**values)


def decision(identifier: str, priority: int, *, urgent: str | None = None, minutes: int = 10) -> FounderDecision:
    return FounderDecision(
        decision_id=identifier, priority=priority, title=f"Decision {identifier}",
        recommended_option="Defer safely", alternatives=["Review evidence"],
        consequence_of_no_action="The item remains blocked", deadline=NOW,
        estimated_minutes=minutes, evidence_reference=f"evidence/{identifier}.json",
        urgent_event=urgent,
    )


def test_all_nine_workflows_validate(policy: dict) -> None:
    assert len(policy["workflows"]) == 9


@pytest.mark.parametrize("mutation", [
    lambda item: item["workflows"][0].pop("timeout_minutes"),
    lambda item: item["workflows"][0].update(action_class="UNKNOWN"),
    lambda item: item["workflows"].append(copy.deepcopy(item["workflows"][0])),
    lambda item: item["workflows"][0].update(timeout_minutes="30m"),
    lambda item: item["workflows"][0].update(depends_on=["missing"]),
    lambda item: item["workflows"][0].update(trigger="schedule: Friday; nonsense"),
    lambda item: item["defaults"].update(unknown_action="AUTO-PASS"),
])
def test_unknown_missing_malformed_and_unsafe_policy_fails(policy: dict, mutation) -> None:
    broken = copy.deepcopy(policy)
    mutation(broken)
    with pytest.raises(PolicyValidationError):
        validate_policy(broken)


@pytest.mark.parametrize("path", [
    ".github/workflows/ci.yml", "config/automation-policy.yml",
    "alembic/versions/change.py", "docs/methodology/formula.md",
])
def test_protected_changes_require_founder_decision(policy: dict, path: str) -> None:
    result = classify_action(action(changed_paths=[path]), policy)
    assert result.action_class == ActionClass.FOUNDER_DECISION


def test_ordinary_documentation_can_auto_pass(policy: dict) -> None:
    assert classify_action(action(), policy).action_class == ActionClass.AUTO_PASS


def test_ambiguous_or_missing_exact_head_evidence_blocks(policy: dict) -> None:
    assert classify_action(action(diff=DiffStatistics(files=2, additions=1, deletions=0)), policy).action_class == ActionClass.AUTO_BLOCK
    assert classify_action(action(observed_checks=[]), policy).action_class == ActionClass.AUTO_BLOCK
    assert classify_action(action(observed_checks=[check(sha="b" * 40)]), policy).action_class == ActionClass.AUTO_BLOCK


@pytest.mark.parametrize("state", ["skip", "unavailable", "fail"])
def test_nonpassing_checks_never_pass(policy: dict, state: str) -> None:
    assert classify_action(action(observed_checks=[check(state=state)]), policy).action_class == ActionClass.AUTO_BLOCK


def test_policy_change_cannot_self_authorize(policy: dict) -> None:
    result = classify_action(action(changed_paths=["config/automation-policy.yml"], workflow_or_policy_change=False), policy)
    assert result.action_class == ActionClass.FOUNDER_DECISION


def test_mandatory_founder_categories(policy: dict) -> None:
    for flag in (
        "security_exception", "readiness_change", "production_credential_or_access",
        "database_migration", "scientific_change", "customer_or_personal_data",
        "legal_regulatory_customer_content", "external_send_intent", "destructive_or_irreversible",
    ):
        assert classify_action(action(**{flag: True}), policy).action_class == ActionClass.FOUNDER_DECISION


def test_local_evidence_cannot_claim_ci() -> None:
    with pytest.raises(ValidationError):
        CheckResult(name="ci", state="pass", source="GitHub CI", evidence_kind="local", commit_sha=SHA)


def test_evidence_roundtrip_and_readiness_unchanged(tmp_path: Path, policy: dict) -> None:
    classification = classify_action(action(), policy)
    readiness = ReadinessSnapshot()
    record = build_evidence_record(
        repository="georisk-engine", branch="work", commit_sha=SHA,
        changed_paths=["docs/guide.md"], diff=DiffStatistics(files=1, additions=4, deletions=1),
        classification=classification, checks_required=["exact_head_ci"], checks_observed=[check()],
        timestamp=NOW, evidence_kind="local", blockers=[], readiness=readiness,
    )
    target = tmp_path / "evidence.json"
    write_evidence(record, target)
    assert read_evidence(target) == record
    assert read_evidence(target).readiness == readiness
    assert read_evidence(target).evidence_kind == "local"
    schema = __import__("json").loads((ROOT / "config/evidence-record.schema.json").read_text())
    Draft202012Validator(schema).validate(record.model_dump(mode="json"))


def test_duplicate_blockers_and_resolution_preserve_history() -> None:
    kwargs = dict(workflow_id="founder_digest", category="missing_check", resource="digest", evidence_version="v1", summary="check missing", observed_at=NOW)
    blockers = upsert_blocker([], **kwargs)
    blockers = upsert_blocker(blockers, **kwargs)
    assert len(blockers) == 1
    assert blockers[0].occurrences == 2
    resolved = resolve_blocker(blockers, blockers[0].blocker_id, NOW)
    assert resolved[0].status == "resolved"
    assert [entry["status"] for entry in resolved[0].history] == ["open", "open", "resolved"]


def test_digest_caps_nonurgent_preserves_urgent_and_calculates_minutes(policy: dict) -> None:
    decisions = [decision(str(i), i) for i in range(5)]
    decisions.append(decision("urgent", 0, urgent="credible_security_compromise", minutes=7))
    rendered = generate_digest(DigestInput(period_start=NOW, period_end=NOW, decisions=decisions), policy)
    assert rendered.count("### Decision") == 4
    assert "Decision urgent — **URGENT**" in rendered
    assert "**Estimated founder time:** 37 minutes" in rendered
    assert rendered.count("Decision deferred:") == 2


def test_digest_defers_decisions_over_minute_budget(policy: dict) -> None:
    rendered = generate_digest(DigestInput(
        period_start=NOW, period_end=NOW,
        decisions=[decision("large", 3, minutes=50), decision("overflow", 2, minutes=20)],
    ), policy)
    assert "**Estimated founder time:** 50 minutes" in rendered
    assert "Decision deferred: Decision overflow" in rendered


def test_routine_failure_is_not_urgent(policy: dict) -> None:
    rendered = generate_digest(DigestInput(period_start=NOW, period_end=NOW, decisions=[decision("ci", 1, urgent="routine_ci_failure")]), policy)
    assert "**URGENT**" not in rendered


def test_empty_digest_is_valid(policy: dict) -> None:
    rendered = generate_digest(DigestInput(period_start=NOW, period_end=NOW), policy)
    assert "## Required decisions\n\nNone." in rendered
    assert "## Autonomous work completed\n\nNone." in rendered
    assert rendered == (ROOT / "tests/automation/fixtures/empty_digest.md").read_text()


def test_digest_applies_configured_deadline_horizons(policy: dict) -> None:
    rendered = generate_digest(DigestInput(
        period_start=NOW, period_end=NOW,
        deadlines=[
            DatedDigestItem(item_id="soon", summary="Soon", due_at=NOW + timedelta(days=2)),
            DatedDigestItem(item_id="later", summary="Later", due_at=NOW + timedelta(days=40)),
        ],
        expiring_exceptions=[DatedDigestItem(item_id="expiry", summary="Exception", due_at=NOW + timedelta(days=20))],
    ), policy)
    assert "Soon" in rendered and "Later" not in rendered and "Exception" in rendered


def test_reconciliation_never_infers_completion_from_docs(policy: dict) -> None:
    report = reconcile(
        policy=policy, roadmap_path=ROOT / "docs/00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md",
        evidence=[], commit_sha=SHA, git_dirty=False, readiness=ReadinessSnapshot(),
    )
    assert report.items
    assert all(item.status == "policy_only_not_implemented" for item in report.items)
    assert report.readiness.production_eligible is False


def test_reconciliation_marks_exact_sha_pass_and_stale(policy: dict) -> None:
    classification = classify_action(action(), policy)
    record = build_evidence_record(
        repository="georisk", branch="work", commit_sha=SHA, changed_paths=["docs/guide.md"],
        diff=DiffStatistics(files=1, additions=4, deletions=1), classification=classification,
        checks_required=["workflow:founder_digest"],
        checks_observed=[check("workflow:founder_digest")], timestamp=NOW,
        evidence_kind="local", blockers=[], readiness=ReadinessSnapshot(),
    )
    exact = reconcile(policy=policy, roadmap_path=ROOT / "docs/00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md", evidence=[("e.json", record)], commit_sha=SHA, git_dirty=False, readiness=ReadinessSnapshot())
    assert next(item for item in exact.items if item.item_id == "founder_digest").status == "completed_with_evidence"
    stale = reconcile(policy=policy, roadmap_path=ROOT / "docs/00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md", evidence=[("e.json", record)], commit_sha="b" * 40, git_dirty=False, readiness=ReadinessSnapshot())
    assert next(item for item in stale.items if item.item_id == "founder_digest").status == "stale"

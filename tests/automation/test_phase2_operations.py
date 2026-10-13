from __future__ import annotations

import json
import re
import shutil
import subprocess
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.automation.artifacts import ArtifactManifest, build_manifest, verify_manifest, write_manifest
from app.automation.automerge import PullRequestFacts, authorize_native_auto_merge
from app.automation.blockers import system_blocker_id
from app.automation.checks import normalize_check_runs
from app.automation.circuit_breaker import CIRCUIT_MARKER, CircuitState, circuit_state
from app.automation.digest import generate_digest, reconciliation_digest_sections
from app.automation.github import GitHubAPIError, GitHubClient, GitHubPage, MAX_PAGES
from app.automation.issues import ExistingIssue, IssueAction, IssueInventory, marker, plan_issue
from app.automation.models import ActionClass, CheckResult, Classification, DigestInput, ReadinessSnapshot
from app.automation.policy import load_policy
from app.automation.reconciliation import ReconciliationItem, ReconciliationReport
from app.automation.schedule import FRIDAY_DIGEST_CRON, friday_digest_utc
from scripts import phase2_ops

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
NOW = datetime(2026, 8, 28, 6, tzinfo=timezone.utc)
REPO = "owner/repo"
CREATOR = "github-actions[bot]"
LABEL = "georisk-automation-state"


@pytest.fixture()
def policy() -> dict:
    return load_policy(ROOT / "config/automation-policy.yml")


def issue(number: int, body: str = "", *, author: str = CREATOR, labels: list[str] | None = None, state: str = "open") -> ExistingIssue:
    return ExistingIssue(number=number, title=f"Issue {number}", body=body, state=state, repository=REPO, author_login=author, labels=labels if labels is not None else [LABEL])


def inventory(issues: list[ExistingIssue], complete: bool = True) -> IssueInventory:
    return IssueInventory(repository=REPO, complete=complete, issues=issues)


def required_checks(policy: dict, sha: str = SHA, state: str = "pass") -> list[CheckResult]:
    return [CheckResult(name=name, state=state, source=f"GitHub check-run {i}", evidence_kind="ci", commit_sha=sha) for i, name in enumerate(policy["phase2"]["required_pr_checks"], 1)]


def make_manifest(tmp_path: Path, policy: dict, *, sha: str = SHA, artifact_type: str = "pr_classification") -> ArtifactManifest:
    names = ["classification.json", "pr-facts.json"] if artifact_type == "pr_classification" else ["checks.json", "founder-digest.md", "reconciliation.json"]
    for name in names:
        (tmp_path / name).write_text("digest\n" if name.endswith(".md") else "{}\n")
    built = build_manifest(directory=tmp_path, filenames=names, commit_sha=sha, workflow_run_id="42", generated_at=NOW, checks_observed=required_checks(policy, sha), artifact_type=artifact_type)
    write_manifest(built, tmp_path / "manifest.json")
    return built


def test_plain_documentation_path_flags_neither_private_flag() -> None:
    result = phase2_ops.path_indicators(["docs/business/example.md"])
    assert result == {
        "dependency_change": False,
        "readiness_change": False,
        "workflow_or_policy_change": False,
        "database_migration": False,
        "scientific_change": False,
        "legal_regulatory_customer_content": False,
        "customer_or_personal_data": False,
        "production_credential_or_access": False,
    }


@pytest.mark.parametrize("path", ["data/customer_profiles.json", "data/portfolio.csv", "notes/personal.md", "mail/confidential.txt", "CUSTOMER/PLAN.docx"])
def test_customer_or_personal_data_path_is_detected_case_insensitively(path: str) -> None:
    assert phase2_ops.path_indicators([path])["customer_or_personal_data"] is True


@pytest.mark.parametrize("path", ["config/credential.yml", "ops/secret.env", "service/auth-token.json", "CREDENTIALS/PRODUCTION.yml"])
def test_production_credential_or_access_path_is_detected_case_insensitively(path: str) -> None:
    assert phase2_ops.path_indicators([path])["production_credential_or_access"] is True


def test_multiple_paths_aggregate_both_private_flags() -> None:
    result = phase2_ops.path_indicators(["docs/business/note.md", "data/customer_profiles.json", "config/credentials.yml"])
    assert result["customer_or_personal_data"] is True and result["production_credential_or_access"] is True


def test_empty_path_collection_fails_closed_on_both_private_flags() -> None:
    result = phase2_ops.path_indicators([])
    assert result["customer_or_personal_data"] is False and result["production_credential_or_access"] is False


class FakePages(GitHubClient):
    def __init__(self, pages: dict[str, GitHubPage | Exception]):
        super().__init__(REPO, "token")
        self.pages = pages

    def request_page(self, method: str, path: str, payload=None) -> GitHubPage:
        value = self.pages[path]
        if isinstance(value, Exception):
            raise value
        return value


def next_link(page: int) -> str:
    return f'<https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page={page}>; rel="next"'


def raw_issue(number: int, body: str = "") -> dict:
    return {"number": number, "title": f"Issue {number}", "body": body, "state": "open", "user": {"login": CREATOR}, "labels": [{"name": LABEL}]}


def test_friday_schedule_is_deterministic() -> None:
    assert FRIDAY_DIGEST_CRON == "0 6 * * 5"
    assert friday_digest_utc(datetime(2026, 1, 2)).hour == friday_digest_utc(datetime(2026, 8, 28)).hour == 6


def test_paginated_issue_on_page_two_is_found() -> None:
    first = f"/repos/{REPO}/issues?state=all&per_page=100"
    second = f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page=2"
    client = FakePages({first: GitHubPage([raw_issue(i) for i in range(1, 101)], {"Link": next_link(2)}), second: GitHubPage([raw_issue(101, CIRCUIT_MARKER)], {})})
    result = client.list_issues()
    assert result.complete and len(result.issues) == 101
    assert circuit_state(result, trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.OPEN


def test_circuit_on_final_bounded_page_is_found() -> None:
    pages: dict[str, GitHubPage] = {}
    for page in range(1, MAX_PAGES + 1):
        key = f"/repos/{REPO}/issues?state=all&per_page=100" if page == 1 else f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page={page}"
        headers = {"Link": next_link(page + 1)} if page < MAX_PAGES else {}
        pages[key] = GitHubPage([raw_issue(page, CIRCUIT_MARKER if page == MAX_PAGES else "")], headers)
    assert circuit_state(FakePages(pages).list_issues(), trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.OPEN


@pytest.mark.parametrize("pages", [
    {f"/repos/{REPO}/issues?state=all&per_page=100": GitHubPage([], {"Link": "not-a-link"})},
    {f"/repos/{REPO}/issues?state=all&per_page=100": GitHubPage([], {"Link": f'<https://api.github.com/repos/{REPO}/issues?state=all&per_page=100>; rel="next"'})},
])
def test_malformed_or_repeated_pagination_fails_closed(pages: dict) -> None:
    with pytest.raises(GitHubAPIError):
        FakePages(pages).list_issues()


def test_max_page_boundary_with_next_fails_closed() -> None:
    pages = {}
    for page in range(1, MAX_PAGES + 1):
        key = f"/repos/{REPO}/issues?state=all&per_page=100" if page == 1 else f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page={page}"
        pages[key] = GitHubPage([], {"Link": next_link(page + 1)})
    with pytest.raises(GitHubAPIError, match="maximum page"):
        FakePages(pages).list_issues()


def test_intermediate_timeout_or_rate_limit_propagates() -> None:
    first = f"/repos/{REPO}/issues?state=all&per_page=100"; second = f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page=2"
    client = FakePages({first: GitHubPage([], {"Link": next_link(2)}), second: GitHubAPIError("rate limited")})
    with pytest.raises(GitHubAPIError): client.list_issues()


def test_only_complete_uncontaminated_inventory_can_close_circuit() -> None:
    assert circuit_state(inventory([]), trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.CLOSED
    assert circuit_state(None, trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.UNKNOWN
    assert circuit_state(inventory([], False), trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.UNKNOWN
    assert circuit_state(inventory([issue(1, CIRCUIT_MARKER, state="closed")]), trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.CLOSED
    assert circuit_state(inventory([issue(1, CIRCUIT_MARKER), issue(2, CIRCUIT_MARKER)]), trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.UNKNOWN


@pytest.mark.parametrize("candidate", [
    issue(1, CIRCUIT_MARKER, author="arbitrary-user"),
    issue(1, CIRCUIT_MARKER, labels=[]),
])
def test_untrusted_circuit_marker_is_contamination(candidate: ExistingIssue) -> None:
    assert circuit_state(inventory([candidate]), trusted_creators={CREATOR}, trusted_label=LABEL) == CircuitState.UNKNOWN


def test_canonical_issue_requires_complete_trusted_provenance() -> None:
    kwargs = dict(kind="founder-digest", identifier="canonical", title="Digest", body="No decisions", trusted_creators={CREATOR}, trusted_label=LABEL)
    created = plan_issue(inventory([]), **kwargs)
    assert created.action == IssueAction.CREATE and created.labels == [LABEL]
    trusted = issue(1, created.body); trusted.title = created.title
    assert plan_issue(inventory([trusted]), **kwargs).action == IssueAction.NOOP
    with pytest.raises(ValueError, match="incomplete"): plan_issue(inventory([], False), **kwargs)
    with pytest.raises(ValueError, match="contamination"): plan_issue(inventory([issue(2, created.body, author="user")]), **kwargs)
    with pytest.raises(ValueError, match="duplicate"): plan_issue(inventory([trusted, issue(3, created.body)]), **kwargs)


def raw_check(name: str, sha: str = SHA, conclusion: str = "success", identifier: int = 1) -> dict:
    return {"name": name, "head_sha": sha, "conclusion": conclusion, "id": identifier}


def test_check_normalization_preserves_actual_sha_and_rejects_mismatch() -> None:
    result = normalize_check_runs([raw_check("pytest")], SHA)
    assert result[0].commit_sha == SHA and result[0].state == "pass"
    with pytest.raises(GitHubAPIError, match="does not match"): normalize_check_runs([raw_check("pytest", "b" * 40)], SHA)


def test_check_mixed_sha_and_conflicting_duplicates_fail() -> None:
    with pytest.raises(GitHubAPIError): normalize_check_runs([raw_check("a"), raw_check("b", "b" * 40)], SHA)
    with pytest.raises(GitHubAPIError, match="duplicate"): normalize_check_runs([raw_check("a"), raw_check("a", conclusion="failure", identifier=2)], SHA)
    assert normalize_check_runs([raw_check("a", conclusion="neutral")], SHA)[0].state == "unavailable"


def test_check_pagination_is_complete() -> None:
    first = f"/repos/{REPO}/commits/{SHA}/check-runs?per_page=100"; second = f"https://api.github.com/checks?page=2"
    client = FakePages({first: GitHubPage({"check_runs": [raw_check("one")]}, {"Link": f'<{second}>; rel="next"'}), second: GitHubPage({"check_runs": [raw_check("two", identifier=2)]}, {})})
    assert [item.name for item in normalize_check_runs(client.list_check_runs(SHA), SHA)] == ["one", "two"]


def test_digest_manifest_full_verification(tmp_path: Path, policy: dict) -> None:
    built = make_manifest(tmp_path, policy, artifact_type="founder_digest")
    verify_manifest(built, tmp_path, SHA, expected_run_id="42", expected_type="founder_digest", expected_files={"checks.json", "founder-digest.md", "reconciliation.json"}, required_checks=set(policy["phase2"]["required_pr_checks"]))
    with pytest.raises(ValueError, match="run ID"): verify_manifest(built, tmp_path, SHA, expected_run_id="wrong")
    with pytest.raises(ValueError, match="wrong-SHA"): verify_manifest(built, tmp_path, "b" * 40)
    (tmp_path / "founder-digest.md").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"): verify_manifest(built, tmp_path, SHA)


@pytest.mark.parametrize("mutation,match", [
    (lambda p: (p / "unexpected.txt").write_text("x"), "unexpected"),
    (lambda p: (p / "checks.json").unlink(), "missing"),
    (lambda p: (p / "founder-digest.md").unlink() or (p / "founder-digest.md").symlink_to("checks.json"), "symlink"),
])
def test_digest_manifest_rejects_unexpected_missing_and_symlink(tmp_path: Path, policy: dict, mutation, match: str) -> None:
    built = make_manifest(tmp_path, policy, artifact_type="founder_digest"); mutation(tmp_path)
    with pytest.raises(ValueError, match=match): verify_manifest(built, tmp_path, SHA)


def test_manifest_model_rejects_duplicate_and_unsafe_paths(tmp_path: Path, policy: dict) -> None:
    built = make_manifest(tmp_path, policy)
    payload = built.model_dump(mode="json"); payload["files"].append(payload["files"][0])
    with pytest.raises(ValueError, match="duplicate"): ArtifactManifest.model_validate(payload)
    payload = built.model_dump(mode="json"); payload["files"][0]["path"] = "../digest.md"
    with pytest.raises(ValueError, match="unsafe"): ArtifactManifest.model_validate(payload)


def test_verification_failure_prevents_digest_sync(tmp_path: Path, policy: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    make_manifest(tmp_path, policy, artifact_type="founder_digest"); (tmp_path / "founder-digest.md").write_text("tampered")
    called = False
    def forbidden(*args, **kwargs):
        nonlocal called; called = True
    monkeypatch.setattr(phase2_ops, "sync_digest", forbidden)
    with pytest.raises(ValueError): phase2_ops.publish_digest(Namespace(artifact_dir=str(tmp_path), expected_sha=SHA, expected_run_id="42"), policy)
    assert not called


def test_native_authorization_remains_bounded(tmp_path: Path, policy: dict) -> None:
    built = make_manifest(tmp_path, policy)
    facts = PullRequestFacts(number=7, head_sha=SHA, actor=policy["phase2"]["trusted_automation_actors"][0], head_repository=REPO, base_repository=REPO, draft=False)
    classification = Classification(action_class=ActionClass.AUTO_PASS, reasons=["eligible"])
    assert authorize_native_auto_merge(facts=facts, classification=classification, manifest=built, policy=policy, circuit=CircuitState.CLOSED).allowed
    assert not authorize_native_auto_merge(facts=facts, classification=classification, manifest=built, policy=policy, circuit=CircuitState.UNKNOWN).allowed


def write_pr_artifact(tmp_path: Path, policy: dict, checks: list[CheckResult]) -> dict:
    actor = policy["phase2"]["trusted_automation_actors"][0]
    facts = PullRequestFacts(number=7, head_sha=SHA, actor=actor, head_repository=REPO, base_repository=REPO, draft=False)
    (tmp_path / "pr-facts.json").write_text(json.dumps(facts.model_dump(mode="json")) + "\n")
    (tmp_path / "classification.json").write_text(json.dumps(Classification(action_class=ActionClass.AUTO_PASS, reasons=["eligible"]).model_dump(mode="json")) + "\n")
    built = build_manifest(directory=tmp_path, filenames=["classification.json", "pr-facts.json"], commit_sha=SHA, workflow_run_id="42", generated_at=NOW, checks_observed=checks, artifact_type="pr_classification")
    write_manifest(built, tmp_path / "manifest.json")
    return {"number": 7, "head": {"sha": SHA, "repo": {"full_name": REPO}}, "base": {"repo": {"full_name": REPO}}, "user": {"login": actor}, "draft": False}


def with_failing(checks: list[CheckResult], name: str) -> list[CheckResult]:
    return [item.model_copy(update={"state": "fail"}) if item.name == name else item for item in checks]


def test_red_required_check_in_artifact_is_a_named_refusal_not_a_crash(tmp_path: Path, policy: dict, capsys: pytest.CaptureFixture[str]) -> None:
    red = with_failing(required_checks(policy), "dependency-security")
    current_pr = write_pr_artifact(tmp_path, policy, red)
    allowed, facts = phase2_ops._authorize(tmp_path, policy, current_pr, red, inventory([]), "42")
    assert not allowed and facts.number == 7
    result = json.loads(capsys.readouterr().out)
    assert result["allowed"] is False
    assert any("evaluator artifact: dependency-security" in reason for reason in result["reasons"])


def test_red_required_check_on_github_now_is_a_named_refusal(tmp_path: Path, policy: dict, capsys: pytest.CaptureFixture[str]) -> None:
    current_pr = write_pr_artifact(tmp_path, policy, required_checks(policy))
    allowed, _ = phase2_ops._authorize(tmp_path, policy, current_pr, with_failing(required_checks(policy), "pytest"), inventory([]), "42")
    assert not allowed
    reasons = json.loads(capsys.readouterr().out)["reasons"]
    assert reasons == [f"required checks not passing at {SHA} on GitHub now: pytest"]


def test_green_required_checks_still_reach_the_authorizer(tmp_path: Path, policy: dict, capsys: pytest.CaptureFixture[str]) -> None:
    current_pr = write_pr_artifact(tmp_path, policy, required_checks(policy))
    allowed, _ = phase2_ops._authorize(tmp_path, policy, current_pr, required_checks(policy), inventory([]), "42")
    reasons = json.loads(capsys.readouterr().out)["reasons"]
    assert allowed == (reasons == ["eligible for GitHub native auto-merge"])
    assert not any("required checks not passing" in reason for reason in reasons)


def test_tampered_artifact_still_raises_before_the_check_refusal(tmp_path: Path, policy: dict) -> None:
    red = with_failing(required_checks(policy), "dependency-security")
    current_pr = write_pr_artifact(tmp_path, policy, red)
    (tmp_path / "classification.json").write_text(json.dumps({"action_class": ActionClass.AUTO_PASS.value, "reasons": ["tampered"]}) + "\n")
    with pytest.raises(ValueError, match="checksum"):
        phase2_ops._authorize(tmp_path, policy, current_pr, red, inventory([]), "42")


def test_manifest_required_check_failure_names_the_check(tmp_path: Path, policy: dict) -> None:
    built = make_manifest(tmp_path, policy, artifact_type="founder_digest")
    built = built.model_copy(update={"checks_observed": with_failing(built.checks_observed, "verify-eal")})
    with pytest.raises(ValueError, match=r"provenance is incomplete: not passing at a{40}: verify-eal$"):
        verify_manifest(built, tmp_path, SHA, required_checks=set(policy["phase2"]["required_pr_checks"]))


def test_all_workflow_actions_are_immutable_shas() -> None:
    action = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        for line in path.read_text().splitlines():
            if "uses:" not in line: continue
            value = line.split("uses:", 1)[1].split("#", 1)[0].strip()
            assert value.startswith("./") or action.fullmatch(value), f"mutable action in {path}: {value}"


def test_workflow_separation() -> None:
    all_text = "\n".join(path.read_text() for path in (ROOT / ".github/workflows").glob("*.yml"))
    evaluation = (ROOT / ".github/workflows/phase2-pr-evaluation.yml").read_text()
    privileged = (ROOT / ".github/workflows/phase2-native-automerge.yml").read_text()
    assert "pull_request_target" not in all_text
    assert "ref: ${{ github.event.repository.default_branch }}" in evaluation
    assert "gh api" not in privileged
    assert "authorize-online" in privileged and "--match-head-commit" in privileged
    assert ReadinessSnapshot().production_eligible is False


def workflow_text(name: str) -> str:
    return (ROOT / ".github/workflows" / name).read_text()


def test_privileged_consumer_downloads_the_artifact_the_evaluator_uploads() -> None:
    evaluation = workflow_text("phase2-pr-evaluation.yml")
    privileged = workflow_text("phase2-native-automerge.yml")
    # The evaluator's own run ID is exactly what `workflow_run.id` resolves to one hop later.
    assert "name: phase2-classification-${{ github.run_id }}" in evaluation
    assert "name: phase2-classification-${{ github.event.workflow_run.id }}" in privileged
    assert "run-id: ${{ github.event.workflow_run.id }}" in privileged
    # At the privileged hop `workflow_run` describes the default-branch evaluation run, so its PR
    # number and head SHA describe that run rather than the pull request. Only the head SHA the
    # artifact itself carries, revalidated by `authorize-online`, may be used here.
    assert "workflow_run.pull_requests" not in privileged
    assert "workflow_run.head_sha" not in privileged


STREAK_FILTER = (
    '[.workflow_runs[] | select((.id | tostring) != $run_id)] '
    '| sort_by(.run_started_at) | reverse | .[0].conclusion // ""'
)


def test_circuit_breaker_reads_consecutive_not_lifetime_failures() -> None:
    text = workflow_text("phase2-circuit-breaker.yml")
    assert STREAK_FILTER in text
    # A lifetime `total_count` of failed runs opens the circuit on any later isolated failure.
    assert "status=failure" not in text and "total_count" not in text


def previous_conclusion(runs: list[dict], run_id: str) -> str:
    result = subprocess.run(
        ["jq", "-r", "--arg", "run_id", run_id, STREAK_FILTER],
        input=json.dumps({"workflow_runs": runs}), capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq evaluates the workflow's streak filter")
@pytest.mark.parametrize("preceding", ["success", "failure"])
def test_streak_filter_reports_only_the_immediately_preceding_run(preceding: str) -> None:
    runs = [
        {"id": 5, "run_started_at": "2026-08-25T10:00:00Z", "conclusion": "failure"},
        {"id": 4, "run_started_at": "2026-08-25T09:00:00Z", "conclusion": preceding},
        {"id": 3, "run_started_at": "2026-08-25T08:00:00Z", "conclusion": "failure"},
    ]
    # The older failure never contributes: only the run immediately before this one can open it.
    assert previous_conclusion(runs, "5") == preceding
    assert previous_conclusion(list(reversed(runs)), "5") == preceding
    assert previous_conclusion([runs[0]], "5") == ""
    assert previous_conclusion([], "5") == ""


class FakeDigestClient:
    repository = REPO

    def __init__(self, issues: list[ExistingIssue], check_names: list[str]) -> None:
        self._issues = issues
        self._check_names = check_names

    def list_check_runs(self, sha: str) -> list[dict]:
        return [raw_check(name, sha, identifier=index) for index, name in enumerate(self._check_names, 1)]

    def list_issues(self) -> IssueInventory:
        return IssueInventory(repository=REPO, complete=True, issues=self._issues)


def blocker_issue(number: int, identifier: str) -> ExistingIssue:
    return issue(number, f"{marker('blocker', identifier)}\n\nDetail")


def test_system_blocker_reaches_the_founder_digest(tmp_path: Path, policy: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    issues = [
        blocker_issue(11, "digest-artifact-verification"),
        blocker_issue(12, "blk_" + "0" * 16),
        issue(13, marker("founder-digest", "canonical")),
    ]
    monkeypatch.setattr(phase2_ops, "github_client", lambda: FakeDigestClient(issues, policy["phase2"]["required_pr_checks"]))
    phase2_ops.prepare_digest(Namespace(sha=SHA, run_id="99", output_dir=str(tmp_path)), policy)
    digest = (tmp_path / "founder-digest.md").read_text()
    # The workflow-raised blocker uses a readable marker identifier, so it is normalized onto the
    # canonical contract instead of being dropped while its canonical issue stays open.
    assert f"`{system_blocker_id('digest-artifact-verification')}`" in digest
    assert "system/digest-artifact-verification" in digest
    assert "`blk_0000000000000000`" in digest


def test_scheduled_digest_reflects_reconciliation_and_a_real_period(tmp_path: Path, policy: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(phase2_ops, "github_client", lambda: FakeDigestClient([], policy["phase2"]["required_pr_checks"]))
    phase2_ops.prepare_digest(Namespace(sha=SHA, run_id="99", output_dir=str(tmp_path)), policy)
    digest = (tmp_path / "founder-digest.md").read_text()
    report = json.loads((tmp_path / "reconciliation.json").read_text())
    policy_only = sum(1 for item in report["items"] if item["status"] == "policy_only_not_implemented")
    # The reconciliation report reaches the Markdown, not only the sidecar file.
    assert policy_only and f"{policy_only} roadmap or workflow items remain policy-only" in digest
    period = next(line for line in digest.splitlines() if line.startswith("**Period:**"))
    start, end = (datetime.fromisoformat(part.strip()) for part in period.removeprefix("**Period:**").split(" — "))
    assert (end - start).days == 7


def reconciliation_report(*statuses: str) -> ReconciliationReport:
    return ReconciliationReport(commit_sha=SHA, git_dirty=False, readiness=ReadinessSnapshot(), items=[
        ReconciliationItem(item_id=f"item-{index}", title=f"Item {index}", status=status, reason="reason", evidence_references=["evidence-1"])
        for index, status in enumerate(statuses, 1)
    ])


def test_reconciliation_sections_carry_decisions_completed_and_deferred(policy: dict) -> None:
    report = reconciliation_report("awaiting_founder_decision", "completed_with_evidence", "blocked", "policy_only_not_implemented")
    decisions, completed, deferred = reconciliation_digest_sections(report, now=NOW, policy=policy)
    assert [item.decision_id for item in decisions] == ["item-1"]
    assert decisions[0].evidence_reference == "evidence-1" and decisions[0].estimated_minutes > 0
    assert completed == ["Item 2 — reason (evidence: evidence-1)"]
    assert deferred[0].startswith("Item 3 — blocked") and deferred[-1].startswith("1 roadmap or workflow items")
    markdown = generate_digest(DigestInput(period_start=NOW, period_end=NOW, decisions=decisions, completed=completed, deferred=deferred), policy)
    assert "Record an explicit decision for Item 1" in markdown and "Item 2 — reason" in markdown

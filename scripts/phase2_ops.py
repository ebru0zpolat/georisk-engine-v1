#!/usr/bin/env python3
"""Trusted workflow entry points for Founder-Autonomous Operations Phase 2."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from app.automation.artifacts import ArtifactManifest, build_manifest, missing_required_checks, verify_manifest, write_manifest
from app.automation.automerge import AutoMergeAuthorization, PullRequestFacts, authorize_native_auto_merge
from app.automation.blockers import SYSTEM_WORKFLOW_ID, system_blocker_id
from app.automation.circuit_breaker import circuit_state
from app.automation.circuit_breaker import ACTIVATION_CONDITIONS
from app.automation.checks import normalize_check_runs
from app.automation.classifier import classify_action
from app.automation.digest import DIGEST_PERIOD, generate_digest, reconciliation_digest_sections
from app.automation.github import GitHubClient
from app.automation.issues import MARKER_RE, plan_issue, trusted_issue, urgent_issue_plan
from app.automation.models import (
    Blocker, CheckResult, Classification, ClassificationInput, DigestInput, DiffStatistics,
    ReadinessSnapshot,
)
from app.automation.policy import load_policy
from app.automation.reconciliation import reconcile

ROOT = Path(__file__).resolve().parents[1]
BLOCKER_MARKER_PREFIX = "blocker:"
CANONICAL_BLOCKER_ID = re.compile(r"^blk_[0-9a-f]{16}$")


def blocker_identity(identifier: str) -> tuple[str, str, str]:
    """Return the `(blocker_id, workflow_id, category)` for a trusted `blocker:<identifier>` marker.

    Workflow-emitted blockers already carry the canonical `blk_<hex16>` identity. Blockers raised by
    the trusted workflows themselves — such as `digest-artifact-verification` — use a readable
    identifier instead, so they are normalized onto the same contract and keep the readable name as
    their category. Without this the digest silently omits them while their issue stays open.
    """
    if CANONICAL_BLOCKER_ID.fullmatch(identifier):
        return identifier, "github", "material_blocker"
    return system_blocker_id(identifier), SYSTEM_WORKFLOW_ID, identifier


def read_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text())


def write_json(path: str | Path, value: object) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def github_client() -> GitHubClient:
    return GitHubClient(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], os.environ.get("GITHUB_API_URL", "https://api.github.com"))


def collect_checks(client: GitHubClient, sha: str) -> list[CheckResult]:
    return normalize_check_runs(client.list_check_runs(sha), sha)


def issue_provenance(policy: dict) -> tuple[set[str], str]:
    return set(policy["phase2"]["trusted_issue_creators"]), policy["phase2"]["trusted_issue_label"]


def path_indicators(paths: list[str]) -> dict[str, bool]:
    dependency_names = {"requirements.txt", "requirements-dev.txt", "pyproject.toml", "package.json", "package-lock.json"}
    return {
        "dependency_change": any(Path(path).name in dependency_names or "lock" in Path(path).name.lower() for path in paths),
        "readiness_change": any("readiness" in path.lower() or "release_manifest" in path for path in paths),
        "workflow_or_policy_change": any(path.startswith(".github/workflows/") or path.startswith("app/automation/") or path.startswith("config/automation-policy") for path in paths),
        "database_migration": any(path.startswith(("alembic/", "migrations/")) for path in paths),
        "scientific_change": any(path.startswith(("app/hazards/", "app/scoring/", "app/loss/", "docs/methodology/")) for path in paths),
        "legal_regulatory_customer_content": any(path.startswith(("docs/legal/", "docs/compliance/", "docs/04-investor/")) for path in paths),
        "customer_or_personal_data": any(
            any(token in path.lower() for token in ("customer", "portfolio", "personal", "confidential"))
            for path in paths
        ),
        "production_credential_or_access": any(
            any(token in path.lower() for token in ("credential", "secret", "auth"))
            for path in paths
        ),
    }


def prepare_digest(args: argparse.Namespace, policy: dict) -> None:
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    client = github_client()
    checks = collect_checks(client, args.sha)
    now = datetime.now(timezone.utc)
    blockers: list[Blocker] = []
    inventory = client.list_issues()
    creators, label = issue_provenance(policy)
    for issue in inventory.issues:
        match = MARKER_RE.search(issue.body)
        if issue.state != "open" or match is None or not match.group(1).startswith(BLOCKER_MARKER_PREFIX):
            continue
        if not trusted_issue(issue, repository=inventory.repository, creators=creators, label=label):
            raise ValueError("untrusted blocker marker contamination")
        identifier, workflow_id, category = blocker_identity(match.group(1).split(":", 1)[1])
        blockers.append(Blocker(
            blocker_id=identifier, workflow_id=workflow_id, category=category,
            resource=f"github-issue-{issue.number}", evidence_version=f"issue-{issue.number}",
            summary=issue.title, first_seen=now, last_seen=now, occurrences=1,
            history=[{"at": now.isoformat(), "status": "open"}],
        ))
    report = reconcile(
        policy=policy, roadmap_path=ROOT / policy["canonical_roadmap"], evidence=[],
        commit_sha=args.sha, git_dirty=False, readiness=ReadinessSnapshot(),
    )
    write_json(output / "reconciliation.json", report.model_dump(mode="json"))
    decisions, completed, deferred = reconciliation_digest_sections(report, now=now, policy=policy)
    digest_input = DigestInput(
        period_start=now - DIGEST_PERIOD, period_end=now, decisions=decisions,
        blockers=blockers, completed=completed, deferred=deferred,
    )
    (output / "founder-digest.md").write_text(generate_digest(digest_input, policy))
    write_json(output / "checks.json", [item.model_dump(mode="json") for item in checks])
    manifest = build_manifest(
        directory=output, filenames=["checks.json", "founder-digest.md", "reconciliation.json"],
        commit_sha=args.sha, workflow_run_id=args.run_id, generated_at=datetime.now(timezone.utc),
        checks_observed=checks, artifact_type="founder_digest",
    )
    write_manifest(manifest, output / "manifest.json")


def evaluate_pr(args: argparse.Namespace, policy: dict) -> None:
    pr = read_json(args.pr); files = read_json(args.files); checks = [CheckResult.model_validate(item) for item in read_json(args.checks)]
    paths = [item["filename"] for item in files]
    classification = classify_action(ClassificationInput(
        commit_sha=pr["head"]["sha"], changed_paths=paths,
        diff=DiffStatistics(files=len(paths), additions=sum(item.get("additions", 0) for item in files), deletions=sum(item.get("deletions", 0) for item in files)),
        required_checks=policy["phase2"]["required_pr_checks"], observed_checks=checks,
        **path_indicators(paths),
    ), policy)
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    write_json(output / "classification.json", classification.model_dump(mode="json"))
    write_json(output / "pr-facts.json", {
        "number": pr["number"], "head_sha": pr["head"]["sha"], "actor": pr["user"]["login"],
        "head_repository": pr["head"]["repo"]["full_name"], "base_repository": pr["base"]["repo"]["full_name"],
        "draft": pr["draft"], "dependency_or_lockfile_change": path_indicators(paths)["dependency_change"],
    })
    manifest = build_manifest(
        directory=output, filenames=["classification.json", "pr-facts.json"],
        commit_sha=pr["head"]["sha"], workflow_run_id=args.run_id,
        generated_at=datetime.now(timezone.utc), checks_observed=checks,
    )
    write_manifest(manifest, output / "manifest.json")


def evaluate_pr_online(args: argparse.Namespace, policy: dict) -> None:
    client = github_client()
    pr = client.request("GET", f"/repos/{client.repository}/pulls/{args.pr_number}")
    files = client.paginate(f"/repos/{client.repository}/pulls/{args.pr_number}/files?per_page=100")
    checks = collect_checks(client, pr["head"]["sha"])
    write_json("/tmp/phase2-pr.json", pr); write_json("/tmp/phase2-files.json", files)
    write_json("/tmp/phase2-checks.json", [item.model_dump(mode="json") for item in checks])
    args.pr, args.files, args.checks = "/tmp/phase2-pr.json", "/tmp/phase2-files.json", "/tmp/phase2-checks.json"
    evaluate_pr(args, policy)


def _authorize(directory: Path, policy: dict, current_pr: dict, current_checks: list[CheckResult], inventory, expected_run_id: str | None = None) -> tuple[bool, PullRequestFacts]:
    manifest = ArtifactManifest.model_validate(read_json(directory / "manifest.json"))
    facts = PullRequestFacts.model_validate(read_json(directory / "pr-facts.json"))
    classification = Classification.model_validate(read_json(directory / "classification.json"))
    # Integrity and PR-identity failures raise: they mean the artifact cannot be trusted at all.
    # A required check that is red is an ordinary refusal and is reported by name below.
    verify_manifest(
        manifest, directory, facts.head_sha, expected_run_id=expected_run_id,
        expected_type="pr_classification", expected_files={"classification.json", "pr-facts.json"},
    )
    if (
        current_pr["number"] != facts.number or current_pr["head"]["sha"] != facts.head_sha
        or current_pr["user"]["login"] != facts.actor
        or current_pr["head"]["repo"]["full_name"] != facts.head_repository
        or current_pr["base"]["repo"]["full_name"] != facts.base_repository
        or current_pr["draft"] != facts.draft
    ):
        raise ValueError("current PR facts do not match the trusted classification artifact")
    required = set(policy["phase2"]["required_pr_checks"])
    missing_in_artifact = missing_required_checks(manifest.checks_observed, required, facts.head_sha)
    missing_now = missing_required_checks(current_checks, required, facts.head_sha)
    if missing_in_artifact or missing_now:
        reasons = []
        if missing_in_artifact:
            reasons.append(f"required checks not passing at {facts.head_sha} in the evaluator artifact: {', '.join(missing_in_artifact)}")
        if missing_now:
            reasons.append(f"required checks not passing at {facts.head_sha} on GitHub now: {', '.join(missing_now)}")
        result = AutoMergeAuthorization(allowed=False, reasons=reasons)
    else:
        creators, label = issue_provenance(policy)
        result = authorize_native_auto_merge(
            facts=facts, classification=classification, manifest=manifest, policy=policy,
            circuit=circuit_state(inventory, trusted_creators=creators, trusted_label=label),
        )
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    return result.allowed, facts


def authorize(args: argparse.Namespace, policy: dict) -> bool:
    from app.automation.issues import IssueInventory
    allowed, facts = _authorize(
        Path(args.artifact_dir), policy, read_json(args.current_pr),
        [CheckResult.model_validate(item) for item in read_json(args.current_checks)],
        IssueInventory.model_validate(read_json(args.issues)), args.expected_run_id,
    )
    if args.github_output:
        with Path(args.github_output).open("a") as handle:
            handle.write(f"allowed={'true' if allowed else 'false'}\npr_number={facts.number}\nhead_sha={facts.head_sha}\n")
    return allowed


def authorize_online(args: argparse.Namespace, policy: dict) -> bool:
    directory = Path(args.artifact_dir)
    facts = PullRequestFacts.model_validate(read_json(directory / "pr-facts.json"))
    client = github_client()
    current_pr = client.request("GET", f"/repos/{client.repository}/pulls/{facts.number}")
    checks = collect_checks(client, current_pr["head"]["sha"])
    allowed, verified_facts = _authorize(directory, policy, current_pr, checks, client.list_issues(), args.expected_run_id)
    if args.github_output:
        with Path(args.github_output).open("a") as handle:
            handle.write(f"allowed={'true' if allowed else 'false'}\npr_number={verified_facts.number}\nhead_sha={verified_facts.head_sha}\n")
    return allowed


def sync_digest(args: argparse.Namespace, policy: dict) -> None:
    client = github_client(); inventory = client.list_issues(); body = Path(args.digest).read_text(); creators, label = issue_provenance(policy)
    client.apply_issue_plan(plan_issue(inventory, kind="founder-digest", identifier="canonical", title="GeoRisk weekly founder digest", body=body, trusted_creators=creators, trusted_label=label))


def publish_digest(args: argparse.Namespace, policy: dict) -> None:
    directory = Path(args.artifact_dir)
    manifest = ArtifactManifest.model_validate(read_json(directory / "manifest.json"))
    verify_manifest(
        manifest, directory, args.expected_sha, expected_run_id=args.expected_run_id,
        expected_type="founder_digest",
        expected_files={"checks.json", "founder-digest.md", "reconciliation.json"},
        required_checks=set(policy["phase2"]["required_pr_checks"]),
    )
    args.digest = str(directory / "founder-digest.md")
    sync_digest(args, policy)


def sync_system_blocker(args: argparse.Namespace, policy: dict) -> None:
    client = github_client(); inventory = client.list_issues(); creators, label = issue_provenance(policy)
    client.apply_issue_plan(plan_issue(
        inventory, kind="blocker", identifier=args.identifier,
        title=f"[AUTO-BLOCK] {args.title}", body=args.summary,
        trusted_creators=creators, trusted_label=label,
    ))


def open_circuit(args: argparse.Namespace, policy: dict) -> None:
    if args.reason not in ACTIVATION_CONDITIONS:
        raise ValueError("unknown circuit-breaker activation condition")
    client = github_client(); inventory = client.list_issues(); creators, label = issue_provenance(policy)
    client.apply_issue_plan(plan_issue(
        inventory, kind="circuit-breaker", identifier="global",
        title="[FOUNDER-DECISION] Automation circuit breaker is open",
        body=f"Activation condition: `{args.reason}`\n\nPrivileged automation is blocked. Reactivation requires an explicit founder decision after remediation evidence.",
        trusted_creators=creators, trusted_label=label,
    ))


def sync_urgent(args: argparse.Namespace, policy: dict) -> None:
    client = github_client(); inventory = client.list_issues(); creators, label = issue_provenance(policy)
    plan = urgent_issue_plan(
        inventory, event=args.event, summary=args.summary,
        evidence_reference=args.evidence_reference,
        urgent_events=policy["urgent_notifications"],
        trusted_creators=creators, trusted_label=label,
    )
    if plan is None:
        raise ValueError("event is not in the exact urgent-event policy list")
    client.apply_issue_plan(plan)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare-digest", "evaluate-pr"):
        item = sub.add_parser(name); item.add_argument("--output-dir", required=True); item.add_argument("--run-id", required=True)
        if name == "prepare-digest": item.add_argument("--sha", required=True)
        else:
            item.add_argument("--pr", required=True); item.add_argument("--files", required=True); item.add_argument("--checks", required=True)
    item = sub.add_parser("evaluate-pr-online"); item.add_argument("--output-dir", required=True); item.add_argument("--run-id", required=True); item.add_argument("--pr-number", required=True, type=int)
    item = sub.add_parser("authorize"); item.add_argument("--artifact-dir", required=True); item.add_argument("--issues", required=True); item.add_argument("--current-pr", required=True); item.add_argument("--current-checks", required=True); item.add_argument("--expected-run-id"); item.add_argument("--github-output")
    item = sub.add_parser("authorize-online"); item.add_argument("--artifact-dir", required=True); item.add_argument("--expected-run-id", required=True); item.add_argument("--github-output")
    item = sub.add_parser("sync-digest"); item.add_argument("--digest", required=True)
    item = sub.add_parser("publish-digest"); item.add_argument("--artifact-dir", required=True); item.add_argument("--expected-sha", required=True); item.add_argument("--expected-run-id", required=True)
    item = sub.add_parser("sync-system-blocker"); item.add_argument("--identifier", required=True); item.add_argument("--title", required=True); item.add_argument("--summary", required=True)
    item = sub.add_parser("open-circuit"); item.add_argument("--reason", required=True)
    item = sub.add_parser("sync-urgent"); item.add_argument("--event", required=True); item.add_argument("--summary", required=True); item.add_argument("--evidence-reference", required=True)
    args = parser.parse_args(); policy = load_policy(ROOT / "config/automation-policy.yml")
    if args.command == "prepare-digest": prepare_digest(args, policy)
    elif args.command == "evaluate-pr": evaluate_pr(args, policy)
    elif args.command == "evaluate-pr-online": evaluate_pr_online(args, policy)
    elif args.command == "authorize": authorize(args, policy)
    elif args.command == "authorize-online": authorize_online(args, policy)
    elif args.command == "sync-digest": sync_digest(args, policy)
    elif args.command == "publish-digest": publish_digest(args, policy)
    elif args.command == "sync-system-blocker": sync_system_blocker(args, policy)
    elif args.command == "open-circuit": open_circuit(args, policy)
    else: sync_urgent(args, policy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Founder-Autonomous Operations — Phase 2 design

## Trusted workflow topology

1. **CI:** read-only tests plus a fail-closed `npm audit --audit-level=high` check.
2. **Founder Digest / generate:** Friday `06:00 UTC` checkout of the exact default SHA, policy
   validation, GitHub check-run collection, read-only reconciliation, digest and checksum manifest.
   The digest covers the preceding seven days and reports the reconciliation outcome in its Markdown
   — decisions awaiting the founder, work completed with evidence, and deferred items — rather than
   retaining the report as a sidecar file only. Blockers raised by the trusted workflows themselves
   carry a readable marker identifier and are normalized onto the canonical `blk_<hex16>` contract so
   they appear alongside workflow blockers instead of being silently omitted.
3. **Founder Digest / issue:** separate `issues: write` job downloads the retained bundle and
   upserts one hidden-marker issue. Upload/download failure creates one canonical AUTO-BLOCK issue
   and fails the workflow.
4. **Phase 2 PR Evaluation:** triggered only after CI; checks out trusted default-branch code, never
   PR code, reads PR files and exact-head checks, classifies, checksums, and uploads evidence.
5. **Phase 2 Native Auto-Merge:** downloads only the trusted evaluator artifact, verifies checksums,
   PR/head/actor/fork/draft/dependencies/check provenance and circuit state, then uses `gh pr merge
   --auto --squash`. GitHub branch protection remains authoritative.
6. **Phase 2 Circuit Breaker:** a GitHub-controlled canonical issue is opened for the closed
   activation set. `repeated_privileged_workflow_failure` means *consecutive*: the failing run plus
   the immediately preceding completed run, never a lifetime failure total. Issue-query failure is
   UNKNOWN and blocks privileged work. Only a founder may reactivate by closing the issue after
   remediation evidence.

There is no `pull_request_target`, PR-controlled trusted artifact, direct merge bypass, deployment,
Linear write, external message, customer communication, readiness write, or production write.

## Issue identities and evidence retention

Issues use hidden markers `<!-- georisk-automation:<kind>:<stable-id> -->`. The digest always uses
`founder-digest:canonical`; blockers use their stable blocker ID; the global circuit uses
`circuit-breaker:global`. Repeated runs update one match. Duplicate matches fail closed. Resolved
blockers close the issue but retain append-only history in the artifact.

Markers are necessary but not sufficient. Canonical state additionally requires the exact
repository, a creator in the default-branch `trusted_issue_creators` allowlist, the
`georisk-automation-state` label, complete bounded pagination and exactly one trusted match. Any
untrusted matching marker is contamination; circuit state becomes UNKNOWN and privileged work
stops. Pagination follows GitHub `Link` relations for at most 10 pages / 1,000 items and never
interprets truncation, malformed links, repeated URLs, timeouts or rate limits as complete.

Artifacts are retained for 30 days. The digest bundle is named with the exact SHA. The PR
classification bundle is named with the evaluation run ID, because at the privileged `workflow_run`
hop the event describes the default-branch evaluation run rather than the pull request, so the PR
number and head SHA are not available there to name it; the privileged job downloads it scoped to
that same run ID and then revalidates SHA, run ID, checksums and current PR facts. `manifest.json`
records schema
version, workflow run ID, UTC generation timestamp, CI evidence kind, observed checks and SHA-256,
size and relative name for every detailed file. Verification rejects stale SHA, wrong provenance,
missing file, size drift or checksum drift. GitHub artifact retention is useful operational
evidence, **not immutable or compliance-grade storage**. Inputs are normalized metadata only; no
secrets, signed URLs, raw customer/personal data, credentials or provider payloads are retained.

## Auto-merge eligibility matrix

| Gate | Eligible | Fail-closed result |
|---|---|---|
| Repository-owned actor, same repository, non-draft | Required | AUTO-BLOCK authorization |
| Allowlisted bounded paths/diff | Required | AUTO-BLOCK or FOUNDER-DECISION for protected paths |
| No dependency/lockfile/protected/destructive/production-write change | Required | FOUNDER-DECISION for material/protected; otherwise AUTO-BLOCK |
| Every policy check passes at current PR head SHA | Required | AUTO-BLOCK; skip/unavailable never pass |
| Trusted artifact SHA/checksum/current PR SHA agree | Required | AUTO-BLOCK and circuit activation on schema/provenance failure |
| Dependency audit has zero high/critical or approved valid exception | Required | AUTO-BLOCK; automation cannot create an exception |
| Circuit state is CLOSED | Required | OPEN or API-unavailable UNKNOWN blocks |
| Artifact and required issue operation succeed | Required | AUTO-BLOCK; no gate is weakened |

Phase 2 only enables GitHub native auto-merge. It never claims that an `AUTO-PASS` classification is
a readiness, scientific-validation, licence, customer, legal or production approval.

## Reproducible workflow validation and action pins

`bash scripts/validate_workflows.sh` downloads actionlint **v1.7.12** from its versioned upstream
release and accepts the Linux AMD64 archive only after SHA-256
`8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` matches. CI and local
verification run the same command. Every external action reference is a full commit SHA:

| Action version | Upstream commit SHA |
|---|---|
| `actions/checkout@v4` | `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-python@v5` | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/setup-node@v4` | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `actions/upload-artifact@v4` | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `actions/download-artifact@v4` | `d3f86a106a0bac45b974a628896c90dbdf5c8093` |

The regression test rejects mutable `uses:` references. These SHAs were resolved from the
authoritative upstream Git tag refs; updates require a protected policy/workflow change.

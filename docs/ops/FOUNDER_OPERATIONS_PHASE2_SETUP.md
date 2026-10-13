# Founder-Autonomous Operations Phase 2 — one-time setup

**Bootstrap boundary:** this change modifies protected workflows, policy, classifiers, evidence
logic and their tests. It is therefore **FOUNDER-DECISION**, cannot approve itself, and requires one
manual bootstrap merge after independent exact-head CI review. This is a one-time control-plane
decision, not recurring approval for later eligible low-risk changes.

GitHub cron is UTC. Friday 09:00 `Europe/Istanbul` is Friday **06:00 UTC**, expressed as
`0 6 * * 5`. Türkiye has remained UTC+3 year-round since 2016, so there is no seasonal clock shift;
the workflow converts and tests the named timezone and never uses runner-local time.

## Setup checklist (42 minutes total)

| # | Exact GitHub setting/action | Recommended value | Verification evidence | Rollback/disable | Minutes |
|---:|---|---|---|---|---:|
| 1 | Git push for branch `work` | Push exact commit only | Remote branch SHA equals local `git rev-parse HEAD` | Delete remote branch | 3 |
| 2 | Pull requests → New pull request | Open Phase 2 bootstrap PR; no auto-merge label | PR head SHA and protected-file diff | Close PR unmerged | 3 |
| 3 | Rulesets/branch protection → required status checks | `pytest`, `frontend`, `verify-eal`, `founder-operations-phase-1`, `dependency-security` | Ruleset screenshot/export and exact-head check suite | Disable Phase 2 workflows; do not remove safety checks merely to merge | 5 |
| 4 | Settings → General → Pull Requests | Enable **Allow auto-merge** and squash merges | Repository setting plus canary PR merge queue state | Disable Allow auto-merge | 3 |
| 5 | Settings → Actions → General → Workflow permissions | Default **Read repository contents**; allow PR approval only if separately required; workflows retain job-level least privilege | Workflow permission setting and run permission summary | Disable Phase 2 workflows and set read-only | 4 |
| 6 | Settings → Actions → General → Artifact and log retention | 30 days, matching policy/workflow | Retained `founder-digest-<SHA>` manifest and expiry | Disable workflows/delete non-required artifacts | 3 |
| 7 | GitHub App/automation account and policy actor allowlist | Install repository-owned `georisk-automation[bot]` with only PR creation needed; exact login must match policy | App installation and canary PR actor | Suspend app and remove actor from allowlist through protected PR | 4 |
| 8 | Issues → Labels and workflow permission confirmation | Create `georisk-automation-state`; restrict canonical creators to policy `trusted_issue_creators`; digest issue job `issues: write`; privileged merge job `pull-requests: write`, `contents: write`; evaluators read-only | Label URL, policy actor match and Actions permission summaries | Disable individual workflows; leave circuit open | 3 |
| 9 | Actions → Founder Digest → Run workflow | One controlled default-branch run; confirm one canonical issue and checksummed 30-day artifact | Run URL, issue marker, manifest SHA/checksums | Disable workflow; close canonical issue | 5 |
| 10 | Repository-owned canary PR | One allowlisted small documentation correction with every required check passing | Exact-head classification artifact and native auto-merge record | Disable auto-merge workflow; revert canary normally | 5 |
| 11 | Circuit-breaker canary | Open marker via approved manual `suspected_credential_exposure` test, confirm auto-merge blocked, then founder closes after evidence review | Circuit issue, blocked authorization, closure audit | Disable privileged workflows; leave circuit issue open | 4 |

Do not proceed past step 3 while `dependency-security` is failing. The previous npm blocker was
remediated by refreshing the lockfile within declared ranges and replacing the risk-tile page's
unused `@deck.gl/geo-layers`/`deck.gl` dependency path with MapLibre's native raster source. A clean
local `npm ci` followed by `npm audit --audit-level=high` reports zero vulnerabilities; the blocker
is resolved only after the protected dependency change passes exact-head CI. Automation may
neither create nor extend an exception if a future audit fails.

After setup there is no daily monitoring. The Friday digest and canonical deduplicated issues are
the normal review surface; urgent issues are limited to the policy's exact closed list.

## Operational acceptance

Phase 2 becomes operational only after the bootstrap is on the default branch, all required
settings are verified, one scheduled/controlled digest run retains a valid exact-SHA artifact and
updates the canonical issue, one eligible canary uses GitHub native auto-merge without bypassing
branch protection, and the circuit-breaker canary blocks privileged action. Local tests or this
runbook alone do not satisfy those conditions.

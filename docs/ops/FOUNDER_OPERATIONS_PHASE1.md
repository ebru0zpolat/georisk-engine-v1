# Founder-Autonomous Operations — Phase 1 runbook

## Posture and boundary

Phase 1 is a **local, read-only artifact engine**. It validates the policy, classifies a proposed
repository action, validates exact-SHA evidence, reconciles policy and roadmap state, deduplicates
blockers and renders a weekly Markdown digest. It cannot merge, deploy, publish, message, create or
update issues, write Linear, use production credentials, or change readiness.

The GitHub check is read-only (`contents: read`) and has no production secret or write-token use.
Local success is not GitHub CI evidence. The workflow is not operational until it is on the default
branch and an exact-head CI run produces retained evidence.

## Commands

```bash
source .venv/bin/activate
PYTHONPATH=. python scripts/founder_ops.py validate-policy
PYTHONPATH=. python scripts/founder_ops.py reconcile --output /tmp/reconciliation.json
PYTHONPATH=. python scripts/founder_ops.py digest input.json --output /tmp/founder-digest.md
```

`reconcile` accepts repeatable `--evidence` paths and an optional read-only `--readiness` snapshot.
With no evidence, every policy workflow is truthfully reported as `policy_only_not_implemented`.
It never treats roadmap prose or a commit message as completion evidence.

## Classifier decision table

| Condition | Result | Meaning |
|---|---|---|
| Mandatory protected category/path | FOUNDER-DECISION | Queue for digest; this is not approval |
| Phase 1 production-write intent | AUTO-BLOCK | Stop; Phase 1 has no production writer |
| Missing/skip/unavailable/failing/wrong-SHA check | AUTO-BLOCK | Required evidence did not pass exact head |
| Ambiguous diff, excessive size, dependency change or non-allowlisted path | AUTO-BLOCK | No safe deterministic classification |
| Bounded allowlisted paths and every required exact-SHA check passes | AUTO-PASS | Classification only; Phase 1 does not merge |

Mandatory founder categories are security exceptions; workflow, policy or gate changes; readiness
changes; production credentials/privileged access; migrations; scientific formula/method changes;
customer/personal data; pricing, contract, legal, regulatory, customer or external communications;
and destructive/irreversible actions.

## Evidence contract

`EvidenceRecord` schema version `1.0` records repository, branch, 40-character exact commit SHA,
sorted changed paths, additions/deletions, classification and reasons, required and observed checks,
each check's pass/fail/skip/unavailable state and source, timestamp, blockers, readiness snapshot and
evidence kind (`local`, `ci`, `deployment`, or `external`). Check SHAs and kinds must equal their
containing record. A local source cannot claim to be GitHub CI. Skip and unavailable never satisfy
the classifier.

Blocker IDs are the first 16 hexadecimal characters of SHA-256 over the stable tuple workflow ID,
category, affected resource and evidence version. Re-observation increments one record; resolution
appends history and retains the record.

## Example zero-action digest

```markdown
# GeoRisk Founder Digest

**Estimated founder time:** 0 minutes

## Required decisions

None.

## Material blockers

None.

## Autonomous work completed

None.
```

The complete artifact also includes deadlines, expiring exceptions, deferred items and an explicit
no-send/no-write footer. Urgent decisions bypass the three non-urgent decision cap only when their
event identifier exactly matches the policy's closed urgent-event list. Ordinary CI failures,
unavailable live checks, stale drafts and unresolved blockers are not urgent.

## External configuration remaining

- Merge the implementation to the default branch and observe exact-head CI.
- Configure artifact retention if reconciliation/evidence/digest outputs must persist beyond CI.
- Configure the Friday schedule only in a later workflow change; the current check is PR/push only.
- Package GitHub/Linear permissions, issue deduplication and any notification route as a later,
  explicit founder setup. Phase 1 intentionally has none of those permissions.
- Keep auto-merge, deployment, content publishing, external send and production writes disabled.

# GeoRisk Engine — Founder-Autonomous Operating Roadmap

**Version:** 1.0 (25 August 2026)  
**Status:** canonical operating model; Phases 1–2 implemented locally, automation not operational
**Scope:** production, Netherlands controlled pilot, scientific validation, Türkiye/COP31,
content/distribution, applications, customer discovery and repository operations  
**Source of technical truth:** repository commits and evidence artifacts, not copied status in
Linear or narrative roadmaps.

This document replaces every routine-human-review instruction in the roadmaps. Domain-specific
documents still define scientific, legal and product requirements, but this document determines
who or what executes them. A conflict fails closed and is reconciled in the Friday digest.

## 1. Non-negotiable operating contract

The founder has one Friday review window and no daily repository duty. Every action has exactly
one class:

- **AUTO-PASS:** execute only inside a declared allowlist after every required check passes.
- **AUTO-BLOCK:** stop the affected action, retain state/evidence, upsert one deduplicated blocker,
  and continue unrelated work. Do not page or repeatedly remind the founder.
- **FOUNDER-DECISION:** queue a bounded decision because a material legal, financial, privacy,
  scientific, security, customer, production or reputational risk cannot be delegated.

Absence of a decision means defer: never infer consent, weaken a gate, publish/send externally,
spend money, use real customer data, promote readiness or wait indefinitely. Only a credible
security compromise, unintended public disclosure, customer-impacting production failure, cost
anomaly over the approved threshold, or external deadline within 48 hours may notify immediately.

## 2. Complete approval inventory

This inventory reconciles the approval points in the production roadmap, master plan, validation
work packages, six-month gates, distribution strategy and Türkiye materials. Rows cover recurring
workflow families as well as named work packages; execution details are in
[`automation-policy.yml`](../../config/automation-policy.yml).

| Approval | Current trigger | Risk protected | New class | Automation change | Residual human action |
|---|---|---|---|---|---|
| Routine PR review/merge | Any code or docs PR | Regression | AUTO-PASS when low-risk policy matches; otherwise AUTO-BLOCK or decision | Exact-head CI, coverage, security and path/diff classifier; bot cannot edit its gates | Decide only excluded/material changes |
| Tests, lint, type, build, schema | Push/PR/schedule | Quality | AUTO-PASS | CI runs and records SHA-bound evidence | None |
| Failed checks or unavailable credentials/network | Gate failure | Quality/integrity | AUTO-BLOCK | Safe-stop, bounded retry, deduplicated issue | None until selected in digest |
| Patch/minor dependencies | Update available | Supply chain | AUTO-PASS if policy and security gates pass | Allowlisted updater with rollback | Major updates/security exception only |
| Workflow, policy or gate edit | Protected path changes | Self-approval/security | FOUNDER-DECISION | Always excluded from auto-merge and bundled | Approve exact diff because it changes the control plane |
| Backlog/Linear/roadmap status | Commit merged or evidence expires | Status integrity | AUTO-PASS | SHA ledger drives reconciliation; Linear is a projection | Strategic deletion/abandonment only |
| Routine issue closure | Verified acceptance criteria | Evidence loss | AUTO-PASS for reversible/non-material work | Closure proposal and evidence link | Scientific/legal/customer/security/production issues never auto-close |
| Stale/duplicate/superseded work | Weekly reconciliation | Lost work | AUTO-PASS to label/link/extract; AUTO-BLOCK closure if protected | Deduplicate and propose safe closure | Close strategically important or protected work |
| Weekly reporting | Friday schedule | Awareness | AUTO-PASS | Generate one capped digest | Review at most three decisions |
| Preview/non-production deploy | Approved branch artifact | Availability | AUTO-PASS | Deploy, smoke, rollback automatically | None |
| Production publication under existing policy | Release artifact passes all declared gates | Customer/availability | AUTO-PASS only for already-approved, reversible release class | Exact-release smoke and automatic rollback | New eligibility, privileged access or irreversible infrastructure |
| Production secret/privileged access | Credential or permission change | Security | FOUNDER-DECISION | Draft change plan only | Authorize exact access because compromise blast radius is material |
| Database/provider/framework/architecture migration | Major boundary change | Irreversibility/data loss | FOUNDER-DECISION | Generate plan, backup/restore evidence and rollback rehearsal | Authorize migration window |
| Security finding | Scanner result | Security | AUTO-BLOCK until remedied | Quarantine; one issue | Create/extend a time-bound exception only |
| Content topic selection and editorial review | Weekly publication | Reputation | AUTO-PASS for evidence-grounded allowlisted topics | Harvest, draft, B1–B7, exact-head CI, publish and verify | None for routine content |
| Prohibited/unsupported content claim | Claim has weak/confidential/endorsement/readiness/legal content | Legal/reputation | AUTO-BLOCK and skip | Claims ledger records reason; valuable topics appear as optional digest item | Select only if material review is worthwhile |
| Bilingual publication | Source supports audience/language | Accuracy | AUTO-PASS | Generate and validate canonical/hreflang parity | None |
| Sitemap/RSS/`llms.txt`/canonical/hreflang/schema | Content merge/deploy | Discoverability | AUTO-PASS | Deterministic generation and deployed-URL validation | None |
| AHN/NCG/BAG/Aqueduct/source health and provenance | Schedule/source change | Scientific/licence integrity | AUTO-PASS when checks pass; AUTO-BLOCK otherwise | Contract tests, manifests, expiry/change checks | Resolve ambiguous licence/legal interpretation only |
| Label verified observation | Evidence pack complete | Scientific truth | AUTO-PASS only under pre-approved objective evidence rule; otherwise AUTO-BLOCK | Machine evaluates provenance, date, hash and contract—not mere HTTP success | Interpret genuinely inconclusive evidence |
| Formula/methodology version check | Code/data change | Scientific validity | AUTO-PASS validation; protected change is FOUNDER-DECISION | Detect drift and invalidate affected evidence | Approve scientific-method change because conclusions may change |
| Pilot evidence pack/reconciliation | Weekly or release candidate | Readiness truth | AUTO-PASS generation; AUTO-BLOCK incompleteness | Generate SHA-bound pack and evaluate manifest | None unless eligibility is proposed |
| Change controlled-pilot/production eligibility | Release decision | Customer/scientific/security exposure | FOUNDER-DECISION | Automation may recommend but never write status | Decide named release after independent evidence |
| Real-event validation and independent review | Preregistered study | Scientific validity | AUTO-PASS computation; AUTO-BLOCK missing data/review | Reproducibility suite and immutable evidence | Appoint reviewer; decide abandonment of evidence; reviewer independently signs |
| EU Taxonomy / ESRS E1-9 conclusion | Proposed claim | Regulatory/legal | FOUNDER-DECISION | Draft evidence mapping only; default no claim | Approve only after qualified interpretation |
| Use real customer/portfolio/personal/confidential data | Pilot proposal/ingest | Privacy/contracts | FOUNDER-DECISION | Synthetic fixtures remain default; prepare boundary checklist | Authorize scoped collection/use and terms |
| Türkiye/COP31/YİDEP/UNFCCC monitoring | Weekly research schedule | Accuracy | AUTO-PASS | Archive primary sources, validate claims, sync demonstrator docs | None for internal factual research |
| Türkiye demonstrator build | Code/doc change | Technical quality | AUTO-PASS within its isolated lane | Build/test without changing NL dependencies | Commit GeoRisk externally to demonstrator only |
| Public institutional/alignment/partner claim | Draft content/outreach | Endorsement/legal | FOUNDER-DECISION | Automatically withhold and bundle | Approve substantiated wording because it implies endorsement/alignment |
| Application, proposal, LOI, outreach or follow-up preparation | Pipeline schedule | Efficiency | AUTO-PASS | Generate brief, agenda, evidence table, draft and missing-evidence list | None until external action |
| Interview/negotiation/application submission or message in founder name | External interaction | Binding/relationship risk | FOUNDER-DECISION | Batch draft and recommended next action | Attend, confirm representations/terms, send or sign |
| Pricing, purchase, funding, contract or material cost change | Commercial action | Financial/legal | FOUNDER-DECISION | Prepare options and cost evidence | Choose/accept because it creates a commitment |
| Routine operational monitoring | Scheduled checks | Reliability | AUTO-PASS/AUTO-BLOCK | Retry then safe-stop; no continuous founder monitoring | Only urgent incident criteria page immediately |
| Deletion of material data or evidence | Retention action | Irreversibility | FOUNDER-DECISION | Produce inventory and reversible archive plan | Explicitly authorize deletion |

### Approvals removed

Routine editorial review, routine maintainer review, manual test/evidence runs, deterministic
artifact approval, manual status copying, preview approval, fixture maintenance, non-material
metadata review, weekly report assembly and repeated blocker acknowledgement are removed. Older
phrases such as “human review” mean the class above: automated objective checks unless the changed
resource is protected for a stated material risk.

### Approvals retained and why

Founder decisions remain only for binding external communications/terms (legal and relationship
risk), money or material cost (financial risk), real or regulated data (privacy/contract risk),
privileged production access and irreversible infrastructure (security/availability risk), major
technical migrations (systemic/rollback risk), security exceptions (accepted residual risk),
unresolved legal/licence/IP/privacy interpretation (legal risk), scientific-method changes and
eligibility promotion (invalid conclusions/customer reliance), endorsement/alignment claims
(reputation/misrepresentation), and material deletion/abandonment (irreversible evidence loss).

## 3. Reconciled work packages and gates

| Lane / existing package | Routine execution | Fail-closed condition | Founder decision | Acceptance evidence |
|---|---|---|---|---|
| Production Stages 0–2: backlog, Dutch sources, demo | AUTO-PASS reconciliation, contract/fixture tests, bounded preview | AUTO-BLOCK stale head, missing licence, failed live smoke | Real data boundary or protected change | SHA ledger, source manifest, CI and smoke artifact |
| Production Stage 3: operational baseline | AUTO-PASS scans, restore/rollback rehearsal and monitoring | AUTO-BLOCK failed security/restore/smoke | Secrets, privileged access, migration, eligibility | Exact-release operational pack |
| Production Stages 4–5 / validation WP-01–12 | AUTO-PASS claim tests, provenance, computation, golden/reproducibility checks | AUTO-BLOCK missing/contradictory licence, event, observation or review | Formula/method change; abandon evidence; eligibility | Versioned methodology, preregistration, independent report |
| Production Stage 6 / commercial gates | AUTO-PASS briefs, drafts, summaries and evidence tables | AUTO-BLOCK unsupported representation or missing evidence | Interviews, terms, send/sign, paid commitment | Dated external evidence; executed agreement when required |
| Production Stage 7 / release gate | AUTO-PASS manifest evaluation only | AUTO-BLOCK any unmet/expired gate | Change pilot or production eligibility | Founder-signed named release record |
| Six-month Gate 1 scientific | AUTO-PASS compute/reconcile; protected issue stays open | AUTO-BLOCK unlicensed observations/reviewer gap | Reviewer appointment or evidence abandonment | Preregistered, reproduced, reviewed pack |
| Six-month Gates 2–3 demand/product | AUTO-PASS pipeline summaries and proposal drafts | AUTO-BLOCK unverifiable evidence | Relationship action, price, contract | Attributable interview/contract evidence |
| Content/distribution B1–B7 | AUTO-PASS harvest→draft→validate→merge→deploy→verify | AUTO-BLOCK prohibited claim, failed check/deploy; circuit opens after threshold | Optional prohibited topic, never routine editing | Claim ledger plus deployed checks bound to SHA |
| Netherlands source monitoring | AUTO-PASS health/provenance/licence-change detection | AUTO-BLOCK missing credential, source drift, expiry or ambiguity | Novel legal/licence interpretation | Timestamped manifests and contract tests |
| Türkiye/COP31 | AUTO-PASS internal monitoring/archive/build/draft; resource-isolated | AUTO-BLOCK unsupported alignment/endorsement | Contact, submit, partner naming, funding/duty, alignment claim | Archived source and build evidence; founder send record |
| Applications/discovery | AUTO-PASS preparation and batching | AUTO-BLOCK missing facts/confidential boundary | Attend, confirm, negotiate, send/sign | Weekly packet and external record |

The Türkiye lane has its own concurrency group and quota. It cannot modify Netherlands readiness,
consume its reserved CI capacity, add a blocking dependency to it, or change its priority. Türkiye
failure remains local.

## 4. Twelve-week approval budget

Counts are planning estimates, not evidence of execution. “Automated actions” includes checks,
generation, synchronization and monitoring. AUTO-BLOCK counts are expected deduplicated blocker
families. Founder minutes cover repository governance only; discovery/interviews/negotiations and
application attendance are separately scheduled and excluded.

| Week | Dominant work packages | Automated actions | Expected AUTO-BLOCK | Founder decisions | Founder minutes |
|---:|---|---:|---:|---:|---:|
| 1 | Policy/classification; backlog reconciliation | 32 | 2 | 1 | 30 |
| 2 | Digest; Dutch source foundation | 38 | 2 | 1 | 35 |
| 3 | Evidence sync; pilot demo | 45 | 2 | 1 | 35 |
| 4 | Low-risk auto-merge; demo completion | 52 | 2 | 1 | 40 |
| 5 | Content pipeline; operational baseline | 58 | 2 | 1 | 40 |
| 6 | Source monitoring; security/restore | 64 | 3 | 2 | 50 |
| 7 | Provenance; hazard semantics | 62 | 2 | 1 | 40 |
| 8 | Pilot evidence pack; methodology checks | 68 | 2 | 2 | 55 |
| 9 | Draft batching; validation execution | 61 | 2 | 1 | 40 |
| 10 | Validation/reproducibility; Türkiye monitor | 66 | 3 | 1 | 45 |
| 11 | Ops metrics; release evidence | 72 | 2 | 2 | 55 |
| 12 | Release evaluation and next-cycle reconciliation | 74 | 2 | 3 | 60 |

No lane may allocate more than three non-urgent decisions or 60 repository minutes in a week.
Overflow is deferred in priority order: optional content, Türkiye opportunities, noncritical
maintenance, then commercial drafts. It is never converted into repeated notification. Separate
founder calendar blocks may cover interviews, negotiations, applications and relationship work.

### Per-work-package steady-state budget

| Work package | Automated actions/week | AUTO-BLOCK/week | Decisions/week | Minutes/week (only when selected) |
|---|---:|---:|---:|---:|
| Repository + evidence sync | 18 | 1 | 0–1 | 15 |
| Content + distribution | 16 | 1 | 0 | 0 |
| Netherlands + scientific validation | 20 | 1 | 0–1 | 20 |
| Türkiye/COP31 | 8 | 1 | 0–1 | 10 |
| Applications/customer preparation | 10 | 1 | 0–1 | 15 |
| Operations/security/cost | 12 | 1 | 0–1 | 15 |

The digest selects at most three decisions total, so maxima are not additive.

## 5. Automation architecture and failure behaviour

1. **Classifier:** validates each proposed action against the machine-readable registry, protected
   paths and prohibited resources. Unknown or conflicting classification is AUTO-BLOCK.
2. **Evidence runner:** executes required checks against the exact head SHA and writes immutable
   manifests containing command, result, timestamp, inputs and artifact hashes.
3. **Ledger/reconciler:** keys evidence by commit SHA, updates GitHub state, projects status to
   Linear and generates roadmap deltas. Green CI is described only as CI, never readiness.
4. **Executors:** separate least-privilege identities and concurrency groups for maintenance,
   content, preview deployment, source monitoring, NL evidence and Türkiye research.
5. **Blocker controller:** bounded retry, safe-stop/rollback, deduplicated issue key, circuit
   breaker and no event notification.
6. **Decision queue/digest:** Friday packet with at most three decisions and three blockers. Each
   decision contains recommendation, alternatives, no-action consequence, deadline, minutes and
   evidence link. It also lists completed work, external deadlines and expiring cost/security
   exceptions.
7. **Urgent router:** only the five urgent conditions in §1 bypass the digest.

No autonomous job waits for a person. Timeouts terminate safely. On circuit break, the lane stays
disabled until a later scheduled health check or an explicit, policy-valid remediation; unrelated
lanes continue.

### Low-risk auto-merge envelope

All exact-head checks, changed-behaviour tests and dependency/security policy must pass. Maximum
change is 10 files and 400 total diff lines, and only allowlisted docs, tests, fixtures,
non-material metadata, generated artifacts, or narrowly scoped regression-tested bug fixes qualify.
The authoring bot cannot modify the approving checks.

Always excluded: `.github/workflows/**`, branch/repository policy, security gates/exceptions,
release/readiness manifests, authn/authz, secrets/deploy credentials, migrations, customer-data
handling, scientific formulas/hazard methodology, pricing/contracts/legal/regulatory claims, and
controlled-pilot/production eligibility. An excluded change creates one consolidated decision
candidate; it is never repeatedly alerted or silently merged.

## 6. Content and agent-native distribution run

Weekly automation harvests approved evidence, optionally creates EN/TR drafts where audience and
source coverage justify both, emits a claim ledger, runs B1 factual provenance, B2 prohibited-claim,
B3 licence/privacy, B4 links/schema, B5 build/test/accessibility, B6 exact-head/security and B7
deployed smoke checks, then safely merges and publishes. It validates sitemap, RSS, `llms.txt`,
canonical URLs, hreflang and structured data.

Unsupported legal conclusions, confidential data, customer/regulator endorsement, readiness
claims and unverifiable figures are skipped rather than sent for routine editorial approval.
Potentially valuable prohibited topics are capped and offered in the Friday digest. A failed B
gate upserts one blocker; three consecutive failures for the same lane/topic family open its
circuit breaker while other content continues.

## 7. Phased implementation plan

Each phase is an independently reviewable PR. “Complete” requires the workflow on the default
branch, exact-head CI, configured permissions and one verified scheduled or controlled run.

| Phase | Deliverable | Acceptance criteria | Current posture |
|---:|---|---|---|
| 1 | Classification, local evidence/reconciliation and digest artifacts | Schema-valid policy; deterministic classifier; exact-SHA evidence; blocker history; read-only reconciliation; capped digest; focused tests | **Implemented locally; default-branch CI and controlled-run evidence pending, therefore not operational** |
| 2 | Scheduled digest, retained evidence, GitHub issue deduplication and native low-risk auto-merge | Privilege-separated trusted workflows, exact-SHA checksummed artifacts, canonical issues, dependency gate and circuit breaker | **Implemented locally; one protected bootstrap merge, settings and controlled digest/merge/circuit runs pending, therefore not operational** |
| 3 | Evidence GitHub/roadmap/Linear sync | SHA ledger and broader remote synchronization; Linear writes remain prohibited in Phase 2 | Not implemented |
| 4 | Extended safe automation | Additional allowlisted maintenance only after Phase 2 operational evidence | Not implemented |
| 5 | Autonomous content publication | B1–B7, bilingual/claims ledger, merge/deploy/metadata smoke and circuit-break test | Not implemented |
| 6 | Data/provenance monitoring | Approved-source health/contracts, licence/source drift and deduplicated blocker evidence | Not implemented |
| 7 | Pilot evidence-pack generation | Reproducible manifest/readiness evaluator that cannot write eligibility | Not implemented |
| 8 | Application/outreach batching | Draft-only packet, external-send prohibition test and weekly bundle | Not implemented |
| 9 | Metrics/automation health | Success/block/retry/circuit/cost/age SLO report in digest; urgent-router test | Not implemented |

## 8. External configuration still required

- Default-branch protection and exact required-check names; GitHub App/bot least-privilege tokens,
  issue/PR permissions, environment rules and auto-merge setting.
- Linear integration identity, project/status mapping and deduplication key field.
- Evidence artifact retention/immutability store and signing identity.
- Production/preview hosting deploy hooks, smoke endpoint, rollback target and incident route.
- Approved cost-anomaly amount/currency/window and external deadline source.
- Content CMS/hosting credentials and canonical domain/Search Console controls.
- AHN, NCG, BAG, Aqueduct and other live-source credentials/endpoints plus licence owners/expiry
  metadata; customer-data processing boundaries remain unset.
- Friday timezone/delivery destination and urgent security/customer channel.
- Application/contact systems may supply drafts, but no automation receives send/sign authority.

## 9. Exact readiness posture

Phases 1–2 can validate and classify policy-bound actions, generate/reconcile evidence, render the
digest, plan deduplicated issues, verify retained artifacts, authorize GitHub native auto-merge and
fail closed through a trusted circuit breaker. Phase 2 changes its own protected control plane and
therefore cannot approve itself: one bootstrap founder decision is required. No autonomous
workflow is claimed operational until default-branch exact-head CI, permissions and controlled
digest, auto-merge and circuit runs produce fresh evidence. This implementation does not alter
scientific, licence, runtime, pilot or production status:

```text
platform_operational = false
data_source_operational = false
model_validated_for_use_case = false
commercially_validated = false
runtime_live_verified = false
controlled_pilot_eligible = false
production_eligible = false
scientific_validation_status = unchanged / not established by this roadmap
licence_verification_status = unchanged / source-specific
```

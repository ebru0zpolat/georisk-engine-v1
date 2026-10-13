# Georisk Engine — Roadmap Status and Micro-task Plan

**Snapshot date:** 2026-09-03  
**Scope:** repository, Linear, deployment, data qualification, scientific claims, and commercial evidence  
**Default posture:** internal self-attested MVP; controlled-pilot and production eligibility remain closed until their separate evidence exists.

## 1. Project-wide decision policy

### 1.1 Internal self-attestation

The same decision applies across the whole project:

- Internal MVP completion may be self-attested by the founder against an exact commit SHA.
- Self-attestation must cite the exact head, reviewed diff, commands, results, known limitations, and claim boundary.
- A second independent reviewer is not a universal prerequisite for internal MVP completion.
- A mergeable PR is not necessarily current: evidence from an old head or old base must not be carried to a new merge result without verification.
- Merge decisions remain founder decisions. This plan does not merge, submit, deploy, provision secrets, or make external representations.

### 1.2 Facts self-attestation cannot create

Self-attestation cannot replace evidence for:

- legal licence rights or licence interpretation;
- live runtime behavior, authenticated smoke, or real-source delivery;
- durable retention, deletion, platform logging, or privacy facts;
- external regulatory, customer, insurer, auditor, or authority approval;
- observed-loss validation, validated EAL/downtime, or scientific performance claims;
- signed customer commitments, revenue, traction, or external submission;
- controlled-pilot or production eligibility.

Until separately proven, preserve:

```text
production_release=none
production_eligible=false
controlled_pilot_eligible=false
runtime_live_verified=false
```

## 2. Current roadmap posture

| Workstream | Current posture | Next decision/evidence |
|---|---|---|
| Dependency compatibility | PR #182 green at `4eb912c`; review/merge decision open | Fresh review, then founder merge decision |
| Frontend deployment | PR #179 open; GEO-212 describes behavior not yet on `main` | Land #179, verify Vercel config, then live smoke |
| Controlled-pilot operations | GEO-62 in progress; 0/9 sources operational | Founder provisions secrets; licence and retention evidence remain external |
| Audit-plane capture | GEO-211 open; four `gee_audit` sources lack a capture path | Implement capture pipeline; credentials alone cannot close it |
| Flood qualification | PR #180 infrastructure merged; real LIWO/AHN qualification open | Vendor real data, seal evidence, qualify; assess v0.4 default separately |
| CMIP6 | PR #174 current with `main`; D1.8 gap remains | Fix citation/retrieval metadata and rerun merge-result checks |
| AHN successor | PR #136 closed unmerged; PR #181 is only a candidate successor | Read #181 against GEO-199 before linking or changing status |
| Self-attested feature PRs | #154/#155/#163 are conflict-free but stale | Reconcile with current `main`; close known A2.5 gap before #163 decision |
| Preview store/logging | GEO-215 and GEO-216 open | Bound store; audit four logging layers and retention |
| Commercial proof | GEO-209 active; GEO-196/GEO-173 stale | Founder decides accelerator posture; rewrite LOI workflow around private evidence |
| SEO | GEO-214 open | Founder decides H1 and FAQPage; add drift guard if shipped |

## 3. Execution order

Do not start a downstream phase until its stated prerequisite is satisfied.

### Phase R0 — Tracker and evidence hygiene

- [ ] **R0.1 — Record this roadmap snapshot**  
  Owner: engineering  
  Output: this file on a documentation branch.  
  Done when: file path and commit SHA are recorded; no eligibility flag changes.

- [ ] **R0.2 — Replace periodic PR #182 polling with an event trigger**  
  Owner: operations  
  Prerequisite: none.  
  Done when: checks run only on new commit/review/merge/close events; unchanged state produces no repeated Linear or PR comments.

- [ ] **R0.3 — Recheck Linear relations**  
  Owner: roadmap  
  Actions: make GEO-216 block GEO-213 closure; relate GEO-215 to GEO-62; keep GEO-211 separate from PR #182.  
  Done when: dependency edges match real prerequisites and no issue is marked Done merely from a comment.

- [ ] **R0.4 — Reconcile milestone wording**  
  Owner: founder  
  Actions: replace universal “independently reviewed” language with “exact-head self-attested internal MVP”; retain explicit external/legal/licence/operational gates.  
  Done when: project milestones and issue descriptions use the same assurance vocabulary.

### Phase R1 — Dependency compatibility: GEO-217 / PR #182

- [ ] **R1.1 — Confirm exact head**  
  Expected: `4eb912c48dabfbc325e844dc390cd4f67929d0bb`. Stop if changed.

- [ ] **R1.2 — Read the complete three-pin diff**  
  Verify: `earthengine-api==1.7.42`, `google-auth==2.55.2`, `google-auth-httplib2==0.4.0`; no unrelated requirements change.

- [ ] **R1.3 — Record installation evidence**  
  Environment: Python 3.12.3.  
  Evidence: clean `pip install -r requirements.txt`; installed versions equal pins.

- [ ] **R1.4 — Record test evidence**  
  Evidence: CI run 388 green and local `1773 passed, 1 deselected`; document the deliberate live-network deselection.

- [ ] **R1.5 — Complete exact-head self-review**  
  Check resolver compatibility, auth imports, dependency audit, and lock/pin consistency.  
  Done when: findings are resolved or explicitly accepted with claim boundaries.

- [ ] **R1.6 — Founder merge decision**  
  Merge only if R1.1–R1.5 remain true. Record merge SHA.  
  Non-effect: does not close GEO-211 and does not change any eligibility flag.

- [ ] **R1.7 — Retire superseded branch metadata**  
  Mark `claude/bump-earth-engine-api-87h5e7` as superseded. Delete or move it only with explicit founder authorization.

### Phase R2 — Frontend deployment and live preview: PR #179 / GEO-212–216

- [ ] **R2.1 — Rebase or merge current `main` into PR #179**
- [ ] **R2.2 — Run exact-head frontend, pytest, verify-eal, dependency-security, and operations checks**
- [ ] **R2.3 — Verify hero claims remain `MODELLED`; never infer `VERIFIED` or `LIVE` from HTTP success**
- [ ] **R2.4 — Founder merge decision for PR #179**
- [ ] **R2.5 — Verify `VITE_API_BASE_URL` in Vercel (GEO-212)**  
  Capture project/environment/host evidence without exposing secrets.
- [ ] **R2.6 — Run the six live hero smoke checks (GEO-213)**  
  Prerequisites: R2.4, R2.5. Store timestamp, deployed SHA, URL, visible result labels, warning, and audit ID.
- [ ] **R2.7 — Bound `_store` lifecycle (GEO-215)**  
  Define capacity, TTL, eviction, concurrency/process behavior, and missing-audit fail-closed semantics before implementation.
- [ ] **R2.8 — Add focused store tests**  
  Cover anonymous repeated preview calls, capacity, expiry, eviction, process/repository miss, and cross-entity isolation.
- [ ] **R2.9 — Audit logging and retention (GEO-216)**  
  Inspect Railway, proxy, uvicorn, and application layers separately. Unobserved layers remain `NOT VERIFIED`.
- [ ] **R2.10 — Close GEO-213 only after retention evidence**  
  A smoke pass alone cannot satisfy the retention checkbox.

### Phase R3 — Controlled-pilot operations: GEO-62 / GEO-211

- [ ] **R3.1 — Founder provisions Railway runtime secrets**  
  User-owned action. Never place secret values in repository, command output, Linear, or evidence files.
- [ ] **R3.2 — Founder provisions GitHub `controlled-pilot` Environment secrets**
- [ ] **R3.3 — Configure required human environment reviewer**
- [ ] **R3.4 — Configure evidence bucket versioning and S3 Object Lock `COMPLIANCE`**
- [ ] **R3.5 — Run source operational evaluator**  
  Record each of nine sources independently; do not aggregate partial success into “operational”.
- [ ] **R3.6 — Collect licence evidence per source**  
  This is a legal fact, not a self-attestation shortcut.
- [ ] **R3.7 — Collect retention evidence per source**
- [ ] **R3.8 — Implement missing `gee_audit` capture plane (GEO-211)**  
  Four sources need a pipeline, not another credential.
- [ ] **R3.9 — Add offline tests for capture routing and fail-closed absence**
- [ ] **R3.10 — Run authenticated deployed smoke**  
  Evidence must bind deployed SHA, auth denial, auth success, release SHA match, golden assertion, and durable retained object.
- [ ] **R3.11 — Evaluate controlled-pilot gate**  
  Leave false unless every required fact is present; do not infer production eligibility.

### Phase R4 — Flood qualification: GEO-210 / PR #180 successor

- [ ] **R4.1 — Select the real LIWO scenario/layer**  
  Record endpoint, layer, scenario, return period, datum, attribution, licence, and retrieval date.
- [ ] **R4.2 — Select matching real AHN-NAP elevation source**
- [ ] **R4.3 — Define pilot asset CSV and coverage expectations**
- [ ] **R4.4 — Run AHN/LIWO extraction without synthetic fallback**  
  Preserve `OUTSIDE_EXTENT`/NoData; never convert absence to zero depth.
- [ ] **R4.5 — Review WMS request URLs and source statuses**
- [ ] **R4.6 — Seal the vendored map and provenance sidecar**
- [ ] **R4.7 — Verify SHA-256, datum equality, cell/return-period uniqueness, and deterministic reload**
- [ ] **R4.8 — Run qualification gate**  
  Require real LIWO plus real AHN-NAP evidence for pilot points. Record `QUALIFIED` or exact fail-closed reason.
- [ ] **R4.9 — Update STUBS #26 only to the proven scope**  
  Infrastructure merged is not the same as real-data qualification.
- [ ] **R4.10 — Founder merge decision for the qualification PR**
- [ ] **R4.11 — Open a separate v0.4-default evaluation PR**  
  Prerequisites: R4.1–R4.10. This task evaluates a default change; it does not presume one.

### Phase R5 — CMIP6 and scientific traceability: GEO-74 / PR #174

- [ ] **R5.1 — Confirm current head `f9458d443004ca1400b13a7199e816ae3369e89a`**
- [ ] **R5.2 — Fix D1.8 citation requirement**  
  A catalogue with `reference=""` must not receive `cmip6_traceable`.
- [ ] **R5.3 — Add retrieval-date field and validation**
- [ ] **R5.4 — Add negative tests for empty citation, missing retrieval date, malformed reference, and metadata-only input**
- [ ] **R5.5 — Rerun D1.2 suite on the new merge result**
- [ ] **R5.6 — Reconfirm D1.3–D1.7 invariants**
- [ ] **R5.7 — Produce exact-head self-attestation record**
- [ ] **R5.8 — Founder merge decision**

### Phase R6 — Self-attested feature decisions: GEO-206/207/208

#### PR #154 / GEO-206

- [ ] **R6.1 — Reconcile 60-commit-old branch with current `main`**
- [ ] **R6.2 — Prove simulation creation cannot change release manifest**
- [ ] **R6.3 — Run fresh exact-head checks**
- [ ] **R6.4 — Founder merge decision**

#### PR #155 / GEO-208

- [ ] **R6.5 — Reconcile 60-commit-old branch with current `main`**
- [ ] **R6.6 — Verify internal merge grants no external submission authority**
- [ ] **R6.7 — Preserve all `NOT_DETERMINED` external states**
- [ ] **R6.8 — Founder internal-merge decision**

#### PR #163 / GEO-207

- [ ] **R6.9 — Reconcile 23-commit-old branch with current `main`**
- [ ] **R6.10 — Reproduce A2.5 duplicate asset-ID collapse through the direct API**
- [ ] **R6.11 — Reject duplicates fail-closed at the canonical boundary**
- [ ] **R6.12 — Add regression tests for direct API and resolver paths**
- [ ] **R6.13 — Reconfirm verification identities remain `init=False` and canonical-decision-only**
- [ ] **R6.14 — Founder merge decision only after A2.5 closes**

### Phase R7 — AHN implementation lineage: GEO-199 / PR #181

- [ ] **R7.1 — Read PR #181 in full against GEO-199 criteria**
- [ ] **R7.2 — Confirm whether #181 is a successor, helper, or unrelated extraction utility**
- [ ] **R7.3 — Verify tests in the repository’s Python 3.12 environment**
- [ ] **R7.4 — Separate extraction mechanics from live evidence**
- [ ] **R7.5 — Link #181 to GEO-199 only if scope matches**
- [ ] **R7.6 — Preserve licence, runtime-live, domain, and production flags as false until proven**

### Phase R8 — Commercial and external actions: GEO-196 / GEO-209 / GEO-173

- [ ] **R8.1 — Founder chooses YES!Delft posture**  
  Choose active application or postponed/reactivation trigger; remove stale deadlines accordingly.
- [ ] **R8.2 — Rewrite GEO-173 for Railway and private evidence room**  
  Never store an unredacted signed LOI in public `docs/legal/`.
- [ ] **R8.3 — Define interview evidence schema**
- [ ] **R8.4 — Keep interview/interest/draft LOI separate from traction**
- [ ] **R8.5 — Record signed commitments and revenue only from primary evidence**
- [ ] **R8.6 — Require explicit founder authorization before any external submission**

### Phase R9 — SEO decision: GEO-214

- [ ] **R9.1 — Founder selects the canonical landing H1**
- [ ] **R9.2 — Founder decides whether FAQPage schema ships**
- [ ] **R9.3 — If shipped, ensure visible FAQ text exactly matches schema**
- [ ] **R9.4 — Add a public-assets drift check**
- [ ] **R9.5 — Verify rendered production output after merge**

## 4. Issue completion template

Use this block when closing an internal self-attested implementation task:

```markdown
### Exact-head self-attestation

- PR:
- Exact head SHA:
- Base/main SHA:
- Reviewed files and scope:
- Commands and results:
- Unresolved review threads: 0
- Known limitations:
- Claim boundary:
- Eligibility flags changed: no
- Founder merge decision:
- Merge SHA (after merge):
```

For live, legal, retention, commercial, or external claims, attach the corresponding primary evidence instead of relying on this template alone.

## 5. Definition of roadmap success

The roadmap is not “production complete” when all code PRs merge. Success is reported by tier:

1. **Internal self-attested MVP:** exact-head code and documentation evidence complete.
2. **Controlled pilot:** live authenticated deployment, operational sources, licence facts, retention, privacy/logging, and human environment gate complete.
3. **Scientifically validated:** real-event/observed-loss protocol and claim-specific evidence complete.
4. **Production eligible:** all technical, legal, operational, security, scientific, and release gates independently satisfied by their required evidence.
5. **Commercially proven:** primary customer/revenue evidence exists; interviews or interest alone are not promoted to traction.


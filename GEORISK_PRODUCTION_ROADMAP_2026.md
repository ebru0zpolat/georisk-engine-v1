# GeoRisk Engine — Production Roadmap 2026

> **Superseded as the active plan (19 September 2026).** Track A execution is
> [`docs/00-master/ROADMAP_VERIFIER_V2.md`](docs/00-master/ROADMAP_VERIFIER_V2.md). The production
> definition in §1 and its readiness gates remain binding and unchanged — every flag stays false.
> Retained as history.

> **Execution model (25 August 2026):** The canonical classification, founder budget, failure
> behaviour and phased automation plan are in
> [`docs/00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md`](docs/00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md).
> Every stage below uses AUTO-PASS, AUTO-BLOCK or FOUNDER-DECISION; older human-review wording
> does not create a routine approval. Readiness values remain evidence-gated and unchanged.

> **Reconciliation (3 September 2026):** Verified against `main` at
> `440955ba30606f50cae89d916a5bf0409c78d746` and Linear team GEO. Three source PRs this plan was
> written around have since closed: **#126 merged** (`836a55a`, 21 Aug), **#132 closed unmerged**
> (30 Aug), **#136 closed unmerged** (1 Sep). GEO-61 is Canceled (successor GEO-210); GEO-199 is
> Backlog with no implementation PR; GEO-105 was redefined and closed as the *self-attested MVP*
> validation tier on 31 Aug, so the real-event/independent-review gate it used to carry is now a
> separate higher-assurance gate and is **not** satisfied by GEO-105 being Done. Superseded lines
> below are struck through with the verified replacement. **Section 8 truth state is unchanged —
> nothing in this reconciliation sets any gate to true.**


**Version:** 1.0

**Roadmap date:** 23 August 2026

**Planning horizon:** 12 weeks

**Primary market:** Dutch/EU commercial property, mortgage and collateral portfolios

**Canonical product posture:** API-first climate-risk decision-support middleware

## 1. Production definition

GeoRisk Engine must not use one undifferentiated **`production_ready`** claim. Readiness is divided into four independently gated states.

| State | Meaning | Initial value |
| --- | --- | --- |
| **`platform_operational`** | Authenticated service can run reliably, persist evidence, recover from failure and be monitored | **`false`** |
| **`data_source_operational`** | Required source connector has verified licence, live runtime evidence, provenance and retention controls | **`false`** |
| **`model_validated_for_use_case`** | Named hazard/loss method has passed a preregistered real-event validation for a defined use case | **`false`** |
| **`commercially_validated`** | Qualified buyer evidence and at least one executed pilot/SOW exist | **`false`** |

**`production_eligible=true`** is permitted only for a named product release, geography, hazard, use case and model version when every applicable gate below passes. A green CI run, merged pull request, live data call, interview, LOI or demo cannot independently set it to true.

## 2. Product boundary for the first production candidate

### Included

- Dutch commercial-property and collateral portfolio screening.
- Asset-coordinate ingestion and bounded portfolio processing.
- AHN elevation/topographic context.
- ~~Aqueduct water-stress context after its pack is reconciled and merged.~~ Superseded by ADR-0007: the NL water-stress indicator is Klimaateffectatlas, not Aqueduct.
- Flood and extreme-heat decision-support only where the relevant source and model gates pass.
- Versioned source manifests, hashes, limitations and audit identifiers.
- Human-readable and machine-readable evidence export.
- Analyst workflow for prioritising deeper assessment.

### Excluded until separately validated

- Automated credit, underwriting, valuation, regulatory-capital or investment decisions.
- Engineering-grade flood survey or inundation certification.
- Validated EAL, downtime or monetary-loss claims.
- Activity-specific EU Taxonomy alignment conclusions.
- ESRS E1-9 financial effects without verified scenario and financial data.
- Regulatory-compliance certification.
- P2P energy trading or blockchain-market functionality.

## 3. Current Linear findings

### Confirmed completed foundation

| Linear | Verified posture | Roadmap treatment |
| --- | --- | --- |
| GEO-60 | Done; PR #126 blockers resolved | Closed foundation |
| GEO-73 | Done; PR #126 merged as **`836a55a`** | Closed decision-support contract |

### Active work that belongs on the production critical path

| Linear | Current finding | Required decision |
| --- | --- | --- |
| GEO-61 | **Canceled 2026-09-01.** Aqueduct NL pack, PR #132 closed unmerged 2026-08-30; superseded by ADR-0007 | ~~Reconcile `main` with ADR-0007 and open the Klimaateffectatlas workstream~~ **Done:** ADR-0007 reconciliation landed on `main` in `d40bb33`; successor issue **GEO-210** is open and In Progress. Branch `feat/geo-61-aqueduct-nl-vector-pack` (`ca017e2`) retained for a possible non-NL portfolio only |
| GEO-210 | Klimaateffectatlas NL indicators, ADR-0007 successor to GEO-61. Ingestion infrastructure merged (PR #180, `440955b`); indicator qualification not started | Deliver at least one indicator end to end — provenance, licence self-attestation, sealed snapshot, coverage gate, NoData handling, semantic validation. No eligibility flag changes |
| GEO-199 | AHN pilot foundation. **PR #136 closed unmerged 2026-09-01; nothing from it is on `main`.** Issue moved to Backlog 2026-09-02. Branch `feat/nl-pilot-contract` (`8f7dd59`) retained | ~~Obtain independent reviews; merge foundation~~ **Re-triage first:** the issue currently tracks no implementation PR. Decide whether PR #181 (AHN4 + LIWO extractor, open) is the successor before re-opening. `runtime_live_verified`, `licence_verified`, `semantic_observation_verified` and `production_eligible` all stay false; closing #136 changed no flag |
| GEO-197 | Regulatory evidence registry, PR #133; draft and behind **`main`** | Correct stale head label, reconcile, retain evidence-readiness-only scope |
| GEO-198 | NACE input and metadata sources depend on GEO-197/PR #133 | Sequence after registry; do not merge independently |
| GEO-201 | Blocked-evidence fail-closed fix touches code changed by merged PR #126 | Reassess diff against current **`main`**; close if superseded or land only remaining defect |
| GEO-62 | Railway secrets, authenticated smoke and evidence retention | Promote to P0 platform-operational gate |
| GEO-50 / GEO-47 / GEO-48 / GEO-19 | Immutable audit and actor/state-transition records | Consolidate into one production audit epic |
| GEO-72 | PostgreSQL migration from in-memory storage | P0 before multi-user or durable pilot operation |
| GEO-105 | **Redefined and closed Done 2026-08-31** as the *self-attested MVP* validation tier (PRs #169 `465e38c`, #170 `d1ab04b`). It is **not** the real-event backtest gate any more | Keep "validated — self-attested MVP tier" visibly distinct from "independently validated". The real-event gate below (Stage 5) is now a **separate, unowned higher-assurance gate** with no Linear issue — open one before any backtest work starts |
| GEO-111 | Accuracy audit layer | Implement only after the Stage 5 real-event protocol and data are fixed — **not** on the strength of GEO-105 being Done |
| GEO-173 / GEO-177 | Data-source agreement and source registry are mixed | Separate legal supply assurance from technical catalog work |
| GEO-183 / GEO-196 | Facilitator, customer validation and YES!Delft evidence sprint | Run in parallel; not a substitute for technical/model readiness |

### Backlog quality findings

1. Several old P0/P1 issues describe a previous anomaly/case-management product rather than the current Dutch collateral-screening wedge.
2. Priority labels are inflated: scientific validation, frontend SEO, database durability and customer discovery all appear as simultaneous P0/P1 work.
3. Dependencies are mostly **`relatedTo`** links rather than blocking relationships; this permits work to start in the wrong order.
4. ~~GEO-199 reports historical test counts and states~~ **Addressed 2026-09-02:** GEO-199 now labels its test totals as historical evidence from a closed PR. The underlying advice stands: link exact-head evidence rather than embedding mutable totals.
5. ~~GEO-61 still contains a stale statement that PR #126 is unmerged.~~ **Addressed 2026-08-21:** GEO-61 carries a reconciliation note recording `836a55a`. The PR #132 body still carries the stale "#126 remains unmerged" line, but #132 is closed and will not be touched again.
6. GEO-197 documents a stale audit-trail head label.
7. GEO-200 taxonomy/SEO work is not on the production critical path and should not precede a working authenticated pilot demo.
8. GEO-202/GEO-203 show excessive open-PR inventory. Repository reconciliation must occur before further stacked feature work.
9. **51 pull requests are open** as of 2026-09-03, against a Stage 0 exit criterion of no more than five production-critical PRs. This is the largest single gap between this plan and the repository, and it is the finding in item 8 quantified.

## 4. Twelve-week execution roadmap

### Stage 0 — Backlog and branch control (Week 1)

**Outcome:** One reliable **`main`**, explicit ownership and a credible critical path.

- ~~Reconcile PR #132 with current **`main`**; preserve all GEO-61 invariants.~~ **Obsolete:** #132 closed unmerged 2026-08-30; GEO-61 Canceled. Its verified invariants are recorded on the retained branch and must not be reinstated for NL assets (ADR-0007).
- Reassess PR #128/GEO-201 against merged PR #126 and close it if fully superseded.
- Decide the sequence for PRs #133 and #134; registry must precede metadata input.
- Review PR #135/GEO-200 and defer taxonomy work not required by the pilot demo.
- Resolve stale and stacked PRs under GEO-202 and GEO-203.
- Add actual **`blockedBy`** relationships in Linear.
- Freeze unrelated feature development until the active-PR count is reduced.

**Exit criteria**

- No production-critical PR is based on an obsolete **`main`**.
- Every active P0/P1 issue has an owner, acceptance criteria and evidence link.
- No two issues track materially different work under the same identifier.
- Critical active PR count is no more than five.

### Stage 1 — Dutch source foundation (Weeks 1–2)

**Outcome:** Mergeable source contracts with truthful evidence states.

- Complete AHN licence review and geospatial/domain review for GEO-199. **These remain human gates and no automated step may set them** — `licence_review.py` / `domain_review.py` default every human-decision field to undetermined.
- Validate reviews against exact reviewed SHA without fabricating approval.
- ~~Merge PR #136 only after exact-head CI and both human reviews pass.~~ **Obsolete:** #136 closed unmerged 2026-09-01. Any successor must re-establish exact-head CI and both human reviews on its own head; #136's evidence does not transfer.
- Rerun bounded AHN verification from the clean merge commit.
- Preserve a durable evidence record bound to source commit, endpoint, coverage ID, request bounds and response hashes.
- Do not merge the Aqueduct pack: ADR-0007 rejects the indicator for NL assets.

**Exit criteria**

- **`licence_verified=true`** only for the reviewed source/version and permitted uses.
- Live transport evidence is dated, bounded and reproducible.
- Fixture and live evidence remain distinguishable.
- **`production_eligible=false`** remains unchanged.

### Stage 2 — Working pilot demo (Weeks 2–4)

**Outcome:** A buyer can submit a Dutch asset and receive a traceable, usable demonstration response.

- Create WP-NL02D as a fresh branch from updated **`main`**.
- Implement authenticated **`POST /api/v1/nl-pilot/elevation-observation`**.
- Add deterministic fixture mode and explicit opt-in live mode with no automatic fallback.
- Add the Netherlands pilot UI with input validation, status badges, source manifest, limitation panel and downloadable JSON evidence.
- Add a 50–200 asset bounded batch demonstration path.
- Use persistent audit identifiers; do not expose raw provider bodies or secrets.
- Show AHN as topographic context, never as flood probability or loss.

**Exit criteria**

- Demonstration succeeds deterministically without external credentials.
- Authenticated live smoke succeeds in the approved environment when explicitly invoked.
- API/UI contract and accessibility tests pass.
- Every response exposes evidence state, source, limitations and **`production_eligible=false`**.

### Stage 3 — Platform operational baseline (Weeks 3–6)

**Outcome:** The demo becomes a controlled pilot service rather than a developer-only application.

- Complete GEO-62: secrets management, authenticated smoke and durable evidence retention.
- Replace in-memory production state with PostgreSQL under GEO-72.
- Consolidate GEO-19/GEO-47/GEO-48/GEO-50 into an immutable audit-state epic.
- Add scoped API keys or organisation/workspace authentication.
- Add rate limits, request-size limits, batch limits and idempotency keys.
- Add structured logs without personal data or secrets.
- Add health/readiness checks, error monitoring, alert ownership and backup/restore test.
- Define incident response, rollback and evidence-retention runbooks.
- Perform dependency, container and application security checks.

**Exit criteria**

- **`platform_operational=true`** for a named staging/pilot release.
- Restore drill and rollback test pass.
- Authenticated exact-release smoke evidence is retained.
- No critical/high unresolved security finding.
- This gate does not change **`model_validated_for_use_case`**.

### Stage 4 — Hazard semantics and model separation (Weeks 5–8)

**Outcome:** Observed inputs, hazard indicators, scenarios and losses are technically and semantically distinct.

- Add raster semantic extraction only with reproducible rasterio/GDAL compatibility.
- Validate raster CRS, bounds, resolution, nodata, finite statistics and decompressed-size limits.
- Keep **`elevation_observation_verified`**, **`flood_hazard_verified`** and **`flood_loss_verified`** separate.
- Reconcile the regulatory registry under GEO-197 and sequence GEO-198 afterward.
- Implement versioned methodology identifiers and change-impact rules.
- Prevent blocked or incomplete evidence from reaching conclusions, resolving GEO-201.
- Add automated claim-control tests for API, reports and frontend wording.

**Exit criteria**

- Every result identifies observation, scenario, proxy and model status independently.
- No elevation-only flood conclusion is possible through public contracts.
- Regulatory mappings are evidence pointers, not compliance determinations.
- Formula or source changes invalidate affected evidence deterministically.

### Stage 5 — Real-event scientific validation (Weeks 6–11)

**Outcome:** One narrow flood or heat use case has defensible empirical evidence—or remains explicitly unvalidated.

- ~~Keep GEO-105 blocked until all prerequisites exist.~~ **Re-pointed:** GEO-105 is Done as the self-attested MVP tier. This stage now needs its **own** issue, and it stays blocked until a named event, licensed observed-loss data, a preregistered sample and exclusion rules, a fixed comparison cutoff and an independent reviewer all exist.
- Name one event and freeze the valuation/data cutoff.
- Secure a licensed observed-loss dataset.
- Preregister assets, sample, exclusions, metrics and naive/incumbent baseline.
- Appoint an independent reviewer before results are observed.
- Run prediction and baseline under the same cutoff.
- Report uncertainty, missingness, representativeness and negative results.
- Implement GEO-111 immutable accuracy log only after the protocol is frozen.

**Exit criteria**

- **`model_validated_for_use_case=true`** only for the exact event/hazard/geography/model version supported by the review.
- No general EAL, downtime or monetary validation claim is inferred.
- Failure to obtain observed-loss evidence leaves the gate false and does not block the safe demonstration product.

### Stage 6 — Commercial and IND evidence (Weeks 1–12, parallel)

**Outcome:** Demonstrated Dutch economic relevance and credible market entry without claim inflation.

- Execute GEO-196 deadlines: 8–12 qualified interviews, including Dutch regulated buyers and operational/model owners.
- Complete the YES!Delft scout inquiry by 25 August and preserve the response.
- Prepare one standard and one prospect-specific 4–6 week paid pilot proposal.
- Obtain two written pilot-scoping confirmations.
- Seek one executed paid diagnostic/SOW; otherwise retain any LOI as non-binding.
- Progress GEO-183 facilitator evidence separately from customer evidence.
- Clarify Dutch incorporation/KVK timing, founder commitment, IP/FTO and runway evidence.
- Build an evidence-indexed IND/accelerator claim register.

**Exit criteria**

- **`commercially_validated=true`** requires at least one executed pilot/SOW; interviews and LOIs alone do not satisfy it.
- Application claims are linked to dated, attributable and retrievable evidence.
- Dutch contribution is expressed through jobs, local supplier/data ecosystem, climate-adaptation decision support and exportable technical capability—not unsupported revenue forecasts.

### Stage 7 — Pilot release decision (Week 12)

**Outcome:** A documented go/no-go decision for a named pilot release.

Required release record:

- release/version and commit SHA;
- geography, hazard, asset class and permitted user decision;
- source and model versions;
- platform, source, model and commercial gate states;
- security and operational evidence;
- human approvals and expiration dates;
- limitations and prohibited uses;
- rollback owner and incident contact.

Possible decisions:

| Decision | Minimum posture |
| --- | --- |
| **`demo_only`** | Deterministic fixture demo, limitations and evidence IDs |
| **`controlled_pilot`** | Platform operational + approved source use + authenticated smoke; model may remain unvalidated if outputs are explicitly observational/proxy-only |
| **`validated_decision_support`** | Controlled pilot plus real-event validation for the exact named use case |
| **`production_eligible`** | All applicable release gates, independent approvals and operational controls pass |

## 5. Linear restructuring recommendation

### Retain and update

- ~~GEO-61 — Aqueduct NL pack~~ **Done:** Canceled 2026-09-01, successor GEO-210 open.
- GEO-199 — AHN foundation: re-triage against PR #181 before re-opening; keep the four false gates and the claim boundary intact.
- GEO-197 — registry: correct the audit-trail head label and explicitly block GEO-198.
- ~~GEO-105 — retain as scientific-validation gate~~ **Superseded:** GEO-105 now closes the self-attested MVP tier only. Open a new issue for the real-event validation gate; do not start implementation under GEO-105.
- GEO-196 — retain as the commercial/YES!Delft critical path.
- GEO-62 — promote to P0 for the controlled-pilot release.

### Consolidate

- GEO-19, GEO-47, GEO-48 and GEO-50 into one immutable production-audit epic.
- GEO-173 and GEO-177 into separate legal-agreement and technical-source-catalog tracks with a clear relationship.
- Old UI integration issues under GEO-16/17/18 should be re-triaged against the Netherlands pilot UI; close obsolete items rather than inheriting them automatically.

### Defer

- GEO-200 taxonomy/SEO until the authenticated Netherlands demo is functional.
- GEO-191 ORAS5 production work unless required by the selected validated use case.
- Graph, transition-risk/CBAM and P2P-energy expansion until the first wedge reaches controlled-pilot status.

### New issues required

1. **[P0] Controlled pilot release gate and release manifest**
2. **[P0] WP-NL02D authenticated Netherlands evidence demo**
3. **[P0] Production persistence, backup and restore drill**
4. **[P0] API authentication, scopes, rate limits and idempotency**
5. **[P0] Observability, incident response and rollback evidence**
6. **[P1] Claim-control tests across API, reports and frontend**
7. **[P1] Independent AHN licence and domain review completion**

## 6. Weekly production scorecard

| Metric | Target by Week 12 |
| --- | --- |
| Open production-critical PRs | ≤ 3 |
| Exact-head CI | 100% passing for release candidate |
| Critical/high security findings | 0 unresolved |
| Authenticated pilot smoke | Passed and evidence-retained |
| Backup/restore drill | Passed |
| Source licences reviewed | 100% of enabled live sources |
| Automatic live-to-fixture fallbacks | 0 |
| Unsupported public claims | 0 |
| Qualified buyer interviews | 8–12 |
| Dutch organisations interviewed | ≥ 5 |
| Written pilot-scoping confirmations | ≥ 2 |
| Executed pilot/SOW | ≥ 1 target |
| Independently reviewed real-event validations | 1 narrow use case target |

## 7. Immediate next seven actions

1. Send the YES!Delft scout inquiry and preserve the dated response under GEO-196.
2. ~~Reconcile PR #132 with current **`main`** and rerun exact-head CI.~~ **Obsolete** (#132 closed). Replaced by: reduce the 51 open PRs toward the Stage 0 target under GEO-202.
3. ~~Obtain independent AHN licence and geospatial-domain reviews for PR #136.~~ **Re-scoped** (#136 closed): re-triage GEO-199 against PR #181 and decide whether it is the successor.
4. Reassess GEO-201/PR #128 against merged PR #126.
5. Make GEO-62 a P0 blocker for the controlled pilot.
6. Create the WP-NL02D demo issue. ~~Start implementation only from updated **`main`** after PR #136 merges.~~ **#136 will not merge** — branch from current `main` instead, and treat the AHN foundation as unlanded.
7. Build the first 15-account Dutch outreach list and schedule the first five qualified interviews.

## 8. Preserved truth state

```text
platform_operational = false
data_source_operational = false
model_validated_for_use_case = false
commercially_validated = false
runtime_live_verified = false
production_eligible = false
```

These values change only through dated release evidence and explicit gate evaluation. Roadmap progress alone never changes them.

## 9. Stage execution classification and founder budget

The operating roadmap §3 is the authoritative reconciliation of every stage. In summary, routine
backlog cleanup, exact-head checks, fixtures, evidence exports, monitoring and permitted deploys are
**AUTO-PASS**; a stale branch, missing credential/licence/evidence, failed check/smoke or unavailable
service is **AUTO-BLOCK** and does not stop other stages. Only protected control-plane changes,
real/customer data, privileged production access, major migrations, scientific-method changes,
external commitments and a change to release eligibility are **FOUNDER-DECISION**.

The 12 weekly budgets in the operating roadmap §4 replace ad-hoc review. Each week stays at no more
than three non-urgent decisions and 60 repository minutes. Stage 6 interview, negotiation and
application attendance is separately scheduled founder work; preparation remains AUTO-PASS and all
external sending/signing remains FOUNDER-DECISION. Stage 7 automation evaluates but cannot write an
eligibility state. Missing founder input defers the decision without weakening any gate.

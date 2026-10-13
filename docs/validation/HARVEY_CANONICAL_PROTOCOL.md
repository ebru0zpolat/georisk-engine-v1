# Harvey 2017 — Canonical protocol, decision matrix, and supersession

**Study ID:** `harvey-2017-nfip-flood-reconstruction-v0.1`
**Status:** **NOT FROZEN** — this document consolidates three competing
preregistration branches. Harvey remains **unvalidated and unfrozen** until the
consolidation below is exact-head verified, P1-03…P1-07 hardening is complete,
the independent challenge is resolved, and a founder-decision freeze commit
binds the complete scientific payload. No outcome value has been accessed.

This document is the single canonical contract. It supersedes the competing
preregistration paths on PRs #116, #187 and #191 and records, clause by clause,
where each decision came from, whether it is KEEP, MERGE, REPLACE or DROP, and
the rationale for every genuinely conflicting scientific parameter.

## 1. Source arms

| Arm | PR | Registration | Authority that survives |
|---|---|---|---|
| Reconstruction protocol | #116 | `data/validation/studies/harvey_2017_nfip/preregistration.json` + `HARVEY_2017_NFIP_STUDY_PROTOCOL.md` | Material clauses transcribed below; branch closed after verification |
| Freeze + verification split | #187 | `pre_registration.harvey_2017.json` + `HARVEY_2017_FLOOD_LOSS_PREREGISTRATION.md` + `flood-hazard-loss-verification-split.md` | Material clauses transcribed below; branch closed after verification |
| Surviving vehicle | #191 | `docs/validation/HARVEY_GATE1_PREREGISTRATION.json`, `config/harvey_baseline_calibration_spec.json`, `app/validation/harvey/preparation.py`, freeze script | Canonical implementation vehicle; values reconciled here, not silently inherited |

**Vehicle authority.** #191 is the surviving implementation branch. Being the
surviving branch does **not** make every #191 numeric value scientifically
canonical. Each conflicting parameter below was classified compatible/additive
versus mutually exclusive, then chosen once with a recorded rationale.

## 2. Clause matrix

Legend: **KEEP** = already correct in the canonical contract; **MERGE** = carry
the clause in as additive; **REPLACE** = the surviving vehicle's value is
replaced by the resolved value; **DROP** = superseded/not adopted.

### A. Framing and identity

| Clause | #116 | #187 | #191 | Decision |
|---|---|---|---|---|
| Study framing | `analysis_mode: event_reconstruction`; ex-post reconstruction, never prospective | ex-post reconstruction, never prospective backtest | event-conditional estimand (flood, not EAL) | **KEEP** — canonically *event reconstruction*: this study challenges the frozen synthetic Phase A flood pathway vs a naive baseline within eligible NFIP Harvey claims; it cannot establish calibration, EAL, Dutch transferability, uninsured loss or prospective skill |
| Study ID | `harvey-2017-nfip-flood-reconstruction-v0.1` | `harvey-2017-flood-loss-v1` | none explicit (estimand-keyed) | **REPLACE** → one canonical ID `harvey-2017-nfip-flood-reconstruction-v0.1`. One ID, one registration (P1-08). #187's ID is superseded. Machine binding deferred to P1-06 |
| Primary metric | rmse_loss_ratio (primary) | MAE, 10% relative improvement | MAE, 10% relative improvement | **MERGE** — MAE in nominal USD is the canonical primary metric (model MAE ≤ baseline MAE × (1 − 0.10)); the #116 RMSE-skill and mean-bias gates are adopted **as acceptance gates**, not the primary metric |
| Event window | 2017-08-25 … 2017-09-01 | 2017-08-25 … 2017-09-04 | not explicit | **REPLACE** → window **2017-08-25 … 2017-09-01 inclusive**. Rationale in §3 (mutually exclusive: 09-01 vs 09-04 resolved) |
| Geography | state = TX (frame) | Harris County, FIPS 48201 | calibration geography `["TX"]`; dict "Harris County eligibility rules to be finalized" | **MERGE** — **Harris County (FIPS 48201) evaluation frame** (#187, matches #191 dict draft); TX-wide retained as the **pre-event baseline calibration geography** (#116+#191). Flagged for founder review (§3) |

### B. Sample, exclusions, outcome handling

| Clause | #116 | #187 | #191 | Decision |
|---|---|---|---|---|
| Unit and population | one de-identified NFIP claim; census-tract clusters | census of eligible records, not a sample; target n is the rule output, never estimated pre-outcome | claim-conditional estimand; coverage qualification | **MERGE** — unit = one de-identified NFIP building claim record; analysis is a **census of eligible event-window records**, no random subsample; no address-level matching (privacy-truncated coordinates) |
| Eligibility / exclusion decides-outcome | all eligibility and exclusion decisions emitted **before** evaluation outcomes unlock; `prohibited_before_evaluation_unlock` list | ordered inclusion→exclusion applied without inspecting loss distributions; filter counts mandatory; >20% one-step exclusion flags review but authorises no rule change | outcome-blind coverage gate rejects outcome columns | **MERGE** — eligibility/exclusion precede and are independent of any outcome access; the outcome-blind field boundary and the exclusion-before-unlock ordering are canonical; filter counts are reportable |
| `N ≥ 200` / `≥ 30` clusters | evaluation_n ≥ 200 and cluster_n ≥ 30 | — | sample_size ≥ 200, location_clusters ≥ 30 (code-enforced) | **MERGE** — additive and already in the surviving vehicle: ≥200 eligible claims **and** ≥30 independent location clusters both required |
| Deterministic assignment / split | sha256_cluster_holdout on `censusTract`, 70/30, public salt, staged outcome access phases 1–3, EvaluationUnlock record (6 hashes) | no split — census; deterministic order/hash of stable identifiers | cluster assignment for coverage; bootstrap by cluster | **MERGE with one REPLACE** — the **random 70/30 cluster holdout is DROPped for the primary** (against #187's census frame). Retained: deterministic SHA-256 cluster assignment, staged outcome access, and the EvaluationUnlock record requirement. §3 |
| Duplicate handling | `duplicate_claim_id` excluded and counted; no silent duplicates | exact duplicates retain one; conflicting duplicates make the study ineligible | not yet enforced in code | **MERGE** — deterministic deduplication: exact duplicates retain one row, conflicting duplicates → ineligible, counts reported. Gap: not yet code-enforced on the surviving vehicle (P1-03…P1-07 phase) |
| No-imputation / no-winsorisation | do not impute missing water depth; do not cap or winsorise claim-payment-over-limit | no imputation in primary analysis; no trimming/winsorisation/cap/outlier removal | `outlier_policy: retain_all_eligible_records`; no trimming in calibration | **MERGE** — no imputation and no winsorisation for the primary analysis are canonical; already partly encoded (`retain_all_eligible_records`); explicit wording added here |
| Zero payments | zero payments remain included | §4: no zero-payment row excluded merely for being zero | `include_zero_payments: true` | **KEEP** — zero payments are part of the frame |
| Post-outcome subgrouping | failure never hidden by subgroup selection; `benchmark_not_supported` | exactly one primary run; negative results retained | verdict fail-closed | **KEEP** — one primary run; any gate failure → `benchmark_not_supported`; post-hoc selection prohibited |

### C. Data sources and hazard

| Clause | #116 | #187 | #191 | Decision |
|---|---|---|---|---|
| Observed loss endpoint | FimaNfipClaims **v2** API (planned) | FIMA NFIP Redacted Claims v2 | NfipClaims **v3** with explicit schema adapter, raw SHA-256, terms archive, licence manifest | **REPLACE** → **FEMA OpenFEMA `NfipClaims` v3** is the canonical source; v2 (`FimaNfipClaims`) is retired/prohibited. Relies on #191's acquisition manifest (query, timestamp, raw SHA-256, terms snapshot). See #116/#187 v2 supersession |
| Outcome field | `amountPaidOnBuildingClaim` | `amountPaidOnBuildingClaim` (nominal USD) | `amountPaidOnBuildingClaim` → canonical `buildingClaimPaymentAmount`; substitutes prohibited | **KEEP** — insurance-limited **building** claim payment via the one approved adapter field; `netBuildingPaymentAmount` / `buildingDamageAmount` are never substitutes |
| Exposure basis | `insurance_limit` | `amountOfBuildingInsuranceCoverage` value proxy | `totalBuildingInsuranceCoverage` | **KEEP** — outcome framed as an insurance-limit payment ratio, not replacement-cost damage; deductibles/limits/adjustment affect the outcome |
| Hazard source hierarchy | USGS contextual | ordered first-authoritative: USGS → FEMA → openly licensed peer governmental derivative; ≥95% coverage; byte-for-byte archive; stop if none qualifies | USGS CO/C0 depth; ≥95% coverage (code-enforced) | **MERGE** — hazard-source qualification is the ordered hierarchy, outcome-blind, ≥95% coverage, archived byte-for-byte, decided **before** outcomes are viewed; no substitute selected after viewing losses |

### D. Baseline and cutoff

| Clause | #116 | #187 | #191 | Decision |
|---|---|---|---|---|
| Information / outcome-leakage & baseline cutoff | calibration-only pre-event; event window after | 2017-08-24 (landfall −1); sample-leakage boundary | 2017-08-24 (registration and calibration code-enforced) | **KEEP** — **2017-08-24**, the pre-event outcome-leakage and historical-baseline cutoff. See §3.1 for its exact semantics; it is **not** a general "predictor cutoff" and does not restrict the preregistered retrospective hazard input |
| Code/product version boundary | — | 2026-09-03, recorded in the post-freeze execution manifest, never in `information_cutoff` | — | **MERGE** — the code/product version boundary is a separate manifest field, distinct from the information cutoff |
| Baseline identity | calibration-only mean payment ratio within frozen depth bins, empty-bin fallback to calibration-wide mean | `value_fraction`, fraction unfilled (blocked: uncited 0.02 placeholder) | `historical_coverage_ratio` = Σ payments / Σ coverage over pre-event claims, with source hash | **REPLACE** — canonical baseline is **`historical_coverage_ratio`** (pre-event, data-derived, hashed, `excluded_event = Hurricane Harvey`, claims before 2017-01-01). #187's uncited `value_fraction` is superseded; its **honesty rule survives** (no arbitrary comparator: freeze refuses {} placeholder/uncited params). #116's depth-bin mean becomes calibration-only **stratified diagnostics** with frozen bins |
| Calibration-only rule | baseline frozen before evaluation payments; calibration cluster-only outcomes | baseline fitted before outcomes joined | baseline calibrated on hashed pre-event sample | **KEEP** — baseline is calibration-only (pre-event), frozen before any evaluation outcome access |

### E. Bootstrap and uncertainty

| Clause | #116 | #187 | #191 | Decision |
|---|---|---|---|---|
| Repetitions | 2,000 | 10,000 | 10,000 | **REPLACE→10,000** (mutually exclusive: 2,000 vs 10,000, §3) |
| Seed | 20170825 | 20170825 | 1729 | **REPLACE→20170825** (§3) |
| Uncertainty method | census-tract cluster percentile bootstrap, 95% CI | record-level paired CI + sensitivity cluster bootstrap by coordinate pair | per-cluster bootstrap 95% CI in calibration diagnostics; location-cluster CI in dict | **MERGE** — 95% percentile bootstrap; record-level CI primary, location-cluster bootstrap sensitivity secondary |

### F. Success rule and gates

| Clause | #116 | #187 | #191 | Decision |
|---|---|---|---|---|
| Success rule | — (gates) | MAE relative improvement ≥ 10% | MAE relative improvement ≥ 10%, `min_fraction 0.10` | **KEEP** — primary rule unchanged |
| Acceptance gates | RMSE-skill lower 95% CI > 0; absolute mean bias ≤ 0.05; n ≥ 200; clusters ≥ 30 | — (MAE only, secondary diagnostics) | dict "Frozen decision rule": n ≥ 200; clusters ≥ 30; skill ≥ 0.10; lower 10,000-repeat cluster-bootstrap 95% CI > 0; normalized \|mean bias\| ≤ 0.05 | **MERGE** — **all five gates coexist**: n ≥ 200; clusters ≥ 30; skill ≥ 0.10; RMSE-skill lower 95% CI > 0; absolute mean bias ≤ 0.05. Any failure → `benchmark_not_supported` |

### G. Governance, review, freeze, claims

| Clause | #116 | #187 | #191 | Decision |
|---|---|---|---|---|
| Independent challenge/review | independent_challenge_status: pending; reviewer challenges selection, licence, filters, alignment, metric, uncertainty, claims | independent reviewer attests `config_hash`; self-attestation tiered and named | gate verdict requires attestation bound to `report_config_hash`, tier min self_attested | **KEEP** — independent reviewer requirement is canonical; attestation bound to the study's `config_hash`; the Harvey challenge remains pending until the consolidated study is frozen |
| Founder-controlled freeze / real freeze act | freeze before claim-level outcome access; registration_status frozen_before_claim_level_outcome_access | freeze is a real act: separate, subsequent commit on a clean tree; resolver-verified `git cat-file -t`; refusal of frozen/unparseable/null-param/dirty tree; hand-edited freeze rejected as unauditable | `freeze_pre_registration` + `verify_git_freeze` refuse already-frozen, missing params, non-resolving commit; `require_frozen` verifies digest | **KEEP** — a freeze is a **founder decision**, performed by the freeze script as a separate subsequent commit whose hash resolves; a fabricated or hand-edited freeze (e.g. `9a18...`) is rejected as unauditable |
| Full-payload freeze binding | protocol/cohort/model/baseline/calibration-receipt hashes in EvaluationUnlock | favours real-act freeze; open-items block | binds the `PreRegistration` scientific payload | **DEFER to P1-06** — current binding covers the machine pre-registration; event window, evaluation frame, gates, bootstrap seed and the source manifest are **not yet hash-bound**. P1-06 inventories and binds every scientific decision |
| Verification split: hazard vs loss | — | `flood_hazard_verified` and `flood_loss_verified` independent, fail-closed; delivered via Linear follow-on | claim registry binds only `harvey_event_loss_method_validated` / `us_harvey_flood_hazard_verified` | **MERGE conceptually** — hazard and loss verification are separately gated, neither implies the other, both default false and fail closed; delivery tracked as a follow-on (the split is currently a proposal, no code exists) |
| Claim boundary | external-validity statement; cannot validate Dutch CRE/EAL/uninsured | RVO hierarchy: NL relevance → Limburg → Harvey methodology → Dutch loss later | registry of allowed vs prohibited claims (INV-11) | **KEEP** — claims are bounded: Harvey may support only `harvey_event_loss_method_validated` and `us_harvey_flood_hazard_verified`; never Dutch CRE transferability, NL hazard, EAL or `model_validated_for_nl_cre_use_case` |

## 3. Genuinely conflicting scientific parameters — resolved with rationale

The following are mutually exclusive, not additive. Each is chosen once and the
rationale recorded here. **Flagged for founder review before freeze.**

| # | Parameter | Candidates | Resolution | Rationale |
|---|---|---|---|---|
| 1 | Bootstrap repetitions | 2,000 (#116) vs 10,000 (#187, #191) | **10,000** | Two of three arms agree; a 10,000-repeat CI is materially more stable for the two bootstrap-based gates (RMSE-skill lower bound, mean-bias CI) and matches #191's code-enforced minimum (`bootstrap_repetitions < 10_000` refused). 2,000 (#116) is superseded |
| 2 | Bootstrap seed | 20170825 (#116, #187) vs 1729 (#191) | **20170825** | Two of three arms agree **and** the value is event-anchored (Harvey landfall date), giving a deterministic, reproducible, auditably non-arbitrary RNG state. #191's `1729` is a fixed illustrative constant with no event or study anchor; it is replaced (explicit deviation from the surviving branch's default) |
| 3 | Information cutoff | calibration-only (#116) vs 2017-08-24 (#187, #191) | **2017-08-24** | Conflating "sample leakage boundary" with the code/product version boundary was #187's core catch: a cutoff after the event makes the `LookaheadError` guard vacuous. 2017-08-24 = day before Harvey's first Texas landfall, the defensible pre-event boundary, and it is already enforced in the surviving calibration spec and code. Its exact meaning is pinned in §3.1 (founder clarification) |
| 4 | Evaluation design / split | random 70/30 census-tract cluster holdout (#116) vs full census of eligible records (#187) | **Census evaluation frame** with staged, hash-bound outcome unlock (#116's staging retained) | #187 argues and #191's own data dictionary concur that the eligible event-window frame **is** the population; a random holdout would throw away eligible claims for no sampling purpose. The ≥30-cluster qualification and the cluster bootstrap still bound spatial dependence. The 70/30 holdout is not adopted for the primary run |
| 5 | Event window | 2017-08-25 … 09-01 (#116) vs … 09-04 (#187) | **2017-08-25 … 2017-09-01** | The Texas flooding period attributable to Harvey is conventionally bounded through 1 September (landfall 8/25; the system re-emerged into the Gulf and crossed into Louisiana 8/30, so 9/2–9/4 conflates the Louisiana phase). 09-04 is superseded |
| 6 | Geography | state TX frame (#116) vs Harris County FIPS 48201 (#187) vs TX calibration (#191) | **Harris County evaluation frame; TX pre-event calibration geography** | Tighter, geographically coherent observable frame; matches the surviving data dictionary's "Harris County eligibility" intent and the RVO/Limburg-parallel evidence ordering. TX-wide calibration keeps a broad pre-event baseline sample. **Founder review requested** because it narrows the frame vs #116 |

### 3.1 Information-cutoff semantics (founder clarification, binding)

**2017-08-24 is the pre-event outcome-leakage and historical-baseline cutoff. It
is NOT a general "predictor cutoff."** The distinction is binding on both the
protocol and its P1-07 enforcement:

- **What the cutoff prohibits.** Harvey loss outcomes, any post-event
  loss-derived information, and any outcome-informed model or baseline
  selection from entering the frozen predictor configuration, the calibration
  sample, or the baseline artifact. The historical baseline is fitted only on
  pre-event claims (Harvey excluded; claims before 2017-01-01), and the
  code-enforced calibration cutoff rejects any row dated after 2017-08-24.
- **What the cutoff does NOT prohibit.** The preregistered **retrospective**
  use of the observed Harvey hazard intensity/depth product as the
  event-conditioning variable. An event-conditioned observed flood hazard
  product necessarily becomes available during/after Harvey; interpreting
  `information_cutoff = 2017-08-24` as "every predictor feature must
  physically exist before landfall" would make the intended event
  reconstruction impossible. This study is an **ex-post event reconstruction,
  never a prospective forecast**, and the cutoff does not convert it into one.
- **Consequence for enforcement.** P1-07 must not "fix" the cutoff by making
  the retrospective event-conditioning evidence unavailable. Hazard/depth
  evidence is outcome-blind and therefore admissible pre-evaluation;
  outcome-bearing fields (in any alias or nested form) are not, and remain
  refused.

Non-conflicting (all additive, already carried or carried above): N ≥ 200 and
clusters ≥ 30; MAE rule plus RMSE-skill/mean-bias gates; ≥95% hazard coverage;
event-reconstruction framing; eligibility-before-outcomes; exclusion accounting;
no-imputation/no-winsorisation; deterministic dedupe; insurance-limit outcome;
staged outcome unlock; ≥95% coverage hierarchy; reviewer `config_hash`; founder
freeze act; hazard/loss verification split.

## 4. Where each decision now lives in the canonical contract

- Machine pre-registration: `docs/validation/HARVEY_GATE1_PREREGISTRATION.json`
  (cutoff, baseline name/params, metric, success rule, estimand; `frozen: false`).
- Baseline calibration specification: `config/harvey_baseline_calibration_spec.json`
  (geography, dates, occupancy, fields, minimums, **bootstrap 10,000 / seed 20170825**,
  outlier policy, status `precommitted_specification`).
- Preparation harness: `app/validation/harvey/preparation.py` (outcome-blind gate,
  coverage qualification ≥95%, baseline calibration, cluster minimums, estimand
  and claim boundary).
- Data-use/acquistion manifest: `config/harvey_data_use_manifest.template.json`
  (v3 endpoint, field mapping, SHA-256s, licence status).
- Claim registry: `config/validation_claim_registry.json` (allowed vs prohibited claims).
- Data dictionary: `docs/validation/HARVEY_FEMA_V3_DATA_DICTIONARY.md`.

All clauses above are **KEEP/MERGE**'d into this document and the files listed,
or explicitly deferred to P1-06 (full-payload freeze binding) or the P1-03…P1-07
phase (code-level enforcement: dedupe, nested outcome alias rejection, coverage
truthiness, endpoint origin binding).

## 5. Supersession and close plan

- #116 and #187 are **not merged wholesale**. After this consolidation is
  exact-head reviewed and CI-green on #191, each is closed with a comment listing
  the clauses transcribed and the pointer to this document.
- #191 remains the surviving vehicle. No readiness flag, `Literal[False]`,
  `production_eligible` or any `*_verified` state is changed by this document;
  Harvey stays `NOT_QUALIFIED` / unfrozen.
- Freeze happens only after: P1-03…P1-07 hardening, the founder-reviewed values in
  §3, exact-head review, a pending independent challenge, and a real freeze commit.
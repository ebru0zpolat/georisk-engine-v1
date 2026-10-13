# GeoRisk Engine — Technical Validation, Remediation and CMIP6/CORDEX Work Plan

> **Execution reconciliation (25 August 2026):** Work-package requirements remain binding, but
> execution classes and founder limits come from
> [`00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md`](00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md).
> Deterministic validation is AUTO-PASS; missing/inconclusive evidence is AUTO-BLOCK; scientific
> method changes, evidence abandonment and eligibility claims are FOUNDER-DECISION.


**Document date:** 7 August 2026  
**Document status:** Working document  
**Product stage:** Technical-validation MVP  
**Primary purpose:** Establish a defensible current-state baseline, control public claims, rationalise the open PR backlog and deliver the first real climate-scenario integration.

**Status-control note:** PR positions in this document reflect the GitHub assessment as of the refresh timestamp below and must be refreshed immediately before any merge, closure or sequencing decision. PR #103 was opened to remove synthetic 2030/2050 multipliers; its final merge status must also be confirmed.

**Provenance of this file:** §1 is taken verbatim from the author draft supplied 7 August 2026. Remaining sections reconstruct the agreed table of contents using that draft’s intent, the repository state on `main` after PRs #97–#101, open PRs #102/#103, and [`docs/business/RVO_Current_State_Assessment_2026-08-06.md`](business/RVO_Current_State_Assessment_2026-08-06.md). Refresh the PR table before acting.

**PR status refresh timestamp (UTC):** 2026-08-07T13:27:00Z (post-merge #102/#103). Re-run `gh pr list` before further merge decisions.

---

## 1. Executive determination

GeoRisk Engine can currently be presented, with appropriate qualifications, as a technical-validation MVP. The five-layer analytical flow, audit trail, methodology and demo infrastructure are implemented. However, the climate-scenario layer, damage curves, financial-loss semantics, commercial pricing and Netherlands-specific calibration remain substantially synthetic, illustrative or unvalidated.

The principal delivery risk is not only missing code. It is the combined effect of:

- public and investor language exceeding implemented capability;
- synthetic and fallback data not being visible enough in API responses;
- inconsistent terminology, especially the use of “EAL”;
- accumulated and overlapping pull requests;
- documentation falling out of sync with the codebase; and
- the absence of a real, versioned and reproducible climate-scenario data path.

### Permitted positioning

GeoRisk Engine has a working, auditable five-layer technical-validation pipeline. Current loss curves and any available forward-looking outputs must be explicitly labelled according to their data provenance and validation status. The next scientific milestone is a narrowly scoped real climate-scenario integration followed by observed-loss validation.

### Language not currently supportable

The product should not yet be described as:

- a production-grade climate-risk model;
- a validated actuarial EAL engine;
- Dutch-calibrated;
- CSRD-compliant or IFRS S2-compliant by default;
- a geopolitical-risk platform;
- a CAT-model replacement;
- a parcel-level precision model without location-specific validation evidence; or
- a provider of VaR/MPL or calibrated loss percentiles.

---

## 2. Usable and avoidable product phrasing

| Prefer | Avoid |
|--------|--------|
| Technical-validation MVP / labelled five-layer pipeline | Production-grade climate risk platform |
| Scenario-conditional damage proxy (methodology `expected-loss-v0.3`) | Actuarial / classical EAL without qualification |
| Synthetic calibration / stub MDR (`STUBS.md`) | Validated loss curves / insurance-grade pricing |
| Forward horizons unavailable without climate-scenario data (post-#103 intent) | “2030/2050 climate scenarios” from fixed 0.95×/1.05× |
| Decision-support evidence; maps to selected ESRS/ECB themes | CSRD-/IFRS S2-compliant out of the box |
| Antalya + Rotterdam port goldens prove pipeline transfer | Pack-nl calibrated / Dutch market validated |
| Indicative contact pricing | Proven ARR / self-serve billing |

Canonical elevator line (directive): *“From climate maps to financeable adaptation: converting location-level climate hazards into asset exposure, financial loss and investment priorities.”*

---

## 3. P0 / P1 technical and public risks

### P0 (block misleading release / investor demos)

| ID | Risk | Mitigation |
|----|------|------------|
| P0-1 | Synthetic 2030/2050 intensities read as climate projections | Land PR #103 (disable fallback; horizons only when versioned maps supplied) |
| P0-2 | Public site / decks overclaim maturity | Keep claim-control from #100; close conflicting stale marketing PRs |
| P0-3 | Demo audit IDs presented as durable without volume | #99 landed; keep `GEORISK_AUDIT_TRAIL_PATH` + Railway volume |
| P0-4 | Methodology–runtime wildfire mismatch | #97 landed (flood + heat only) |
| P0-5 | “EAL” without proxy disclaimer | Keep methodology §4.1 language in API/demo copy |
| P0-6 | Overlapping open PRs causing merge thrash | §10 rationalisation table |

### P1 (near-term credibility)

| ID | Risk | Mitigation |
|----|------|------------|
| P1-1 | No real CMIP6/CORDEX path | Work packages WP-07–WP-09 |
| P1-2 | No observed-loss backtest | WP-10; RVO backtest design PRs |
| P1-3 | NL calibration absent | pack-nl Phase B; do not claim early |
| P1-4 | Fallback connectors silent in some surfaces | Surface `synthetic` / source flags on every financial response |
| P1-5 | Audit integrity under tamper/restart | Land PR #102 |

---

## 4. 2030 / 2050 status after PR #103

**Before #103 (on `main` at refresh):** adapters invent horizons via `synthetic_sensitivity_v0` (0.95× / 1.05×) with provenance stamps (#98).

**After #103 (branch `agent/disable-synthetic-horizons`, CI green at refresh):**

- Current-only hazard inputs → empty `scenario_eal` / `scenario_deltas` and method stamp `not_available_without_climate_scenario_data`.
- Horizons computed **only** when callers supply **both** versioned 2030 and 2050 intensity maps.
- Synthetic multipliers removed from live five-layer paths, demo aggregates, and misleading `horizon="2050"` stub labels.
- Independent verifier, STUBS, methodology updated on that branch.

**Rule:** Do not reintroduce fixed climate multipliers. Any temporary sensitivity mode must be opt-in, named, and never the default demo path.

---

## 5. CMIP6 / CORDEX extreme-heat integration scope (Phase 1 scientific target)

**In scope (narrow):**

- One extreme-heat intensity pathway for a bounded TR (or later NL) AOI.
- Versioned dataset id, scenario (e.g. SSP2-4.5 or SSP5-8.5 — **decision pending §7**), horizon years 2030 and 2050.
- Provenance fields on hazard outputs: `source`, `dataset_id`, `version`, `as_of`, `scenario_id`.
- Feed five-layer financial translation **without** inventing missing horizons.

**Out of scope for Phase 1:**

- Full multi-hazard CMIP stack; wildfire; drought; storm.
- Actuarial EAL under exceedance curves.
- Dutch calibration curves; CSRD automation.
- Parcel-level “precision” claims.

---

## 6. Twelve technical work packages and acceptance criteria

| WP | Title | Acceptance criteria | Phase |
|----|-------|---------------------|-------|
| WP-01 | Claim-control freeze | Marketing/API copy matches §2; no unsupported compliance/CAT claims | 1 |
| WP-02 | Horizon honesty (#103) | No default synthetic 2030/2050; unavailable stamped; tests green | 1 P0 |
| WP-03 | Stub visibility | Financial responses expose calibration badge / `synthetic` / source | 1 |
| WP-04 | EAL terminology pass | Demo/API/docs say “scenario damage proxy” where money is shown | 1 |
| WP-05 | Audit integrity (#102) | Restart + tamper tests on `AppendOnlyAuditTrail` | 1 P0 |
| WP-06 | PR backlog rationalisation | §10 table executed; conflicting drafts closed or deferred | 1 |
| WP-07 | Climate data decision record | Next deliverable: Climate Data Source and Methodology Decision Record | 1 |
| WP-08 | Extreme-heat connector (read path) | Versioned intensity maps for 2030/2050 for pilot AOI | 1–2 — **started** (CLIM-03 slice #107: `engine/climate/cmip6_heat_adapter.py`; CDS download + intensity maps still open) |
| WP-09 | Wire heat scenarios into five-layer | Demo/golden can show real horizons with provenance | 2 |
| WP-10 | Observed-loss validation design | One flood **or** heat event pack design (no lookahead) | 2 |
| WP-11 | Golden baseline refresh | Antalya + Rotterdam baselines regenerated after WP-02/09 | 1–2 |
| WP-12 | Competition / RVO claim sync | §9 corrections applied to investor materials | 1 |

---

## 7. Scientific decisions required before implementation of WP-08+

Record decisions in the Decision Log (§12) and in the Climate Data Source Decision Record:

1. **Primary archive:** CMIP6 (ESGF) vs CORDEX-EUR vs hybrid.  
2. **Scenario set:** SSP2-4.5 only vs SSP2-4.5 + SSP5-8.5.  
3. **Variable / index for extreme heat:** e.g. TX / TX30d / Heat Index — pick one for Phase 1.  
4. **Baseline climatology period** (e.g. 1991–2020) and horizon definition (20-year windows vs single years).  
5. **Spatial method:** nearest grid vs bilinear vs AOI mean; resolution disclosure.  
6. **Licence / redistribution** constraints for commercial use.  
7. **No-lookahead:** intensities must be valid as of `valuation_date`.  
8. **Failure mode:** if climate data missing → horizons unavailable (not synthetic fill).

---

## 8. Phase 1 definition of done

Phase 1 is done when **all** of the following hold:

1. PR #103 merged (or equivalent on `main`): no default synthetic climate horizons.  
2. PR #102 merged: audit restart/tamper tests on `main`.  
3. This work plan committed under `docs/`.  
4. Demo and methodology text no longer present 2030/2050 as climate projections without real maps.  
5. Open PR backlog reviewed per §10; merge/close decisions recorded in §12.  
6. Climate Data Source and Methodology Decision Record opened (even if decisions pending).  
7. CI green on `main` after the above.

**Not required for Phase 1 DoD:** live CMIP download in production; NL pack; actuarial EAL; paid pilots.

---

## 9. Competition-report corrections

When updating investor/competition materials, enforce:

- Do not claim calibrated multi-peril loss models peers may claim without matching evidence here.  
- Position on **auditability, methodology versioning, five-layer contract, stub honesty** — not on data monopoly.  
- Rotterdam golden = geographic transfer of **stub** pipeline, not Benelux product superiority.  
- Pricing bands remain indicative until sales evidence exists.

---

## 10. PR rationalisation and closure table

Refresh before acting. Snapshot at document refresh timestamp:

| PR | Title | Draft | Mergeable | Recommendation |
|----|-------|-------|-----------|----------------|
| **#104** | Phase 1 work plan + climate decision record | — | — | **Merge** (this PR) |
| **#103** | Disable synthetic 2030/2050 climate horizons | — | — | **Merged** 2026-08-07 |
| **#102** | Audit restart/tamper tests | — | — | **Merged** 2026-08-07 |
| #96 | Zero-placeholder links | yes | CONFLICTING | Superseded by #100 — **close** |
| #93–#87 | RVO workstreams 01–07 | yes | mostly MERGEABLE | Keep as docs track; sequence after Phase 1 DoD |
| #77, #64, #61, #58–#55, #51, #2 | Deploy/marketing/legacy | mixed | CONFLICTING | **Close or archive** unless owner rebases with explicit need |
| #50, #19, #18, #6 | Docs/skills | mixed | MERGEABLE | Low priority; do not block Phase 1 |

Merged already (do not reopen): #97 wildfire align, #98 horizon provenance, #99 demo audit persist, #100 marketing honesty, #101 Rotterdam golden, **#102 audit integrity**, **#103 disable synthetic horizons**.

---

## 11. Controlled execution order

1. Commit this work plan to `docs/`.  
2. Merge #102 (audit integrity tests).  
3. Merge #103 (disable synthetic horizons); regenerate goldens if baselines drift.  
4. Verify demo UI/API show horizons unavailable / provenance correctly.  
5. Close superseded conflicting PRs (#96 and confirmed-stale marketing/deploy drafts).  
6. Open Climate Data Source and Methodology Decision Record (§13).  
7. Resolve §7 scientific decisions → start WP-08.

---

## 12. Priority action log and decision log

### Actions (Phase 1 kickoff)

| When | Action | Owner | Status |
|------|--------|-------|--------|
| 2026-08-07 | Save this work plan under `docs/` | Engineering | Done (#104) |
| 2026-08-07 | Merge #102 | Engineering | **Merged** 2026-08-07T13:25:10Z |
| 2026-08-07 | Merge #103 | Engineering | **Merged** 2026-08-07T13:27:03Z |
| 2026-08-07 | Demo UI: show 2030/2050 as unavailable (not synthetic) | Engineering | In progress (#104) |
| 2026-08-07 | Refresh PR table post-merge | Engineering | Done below |
| Next | Climate Data Source Decision Record decisions | Science + Engineering | Opened; decisions pending |

### Decisions

| ID | Decision | Date | Notes |
|----|----------|------|-------|
| D-01 | Phase 1 P0 = land #102 + #103 before CMIP wiring | 2026-08-07 | Executed |
| D-02 | Do not replace `AppendOnlyAuditTrail` with SecureAuditLogger snipet | 2026-08-07 | Review: existing trail is stronger |
| D-03 | Second golden = Rotterdam port (not İstanbul) | 2026-08-07 | #101 merged; geographic generalisation |
| D-04 | CMIP scenario / variable choices | TBD | Blocked on Decision Record |
| D-05 | Default missing climate data → horizons unavailable | 2026-08-07 | Enforced by #103 |

---

## 13. Next deliverable — Climate Data Source and Methodology Decision Record

**Working title:** `docs/methodology/CLIMATE_DATA_SOURCE_AND_METHODOLOGY_DECISION_RECORD.md`

**Must include:**

- Chosen archive(s), licence, access method.  
- Scenario(s), variable/index, baseline period, horizon definition.  
- Spatial aggregation and resolution disclosure.  
- Mapping to five-layer `HazardScenarioIntensities` fields.  
- Explicit non-claims (not actuarial EAL; not multi-hazard).  
- Validation plan pointer (observed heat or flood event).  
- Versioning / methodology bump rules when source changes.

Until that record is approved, do not ship “CMIP-backed” marketing language.

---

## Appendix A — Related repository artefacts

- Methodology: `docs/methodology/GEORISK_ENGINE_METHODOLOGY.md`  
- Stub inventory: `STUBS.md`  
- RVO assessment: `docs/business/RVO_Current_State_Assessment_2026-08-06.md`  
- Directive: `GEORISK_ENGINE_REPOSITIONING.md`  
- Goldens: `data/portfolios/golden/`

## 14. Work-package execution classification

| Work packages | Class in normal execution | Automatic blocker | Material founder decision |
|---|---|---|---|
| WP-01–04, WP-12 claims/copy synchronization | AUTO-PASS inside the evidence-led claim policy | Unsupported, confidential, endorsement, legal or readiness claim | Publish a material regulated/alignment claim |
| WP-05 audit and WP-06 backlog controls | AUTO-PASS tests/reconciliation | Failed integrity check; protected issue cannot close | Delete material evidence or change security exception |
| WP-07 decision-record consistency | AUTO-PASS version/check enforcement | Missing/contradictory evidence | Change scientific method or resolve novel licence/legal interpretation |
| WP-08–09 connector/scenario wiring | AUTO-PASS contract, provenance and reproducibility checks | Missing credential/licence/data; synthetic/live-unverified promotion | Major provider/architecture change or real customer data use |
| WP-10 validation design/run | AUTO-PASS preregistered computation and pack generation | Missing licensed observation, preregistration or independent review | Appoint reviewer, abandon evidence, or change validation/eligibility status |
| WP-11 golden refresh | AUTO-PASS deterministic generation | Non-reproducible or unexplained drift | Scientific formula change causing the drift |

An HTTP connector response never constitutes scientific validation. Green CI never constitutes
pilot or production readiness. Protected validation issues remain open when evidence is missing;
their blocker is deduplicated and reported only in the Friday digest.

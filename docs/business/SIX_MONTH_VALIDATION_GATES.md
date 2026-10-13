# GeoRisk Engine — Corrected Six-Month Validation Gates

> **Execution reconciliation (25 August 2026):** Gate evidence is generated and reconciled by the
> [founder-autonomous operating roadmap](../00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md).
> Missing evidence AUTO-BLOCKs only the affected gate. Computation and evidence preparation are
> AUTO-PASS; customer commitments, terms, real data, scientific-method changes and readiness
> promotion remain FOUNDER-DECISION for the material risks stated there.


**Document date:** 13 August 2026
**Document status:** Working directive
**Product stage:** Technical-validation MVP
**Supersedes:** The 0–6 / 6–12 / 12–36 month phasing in [`RVO_Current_State_Assessment_2026-08-06.md`](RVO_Current_State_Assessment_2026-08-06.md) §4.8 for the first six months.
**Primary purpose:** Replace the loose "Phase 1 evidence" window with three sequential, time-boxed gates whose exit criteria are evidence-based and independently checkable.

---

## Why this correction

The earlier go-to-market plan compressed scientific proof, demand proof and product proof into a single 0–6 month "evidence and design partners" window. That framing let the three kinds of validation blur together, so none of them had a hard pass/fail line. Each of the three is a distinct claim that must be closed on its own evidence before the next investment is justified:

1. **Scientific validation** — the model measures something real, better than a naive baseline, and its limits are known.
2. **Demand validation** — a named buyer will pay for that measurement on a named dataset with a defined procurement route.
3. **Recurring-product validation** — the paid pilot converts into a repeatable, margin-positive annual product.

Each gate below is sequential. Do not open work on the next gate's exit criteria until the current gate has passed. A gate is passed only when every exit criterion carries written evidence; a partial or verbal result is not a pass.

---

## Gate 1 — Scientific validation (Months 0–2)

**Question answered:** Does the model measure a real hazard event more accurately than a defensible baseline, with its uncertainty and representativeness stated?

**Entry condition:** Labelled five-layer pipeline on `main`; methodology page published; synthetic/fallback provenance visible in API responses (per the technical workplan).

### Exit criteria

| # | Criterion | Evidence required to pass |
|---|-----------|---------------------------|
| 1.1 | Real hazard event selected | A single, documented real heat **or** flood event (location, dates, source) — not a synthetic or illustrative case. |
| 1.2 | Pre-registered sampling and exclusion rules | Sampling frame, inclusion/exclusion rules and analysis plan written and timestamped **before** results are computed. |
| 1.3 | Licensed observed-loss data | Observed-loss dataset with a commercial-use licence on file; provenance and licence terms recorded in the data-claims/licence matrix. |
| 1.4 | Model beats the baseline under one cutoff | Model output and a named naive baseline both evaluated on the same data under the same information cutoff, **and** the model meets the pre-registered success rule (§7 of the pre-registration) — i.e. it beats the baseline on the pre-stated metric and threshold. A recorded result in which the model fails the success rule (ties or loses to the baseline) does **not** pass this criterion; it is an honest negative that fails Gate 1. |
| 1.5 | Uncertainty and representativeness analysis | Quantified uncertainty on the headline result and an explicit statement of what population the single event does and does not represent. |
| 1.6 | External reviewer challenge report | Written challenge report from an independent technical/climate-domain reviewer, with responses to each material objection. |

**Anti-patterns that void the gate:** computing results before the sampling plan is registered; comparing against no baseline or a baseline chosen after seeing results; treating a completed comparison as a pass when the model did **not** beat the baseline on the pre-registered success rule; using observed-loss data without a licence; presenting a point estimate with no uncertainty.

---

## Gate 2 — Demand validation (Months 2–4)

**Question answered:** Will a named buyer pay for this, on a named dataset, through a real procurement route?

**Entry condition:** Gate 1 passed — there is a defensible scientific result to sell.

### Exit criteria

| # | Criterion | Evidence required to pass |
|---|-----------|---------------------------|
| 2.1 | 15 structured buyer interviews | Notes from 15 structured interviews against a fixed discovery script; segments and roles recorded. |
| 2.2 | One paid design partner | One signed **paid** design-partner agreement, or an equivalent signed procurement commitment. Non-binding LOIs do **not** pass this criterion — record them as interest under the demand narrative, but they never close 2.2. |
| 2.3 | Named executive sponsor | A named executive sponsor inside the buyer, on record as accountable for the engagement. |
| 2.4 | Agreed dataset | The specific dataset the pilot will run on, named and access-agreed. |
| 2.5 | Success criteria | Written pilot success criteria the buyer agrees define a good outcome. |
| 2.6 | Procurement route | The concrete path from pilot to purchase order (budget line, approver, timeline). |
| 2.7 | Willingness to pay tested | A stated or contracted price the buyer will pay, tested — not assumed from prior pricing hypotheses. |
| 2.8 | Delivery-cost measurement | Measured (not estimated) cost to deliver the pilot, so margin can be reasoned about at Gate 3. |

**Preference rule:** One paid design partner is worth more than two non-binding LOIs. Treat LOIs as interest, not demand; only money or a signed procurement commitment closes 2.2.

**Anti-patterns that void the gate:** counting an LOI as a paid partner; a sponsor with no budget authority; "willingness to pay" inferred from earlier €2,000–€5,000/month hypotheses rather than tested with the buyer.

---

## Gate 3 — Recurring-product validation (Months 4–6)

**Question answered:** Does the paid pilot become a repeatable annual product with a defensible margin and a stable service contract?

**Entry condition:** Gate 2 passed — a paid pilot is running with agreed success criteria.

### Exit criteria

| # | Criterion | Evidence required to pass |
|---|-----------|---------------------------|
| 3.1 | Pilot-to-annual conversion | A signed annual agreement converting the pilot, or a documented, dated conversion commitment. |
| 3.2 | Standard onboarding and refresh cycle | A repeatable onboarding runbook and a defined data/model refresh cycle — not a one-off bespoke setup. |
| 3.3 | Measured delivery hours | Actual hours to deliver onboarding and each refresh, recorded from the pilot. |
| 3.4 | Positive gross margin | Gross-margin estimate built from measured delivery hours (3.3) and price (2.7), with assumptions stated, that is **positive** — the tested price must cover measured delivery cost with margin to spare. A non-positive estimate (delivery cost at or above price) does **not** pass this criterion; it fails Gate 3 because the product is not margin-positive at the tested price. |
| 3.5 | Versioned methodology | Methodology under explicit version control with a change/decision record. |
| 3.6 | API contract | A documented, versioned API contract for the delivered product. |
| 3.7 | Audit retention | Defined audit-trail retention policy and mechanism for delivered results. |
| 3.8 | Service boundaries | Written service boundaries (scope in/out, SLAs, support limits) that keep the offer a product, not open-ended consultancy. |

**Anti-patterns that void the gate:** converting on a bespoke, non-repeatable delivery; margin computed from assumed rather than measured hours; treating a non-positive margin estimate as a pass; "annual product" with no versioned methodology or API contract; scope with no boundaries, drifting toward services-only revenue.

---

## Gate summary

| Gate | Window | Proves | Hard pass line |
|------|--------|--------|----------------|
| 1. Scientific validation | Months 0–2 | The measurement is real and beats a baseline, with known limits | Baseline-beating result on a real event, pre-registered, licensed data, external challenge answered |
| 2. Demand validation | Months 2–4 | A named buyer will pay via a real procurement route | One paid design partner (LOIs do not pass), sponsor + dataset + success criteria + procurement + tested WTP |
| 3. Recurring-product validation | Months 4–6 | The pilot becomes a repeatable, margin-positive annual product | Pilot-to-annual conversion with positive measured margin, versioned methodology/API, retention and service boundaries |

**Sequencing rule:** Gates are strictly ordered. Spending on Gate 2 buyer commitments before Gate 1 has a defensible result, or on Gate 3 productisation before Gate 2 has a paying buyer, is out of order and not permitted under this directive.

---

## Cross-references

- Business plan and revised go-to-market: [`RVO_Current_State_Assessment_2026-08-06.md`](RVO_Current_State_Assessment_2026-08-06.md)
- Technical validation and CMIP6/CORDEX work plan: [`../GeoRisk_Engine_Technical_Validation_and_CMIP6_CORDEX_Workplan_2026-08-07.md`](../GeoRisk_Engine_Technical_Validation_and_CMIP6_CORDEX_Workplan_2026-08-07.md)
- Master plan and workstream status: [`../00-master/MASTER_PLAN.md`](../00-master/MASTER_PLAN.md)
- LOI tracker: [`../04-investor/LOI_TRACKER.md`](../04-investor/LOI_TRACKER.md)
- ICP and outreach: [`../05-commercial/ICP.md`](../05-commercial/ICP.md)

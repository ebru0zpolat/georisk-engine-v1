# Six-Month Validation Gates — Live Tracker

> **Source-of-truth rule (25 August 2026):** This tracker is a generated projection target under
> the [founder-autonomous operating roadmap](../00-master/FOUNDER_AUTOMATION_OPERATING_ROADMAP.md),
> not a weekly manual checklist. Until reconciliation automation has a verified default-branch run,
> its current rows remain a static snapshot. Protected scientific, legal, customer, security and
> production issues are never automatically closed.


**Status:** Internal · 2026-08-13
**Definition (authority):** [`SIX_MONTH_VALIDATION_GATES.md`](SIX_MONTH_VALIDATION_GATES.md)
**How to use:** This is the *status* companion to the gates *definition*. Update the checkbox, evidence link and owner weekly. A criterion is passed only when its **Evidence** column links to a written artefact. A gate is passed only when every one of its criteria is checked and evidenced. Do not open the next gate's work until the current gate has passed.

**Legend:** ☐ not started · ◐ in progress · ☑ passed (evidenced) · ⛔ blocked (see note)

---

## Gate 1 — Scientific validation (Months 0–2) — target close: 2026-10-13

**Gate status:** ◐ in progress · **Blockers:** data licence, CDS key, external reviewer (all human)

| # | Criterion | State | Owner | Evidence (link) | Note |
|---|-----------|:---:|-------|-----------------|------|
| 1.1 | Real heat/flood event selected | ☐ | — | — | Depends on live data path (CDS key, WS-06). |
| 1.2 | Pre-registered sampling & exclusion rules | ◐ | — | [`gate1_pre_registration_TEMPLATE.md`](gate1_pre_registration_TEMPLATE.md) | Template ready; must be filled and timestamped **before** any result is computed. |
| 1.3 | Licensed observed-loss data | ⛔ | Founder | — | Needs commercial-use licence; track in [`LOI_TRACKER.md`](../04-investor/LOI_TRACKER.md). |
| 1.4 | Model **beats** baseline under one cutoff | ◐ | — | [`app/validation/gate1/`](../../app/validation/gate1/README.md) | Comparison harness **shell ready and tested** (fail-closed). Passes only if the model meets the pre-registered success rule (§7); a tie/loss is an honest negative that fails the gate. Needs frozen pre-registration (1.2) + licensed provider (1.3) to produce a result. |
| 1.5 | Uncertainty & representativeness analysis | ☐ | — | — | Method fixed in pre-registration §6 before results. |
| 1.6 | External reviewer challenge report | ⛔ | Founder | — | Recruit independent technical/climate reviewer. |

**Exit rule:** all six ☑ with evidence. Baseline (1.4), uncertainty method (1.5) and exclusion rules (1.2) must be fixed **before** results exist, or the gate is void. 1.4 passes only when the model beats the baseline on the pre-registered success rule — a recorded tie or loss fails the gate.

---

## Gate 2 — Demand validation (Months 2–4) — target close: 2026-12-13

**Gate status:** ☐ not started (do not begin buyer commitments until Gate 1 passes) · **Entry:** Gate 1 passed

| # | Criterion | State | Owner | Evidence (link) | Note |
|---|-----------|:---:|-------|-----------------|------|
| 2.1 | 15 structured buyer interviews | ☐ | — | — | Fixed discovery script; record segment + role. |
| 2.2 | One paid design partner | ☐ | — | — | Signed paid partner or equivalent signed procurement commitment; LOIs do not pass — record as interest only. |
| 2.3 | Named executive sponsor | ☐ | — | — | Must hold budget authority. |
| 2.4 | Agreed dataset | ☐ | — | — | Named + access-agreed. |
| 2.5 | Success criteria | ☐ | — | — | Buyer-agreed definition of a good outcome. |
| 2.6 | Procurement route | ☐ | — | — | Budget line, approver, timeline. |
| 2.7 | Willingness to pay tested | ☐ | — | — | Tested price, not inferred from prior hypotheses. |
| 2.8 | Delivery-cost measurement | ☐ | — | — | Measured, feeds Gate 3 margin (3.4). |

**Exit rule:** all eight ☑. Do not count an LOI as satisfying 2.2.

---

## Gate 3 — Recurring-product validation (Months 4–6) — target close: 2027-02-13

**Gate status:** ☐ not started · **Entry:** Gate 2 passed

| # | Criterion | State | Owner | Evidence (link) | Note |
|---|-----------|:---:|-------|-----------------|------|
| 3.1 | Pilot-to-annual conversion | ☐ | — | — | Signed annual or dated conversion commitment. |
| 3.2 | Standard onboarding & refresh cycle | ☐ | — | — | Repeatable runbook, not bespoke. |
| 3.3 | Measured delivery hours | ☐ | — | — | Actuals from the pilot. |
| 3.4 | Positive gross margin | ☐ | — | — | Built from 3.3 hours + 2.7 price; must be **positive** — a non-positive estimate fails the gate. |
| 3.5 | Versioned methodology | ☐ | — | — | Version control + decision record. |
| 3.6 | API contract | ☐ | — | — | Documented, versioned. |
| 3.7 | Audit retention | ☐ | — | — | Retention policy + mechanism. |
| 3.8 | Service boundaries | ☐ | — | — | Scope in/out, SLAs, support limits. |

**Exit rule:** all eight ☑. Margin (3.4) must use measured hours, not assumptions, and must be **positive** — a non-positive estimate fails the gate.

---

## Weekly review log

| Date | Gate | Change | By |
|------|------|--------|----|
| 2026-08-13 | 1 | Tracker created; 1.2 template ready; 1.3 and 1.6 flagged blocked (human). | Claude Code |
| 2026-08-13 | 1 | 1.4 comparison harness shell built and tested (`app/validation/gate1/`, 16 tests); fail-closed pending 1.2 freeze + 1.3 licence. | Claude Code |

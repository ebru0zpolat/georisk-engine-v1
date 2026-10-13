# GeoRisk Engine — Product Charter v2

**Status:** BINDING. Supersedes the product-identity sections of
[`GEORISK_ENGINE_REPOSITIONING.md`](../../GEORISK_ENGINE_REPOSITIONING.md) §1 and the primary-narrative
scope of [`docs/roadmap/georisk-resilience-analytics-v1.md`](../roadmap/georisk-resilience-analytics-v1.md).
**Date:** 19 September 2026
**Changes no readiness flag.** Every gate in [`GEORISK_PRODUCTION_ROADMAP_2026.md`](../../GEORISK_PRODUCTION_ROADMAP_2026.md) §1 stays false.
**Amended by [`ADR-0008`](../decisions/ADR-0008-product-family-and-own-indicator-engines.md) (opened 2026-10-13):** §1 stands; §4 gains Track C (own heat and extreme-precipitation *indicators*, under the ADR's D2–D4 limits) and Track D (P0 frontend). The §4 sentence on deriving an original flood probability stays in force. Where this charter and ADR-0008 disagree on Track C or D, the ADR wins.
**Authority order when documents conflict:** this charter → [`ENGINEERING_INVARIANTS.md`](ENGINEERING_INVARIANTS.md) →
[`ROADMAP_VERIFIER_V2.md`](ROADMAP_VERIFIER_V2.md) → everything else.

---

## 1. The one sentence

> GeoRisk Engine establishes whether a physical-risk number can be defended — its own, or somebody else's.

It is not a hazard model. It does not compete with First Street, Moody's, Climate X, Jupiter or XDI on
hazard physics, and from this date it does not try to.

## 2. What changed, and why

The previous identity was "asset-level physical climate risk → financial impact", i.e. *produce the
number*. Three facts make that the wrong primary:

1. **The hazard layer is consolidating.** MSCI/First Street (June 2026), ISS STOXX/Sust Global (2025),
   Cervest's administration (2023). An independent hazard model is an acquisition target, not a business.
2. **Buyers are internalising production.** The market for selling a bank a score is closing; the market
   for helping a bank *defend* a number is opening — EBA ESG guidelines (Jan 2026), PRA SS5/25 gap-closure
   plans (June 2026), SR 26-2 extending model-risk governance to AI, EU AI Act high-risk provisions
   (Aug 2026), TSRS assurance in Türkiye.
3. **The repository's strongest artefacts are its refusals.** `ClaimState`, fail-closed source gates,
   datum-mismatch guards, `Literal[False]` readiness flags, the hash-chained trail, the independent
   recomputation verifier, and the VERA-RAP evidence/claim grammar. Amsterdam resolving to
   `SEMANTICALLY_AMBIGUOUS` is not a defect report. It is the product demonstration.

## 3. The three questions the product answers

| # | Question | Subject | Status today |
|---|---|---|---|
| Q1 | Can this number be **recomputed** from its own sealed inputs? | our own outputs | Shipping (`recompute_eal_from_trail_record`, `tests/verification/independent_eal.py`) |
| Q2 | For the numbers that cannot be defended, **what evidence is missing**, per asset, machine-readably, and which single gap unlocks the most value? | our own portfolio | Shipping, uncommitted (`app/resilience/triage.py`) |
| Q3 | Given **somebody else's** physical-risk output, which of its claims are defensible and which are not? | a third-party report | **Not built.** This is the v2 build target. |

Q3 is the commercial core. Q1 and Q2 are the machinery it is built from.

## 4. Two tracks, explicitly ranked

**Track A — Verification of third-party numbers (primary).** Read a vendor or in-house physical-risk
output, bind each of its figures to the evidence it claims, and emit a *defensibility gap report*: which
claims are supported, which are unsupported, and exactly what would have to exist for each to become
supportable. Spec: [`docs/specs/defensibility-gap-report-v1.md`](../specs/defensibility-gap-report-v1.md).

**Track B — Own-number production (demoted to input capability).** The five-layer pipeline stays, but its
purpose changes: it exists to prove the verification standard is satisfiable, and to be the reference
implementation the verifier tests third parties against. It is no longer the thing being sold.

**Track C and Track D** — added by [`ADR-0008`](../decisions/ADR-0008-product-family-and-own-indicator-engines.md): published statistical indicators (ETCCDI heat and extreme precipitation) computed from sealed public climate data, held to the verifier's own standard; and implementation of the P0 design canvas. Neither is a physical hazard model.

**Track B never becomes a hazard-modelling programme again.** Deriving an original flood probability
(`faalkans × P(scenario | breach)`) is out of scope as a product goal. Public and vendor hazard is an
*input to be qualified*, not an output to be manufactured. See [`PRUNE_LIST.md`](PRUNE_LIST.md) §3.

## 5. Buyer

**Primary:** model validation, model risk management, and internal audit — the function whose job is to
challenge a number, not to produce one. They do not want another vendor score; they want an instrument
that tells them whether the score they already bought can survive a reviewer.

**Secondary:** the sustainability/TSRS-CSRD preparer who has to hand a reviewer something.

**Explicitly not:** actuarial pricing, reinsurance, catastrophe accumulation. The engine does not model
annual exceedance probability and must not be positioned as an actuarial input.

## 6. Prohibited claims (unchanged in force, restated because the narrative changed)

Nothing in this charter licenses any of the following:

- that any hazard, loss, probability or adaptation figure produced here is validated, calibrated,
  production-eligible, bank-grade or independently verified;
- that a verification verdict about a third-party report is an audit opinion, an assurance engagement,
  a certification, or a legal-compliance statement. It is a reproducibility and evidence-sufficiency
  finding, and its own limits ship with it;
- that "evidence-bound", "verified", "fail-closed" or "QUALIFIED" describe anything except the exact
  machine states defined in [`docs/specs/claim-state-grammar-v1.md`](../specs/claim-state-grammar-v1.md);
- any Turkish output being anything other than `NOT_QUALIFIED` until a real Turkish source is sealed
  and passes the qualification gate. No Turkish hazard value exists in this repository today.

## 7. What "done" means for v2

The charter is satisfied — and only then — when all four hold:

1. A third-party report in a documented input format produces a defensibility gap report whose every
   verdict cites the evidence (or the missing evidence) it rests on.
2. That report is reproducible: same input, same method version → byte-identical verdicts, recorded in
   the hash-chained trail.
3. The verifier that produces it does not import the production pipeline (independence invariant, INV-07).
4. One model-validation or internal-audit function outside this company has run it against a report they
   actually own, and said in writing what it got wrong.

Items 1–3 are engineering. Item 4 is the only one that decides whether the thesis is true.

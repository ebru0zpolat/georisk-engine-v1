# GeoRisk Engine — resilience analytics repositioning (v1)

> **Partially superseded (19 September 2026).** §4 (triage) and §6 (claims control) are adopted unchanged.
> §5 stages S2–S5 (Susurluk vendoring, own-number Turkish EAL) are deferred past Gate S3 — see
> [`../00-master/ROADMAP_VERIFIER_V2.md`](../00-master/ROADMAP_VERIFIER_V2.md) §7 for the line-by-line
> reconciliation. The diagnosis in §1–§2 stands and is carried into
> [`../00-master/PRODUCT_CHARTER_V2.md`](../00-master/PRODUCT_CHARTER_V2.md).

**Status:** Direction record. Binding for new GeoRisk work from this date.
**Date:** 19 September 2026
**Supersedes, in scope only:** the "asset-level EAL for Dutch collateral" framing as the
*primary* product narrative. The five-layer contract in
[`GEORISK_ENGINE_REPOSITIONING.md`](../../GEORISK_ENGINE_REPOSITIONING.md) is unchanged and
still the pipeline. What changes is which layer is the product.
**Changes no readiness flag.** Every gate in
[`GEORISK_PRODUCTION_ROADMAP_2026.md`](../../GEORISK_PRODUCTION_ROADMAP_2026.md) §1 stays false.

---

## 1. Why reposition

Three independent findings point the same way.

**The hazard-model layer is commoditising.** MSCI acquired First Street for USD 120m cash
in June 2026, closing August 2026. ISS STOXX acquired Sust Global in 2025. Cervest
entered administration in 2023 after raising over USD 40m. A physics-based model of every
property in a country is now an acquisition target priced in the low hundreds of millions,
not a defensible independent business. GeoRisk cannot win that race and should not enter it.

**Buyers are moving the work in-house.** Roughly a third of global systemically important
banks are building second-generation physical-risk models that produce financial loss
rather than hazard scores. The market for selling a bank a score is closing. The market for
helping a bank *defend* a number is opening: EBA ESG guidelines in force from January 2026,
ECB binding decisions, PRA SS5/25 property-level granularity with gap-closure plans due
June 2026, SR 26-2 extending model-risk governance to AI, EU AI Act high-risk provisions
from August 2026, and TSRS assurance beginning in Türkiye.

**The engine's real asset is its refusals.** Today every readiness flag is false, the
annual flood probability is null, and the Amsterdam pilot is semantically ambiguous. Read
as a hazard-model project that is failure. Read as a decision-support project it is the
product: the engine knows precisely what it does not know, and names it in machine-readable
form. No competitor ships that.

## 2. What the product becomes

> **Dirençlilik analitiği, risk haritaları ve karar destek sistemleri** — resilience
> analytics over an evidence-constrained portfolio.

The question changes from "what is this asset's expected annual loss" to:

1. How much of this portfolio, by value, can I actually make a defensible claim about today?
2. For the rest, exactly what evidence is missing, per asset, in machine-readable form?
3. Which single missing piece of evidence, if obtained, unlocks the most portfolio value?

Question 3 is the commercial core and the research novelty. It is a decision under
epistemic constraint, not a prediction.

This maps one-for-one onto the TÜBİTAK 2026-2028 priority topic *Dirençlilik Analitiği,
Risk Haritaları ve Karar Destek Sistemleri*, technology area Yapay Zeka ve Veri Bilimi,
application focus Afetlere Dayanıklılık, THS 2-8 — which sits under **Dijital Liderlik** and
therefore carries the call's +5 priority-area score. It must not be framed under Yeşil
Dönüşüm, which the 1501/1507 call text excludes from that bonus.

## 3. Geographic pivot: Amsterdam to Susurluk

The Netherlands pilot is blocked on probability semantics, not engineering. The Dutch
exceedance frequency is a hydraulic-load quantity, event probability requires
`faalkans × P(scenario | dike failure)`, and Amsterdam resolves to
`SEMANTICALLY_AMBIGUOUS`. That work is sound and stays on the shelf as a hard case.

Turkish basin flood management plans publish hazard and risk maps at **explicit return
periods**, which is exactly the field `FloodHazardMap.return_period_years` requires. The
Susurluk Havzası Taşkın Yönetim Planı is published, with two-dimensional hydrodynamic
modelling results transferred to GIS. Susurluk is Balıkesir's own basin.

The pack architecture already supports this with zero core change:
`evaluate_flood_source_qualification` takes `required_datum` as a parameter, so a Turkish
source passes its own vertical datum instead of NAP. That is the architecture's own
acceptance test, and it passes.

**Nothing Turkish is vendored yet.** No Turkish water level, elevation or seismic value
exists in this repository. Until a real source is sealed and qualified, every Turkish
output is `NOT_QUALIFIED` and no synthetic Turkish fixture may stand in for one.

## 4. What shipped with this record

`app/resilience/triage.py` — evidence-constrained portfolio triage, country-agnostic core.

It reads claim states and blocker codes the existing layers already produce and returns
portfolio readiness by value, the readiness distribution, and the **ranked evidence gaps**.
The ranking separates two quantities that are routinely conflated:

| Quantity | Meaning | Additive across gaps |
|---|---|---|
| `value_at_stake` | Value of every asset carrying this blocker | No, gaps overlap |
| `sole_blocker_value` | Value of assets whose only remaining blocker is this one | Yes |

`sole_blocker_value` is the primary ranking key because it is the only one that answers
"what does closing this unlock". A blocker sitting on the whole portfolio that unlocks
nothing on its own correctly ranks below a narrow blocker that releases a single asset.

When every blocked asset carries several blockers, every `sole_blocker_value` is zero.
That is a real answer, not an empty one, and it must not read as "nothing is worth doing".
The triage therefore also reports `universal_blockers`, the codes carried by every blocked
row: the portfolio's mandatory floor, below which no single action moves any value.

`scripts/run_resilience_triage_demo.py` runs this over a portfolio file. Against the
shipped verification portfolio it reports zero decision-ready value out of 11.45m across
sixteen asset-hazard rows, no gap that unlocks anything alone, and a two-item mandatory
floor of synthetic damage curves and synthetic hazard intensities. That is the correct
answer for a portfolio labelled `synthetic: true`, and it is a fair picture of where the
engine stands today.

Invariants enforced rather than assumed:

- a `QUALIFIED` asset carrying a blocker raises, it is a contradiction not a warning;
- a `NOT_QUALIFIED` asset that names no blocker raises — refusing is permitted, refusing
  silently is not;
- claim states are never averaged, the portfolio carries the weakest plus the distribution;
- `SYNTHETIC` is a distinct readiness state, `NOT_DECISION_GRADE`, so a run that completed
  on labelled synthetic input is never counted as decision-ready.

No new stub is introduced, so [`STUBS.md`](../../STUBS.md) is unchanged. The module computes
no hazard, loss or monetary value and cannot promote a claim.

## 5. Staged plan

Each stage has an exit gate. No stage opens before the previous gate passes.

**S1 — Decision-support layer, core.** Done: triage module, tests, and a demo script over
a portfolio file. Next in this stage: expose triage on the portfolio path so a run reports
readiness and gaps alongside results, and emit gaps into the audit trail so they are
replayable evidence rather than a view. That step touches `app/services/portfolio_demo.py`
and `app/services/portfolio_ingest.py`, both of which currently carry uncommitted work, so
it waits until that work lands.
*Gate:* a portfolio run returns ranked gaps with no readiness flag changed.

**S2 — Turkish source qualification, flood.** Vendor Susurluk return-period water levels
with a SHA-256 provenance sidecar, build the sealed evidence pack, and run the existing
qualification gate with the Turkish vertical datum. *Gate:* `qualified=true` from
`evaluate_flood_source_qualification` against a real sealed artifact, with licence evidence
independent of the vendor's own claim.

**S3 — Turkish elevation.** A real sealed ground elevation for the pilot cells in the same
datum as the flood map, passing `assert_differenceable`. *Gate:* a per-asset inundation
depth computed from two real sealed sources.

**S4 — First defensible Turkish asset-level loss.** Depth into the JRC depth-damage engine,
value from client-supplied collateral figures, never an indicative rate. *Gate:* one asset,
one hazard, `QUALIFIED` end to end, independently recomputed from its own audit record.

**S5 — Resilience investment analytics.** Adaptation measures priced against avoided loss,
with residual risk and the evidence state of every input carried through. *Gate:* an
adaptation recommendation whose claim ceiling is explicit.

Earthquake enters at S2 in parallel only if a PGA source with usable licence terms can be
sealed. The module already refuses to run without one, which is the correct default.

## 6. Claims control

Permitted from this record: that the engine reports what it cannot establish and ranks the
evidence needed to establish it, and that this runs today over a portfolio.

Not permitted, and not changed by anything here: any statement that a hazard, loss,
probability or adaptation figure is validated, production-eligible, bank-grade or
independently verified. The VERA-RAP experiment comparison remains a mechanism test over
scripted fixtures, not an experimental result against live baselines. Turkish outputs stay
`NOT_QUALIFIED` until S2 and S3 gates pass.

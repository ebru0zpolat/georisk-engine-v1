# Prune list — keep, demote, cut

**Status:** BINDING scope control for [`PRODUCT_CHARTER_V2.md`](PRODUCT_CHARTER_V2.md).
**Date:** 19 September 2026
**Principle:** this is a pruning, not a rebuild. Roughly a third of the repository is exactly the product;
the rest is residue from the ambition to be a hazard model. Nothing here is deleted for tidiness — each row
says whether the code stays, becomes an input, or leaves the narrative.

**Deletion policy.** Default is **demote, do not delete**. Working code with tests costs nothing to keep and
something to remove. What gets cut is *narrative position*: what the README leads with, what a demo shows,
what an agent is told to improve. Actual file deletion needs a row in §5 and a decision record.

---

## 1. Keep, and make load-bearing

These are the product. Every one of them gets promoted from "supporting machinery" to "the thing itself".

| Asset | Path | Role under v2 |
|---|---|---|
| Claim algebra | `app/loss/claim_state.py` | The grammar every verdict is expressed in |
| Fail-closed screening ladder | `app/regulation/verify.py` | Reference implementation of ordered precedence |
| Hash-chained trail | `app/services/audit_trail.py` | Evidence that a verdict is replayable |
| Independent recomputation | `tests/verification/independent_eal.py`, `expected_loss.recompute_eal_from_trail_record` | Proof the standard is satisfiable on our own numbers |
| Source qualification gate | `app/loss/flood_source_qualification.py` | Generalises to "is this third-party source usable at all" |
| Datum guard | `app/loss/flood_hazard_map.py::assert_differenceable` | The canonical worked example of a silent-error class |
| LDO band semantics | `app/loss/ldo_band_semantics.py` | Best demonstration asset in the repository (§4) |
| VERA-RAP evidence + claims | `app/research/vera_rap/` | Engine of the third-party verdict path |
| Cognitive trace | `app/research/vera_rap/trace.py` | Machine-verifiable reasoning record; speaks SR 26-2 / AI Act directly |
| EvidenceBoundBench | `benchmarks/vera_rap/` | The measurement instrument for the above |
| Resilience triage | `app/resilience/triage.py` | Ranking engine of the gap report |
| Stubs inventory | `STUBS.md` | Severity vocabulary + the verifier's own test corpus |
| ESRS E1 mapping registry, TR sustainable-finance pack | `app/regulation/`, `docs/compliance/` | Requirement source for "what would have to exist" |

## 2. Demote to input, or to a separate small product

Still runs, still tested, no longer part of the main narrative. Not mentioned in the README lead, not shown
in the flagship demo, not a target for new investment.

| Asset | Path | Disposition |
|---|---|---|
| Synthetic score path | `/v1/risk/score`, `app/scoring/risk_score.py` | Stays for API compatibility. Removed from the README lead. **Never shown to a regulated buyer** (already the rule; now enforced by narrative too) |
| Scenario-Lab v1 | `app/services/scenario_lab_service.py`, `app/scoring/scenario_score.py` | Frozen. No new work. `STUBS.md` #11/#12 stay open |
| ORAS5 / ocean connector | `app/connectors/cds_oras5.py` | Input connector only |
| Night-lights / NO₂ / Landsat thermal | `app/connectors/gee.py`, `scripts/*_audit.py` | **Separate small product**: industrial operational audit. Keep it, sell it separately if it sells, do not let it back into the physical-risk narrative |
| Risk tiles | `app/services/risk_tiles.py` | Presentation only |
| Frontend / landing | `frontend/` | Rewritten narrative (§3), no feature work in Track A. **Amended by ADR-0008 D5:** P0 design canvas implementation re-admitted as Track D |
| Five-layer own-number pipeline | `app/loss/`, `app/hazards/` | Track B: exists to prove the standard is satisfiable, not to be sold |

## 3. Cut as a *goal* (the code stays; the ambition goes)

| Ambition | Where it lives | Replaced by |
|---|---|---|
| Deriving our own annual flood probability (`faalkans × P(scenario \| breach)`) | `app/nl_pilot/ldo_probability_guards.py`, LDO/LIWO work | Taking vendor or public hazard as an **input to qualify**. The guards stay — they are how we judge somebody else's probability claim |
| Becoming a national hazard-map provider | LIWO/AHN national foundation specs | Source qualification of national datasets, for verification purposes only |
| Competing on hazard physics | — | Nothing. This race is over and we are not in it. **ADR-0008 D2:** published ETCCDI heat and extreme-precipitation indicators from sealed public data are permitted (Track C); physical modelling, downscaling and precipitation-to-flood conversion are not |
| Own-number Turkish EAL as the near-term goal | v1 record S2–S4 | Deferred past Gate S3 — [`ROADMAP_VERIFIER_V2.md`](ROADMAP_VERIFIER_V2.md) §7 |

**Important:** cutting the ambition does not devalue the work. Amsterdam resolving to `SEMANTICALLY_AMBIGUOUS`
is the finding being sold; the guards that produced it are §1 keep-and-promote assets.

## 4. Narrative rewrite (the landing and the README)

| From | To |
|---|---|
| "Signal from every relevant source" | "Can this number be defended?" |
| "From climate maps to financeable adaptation" | "We verify physical-risk numbers — ours and yours" |
| Hazard coverage, layers, connectors as headline | Refusals, provenance, reproducibility as headline |
| Demo = a map with scores | Demo = a report saying which claims survive and what is missing |

The README rewrite lands in this change. The landing page is narrative-only work and is **not** in
Track A (roadmap §6).

## 5. Actual deletions proposed (none execute without a decision record)

| Candidate | Argument for | Argument against | Recommendation |
|---|---|---|---|
| `demonstrators/`, `layers/`, `engine/`, `src/` top-level trees | Four parallel roots invite drift | May carry live imports | **Audit first**; delete nothing before Gate S2 |
| Duplicate roadmap documents (`GEORISK_PRODUCTION_ROADMAP_2026.md`, `docs/00-master/MASTER_PLAN.md`, `docs/sprints/`) | Three plans is zero plans | History value | Mark superseded in-place with a banner; do not delete |
| `.cursor/rules/` vs `.agents/skills/` vs `AGENTS.md` | Three rule surfaces for agents | Different tools read different files | Keep all three, make `AGENTS.md` the single source and have the others point at it |

## 6. Review question for every new pull request

> Does this change make it easier to establish whether a number can be defended?

If the honest answer is "no, it makes the number better", it belongs to Track B and needs an explicit reason
to be done now.

# Glossary — words with machine meanings

**Status:** BINDING. Enforced by [`ENGINEERING_INVARIANTS.md`](ENGINEERING_INVARIANTS.md) INV-12.
These words have regulatory meanings that a buyer's counsel will test. In this repository they mean exactly
what is written here and nothing wider. If you need a different meaning, add a different word.

| Term | Means exactly | Does **not** mean |
|---|---|---|
| `QUALIFIED` | Every dependency of this figure is real, sealed, licence-qualified and provenance-complete under `app/loss/claim_state.py` | Accurate, calibrated, validated, or correct |
| `SYNTHETIC` | At least one labelled synthetic/fixture input contributed | Approximate but usable |
| `NOT_QUALIFIED` | At least one enumerated blocker prevents a defensible claim | Failed, broken, or zero |
| `SUPPORTED` (VERA-RAP) | An earned `EpistemicState`: the claim's stated evidence requirements were evaluated and met | True |
| `CONDITIONALLY_SUPPORTED` | Met, subject to named conditions that were not themselves verified | Mostly supported |
| `INSUFFICIENT_EVIDENCE` | The evidence needed to evaluate was absent | The claim is false |
| `CONTRADICTED` | Evidence exists that is inconsistent with the claim | The claim is false — it means inconsistency was detected |
| `VERIFIED` (`VerificationStatus`) | An evidence item passed its own integrity check (hash, source, freshness) | The content is true |
| `STALE` | Evidence is past its declared validity horizon | Wrong |
| Verified / verification (product sense) | Recomputed from sealed inputs by an independent implementation (INV-07) | Audited, assured, certified |
| Defensible | Can be traced to evidence sufficient for the claim being made | Correct |
| Defensibility gap | A named, enumerated missing requirement that prevents a claim | An error |
| `threshold_satisfied` | The engineered value met the numeric threshold **and** the threshold source and official artefact were independently retrieved and hashed | Legally compliant |
| `production_eligible` | A release-manifest decision flag, currently `false` everywhere | Ready to use |
| `sole_blocker_value` | Portfolio value whose *only* remaining blocker is this one — additive across gaps | Value at risk |
| `value_at_stake` | Value of every asset carrying this blocker — overlapping, **not** additive | Exposure |
| `output-shaping` (STUBS severity) | The stub invents the numeric output itself | Minor |
| `data-fallback` | A real method path fed synthetic or missing input | Degraded but fine |
| Sealed | Written once, atomically, with a SHA-256 recorded before use | Saved |
| Evidence pack | A sealed bundle binding licence, datum, methodology and coverage evidence to an artefact by SHA-256 | Documentation |
| Gap report | The v2 output artefact: per-claim verdicts plus ranked missing requirements, with its own limits | An audit report |

## Banned constructions

- "GeoRisk verified vendor X's numbers" → "the gap report found N of M claims supportable **on the evidence supplied**".
- "AI-validated" / "blockchain-verified" → neither is true; the trail is an independent hash chain, not a blockchain.
- "Compliant with CSRD/TSRS/SR 26-2" → the engine produces evidence a preparer may use; it certifies nothing.
- "Bank-grade" → means nothing, and invites the question we cannot yet answer.

# Spec — claim-state grammar v1 (the one-way bridge)

**Status:** BINDING specification. Implementation target of WO-05/WO-06/WO-07.
**Version:** `claim-grammar-v1` · **Date:** 19 September 2026
**Enforces:** [`ENGINEERING_INVARIANTS.md`](../00-master/ENGINEERING_INVARIANTS.md) INV-01, INV-09.

---

## 1. Problem

Two claim vocabularies exist and were deliberately kept apart.

**Money grammar** — `app/loss/claim_state.py`, three totally ordered states:

```
NOT_QUALIFIED  <  SYNTHETIC  <  QUALIFIED
```

`weakest_claim(states)` returns the minimum. Conservative by construction, and the only vocabulary any
monetary output may speak.

**Research grammar** — `app/research/vera_rap/claims.py` and `evidence.py`:

```
EpistemicState      OBSERVED | INFERRED | HYPOTHESISED            (declared)
                    SUPPORTED | CONDITIONALLY_SUPPORTED |
                    CONTRADICTED | INSUFFICIENT_EVIDENCE |
                    REJECTED                                       (earned, via evaluation token)
VerificationStatus  UNVERIFIED | VERIFIED | REJECTED | STALE | CONTRADICTED
```

Expressive, evaluation-based, and **not** totally ordered.

Track A needs them to meet. Connecting them in both directions would let an expressive `SUPPORTED`
manufacture a `QUALIFIED`, which is the exact failure mode the whole product exists to detect in other
people's systems.

## 2. The rule

> The bridge is a **monotone downward map**. It may lower a `ClaimState`. It may never raise one.
> It exists in exactly one module. Any second implementation is a defect.

Formally, for an incoming claim with dependency states `D` and a VERA-RAP evaluation `E`:

```
bridge(D, E)  =  min( weakest_claim(D),  ceiling(E) )
```

`ceiling(E)` is the highest claim the evaluation *permits*; it never sets a floor.

## 3. Ceiling table

| `EpistemicState` | Every supporting evidence `VERIFIED` and non-synthetic | Any supporting evidence synthetic/fixture | Any evidence `UNVERIFIED`, `STALE`, `REJECTED` or `CONTRADICTED` |
|---|---|---|---|
| `SUPPORTED` | `QUALIFIED` | `SYNTHETIC` | `NOT_QUALIFIED` |
| `CONDITIONALLY_SUPPORTED` | `NOT_QUALIFIED` ¹ | `NOT_QUALIFIED` | `NOT_QUALIFIED` |
| `OBSERVED` | `QUALIFIED` ² | `SYNTHETIC` | `NOT_QUALIFIED` |
| `INFERRED` | `SYNTHETIC` ³ | `SYNTHETIC` | `NOT_QUALIFIED` |
| `HYPOTHESISED` | `NOT_QUALIFIED` | `NOT_QUALIFIED` | `NOT_QUALIFIED` |
| `INSUFFICIENT_EVIDENCE` | `NOT_QUALIFIED` | `NOT_QUALIFIED` | `NOT_QUALIFIED` |
| `CONTRADICTED` | `NOT_QUALIFIED` | `NOT_QUALIFIED` | `NOT_QUALIFIED` |
| `REJECTED` | `NOT_QUALIFIED` | `NOT_QUALIFIED` | `NOT_QUALIFIED` |

¹ Conditions that were not themselves verified are blockers. A conditional support is a *description of what
would be needed*, which is precisely the gap report's content — it is never a qualification.
² `OBSERVED` is a declared state, but a directly observed, verified, sealed measurement is the strongest
input there is. It still passes the `min` with its dependencies, so a single observation cannot lift a
derived figure.
³ An inference from verified evidence is method-dependent; it may carry a real number but never a
qualification, because the inference step itself has not been independently recomputed.

## 4. Mandatory blocker emission

Whenever `bridge(...)` returns anything below `weakest_claim(D)`, it **must** emit the blocker codes that
caused the reduction. A reduction with no blocker code is a violation of INV-02 and must raise, not warn.

```python
BridgeResult(
    claim_state=ClaimState.NOT_QUALIFIED,
    blockers=("EVIDENCE_STALE", "CONDITION_UNVERIFIED"),
    reason_ids=("E-2026-0442", "C-datum-match"),   # evidence / condition identities
)
```

## 5. Properties the implementation must satisfy (WO-07)

For all `D` (non-empty) and all evaluations `E`:

1. **No promotion.** `bridge(D, E) ≤ weakest_claim(D)` under the total order in §1.
2. **Monotonicity.** Weakening any dependency or any evidence status never raises the result.
3. **Blocker completeness.** `bridge(D, E) < weakest_claim(D)` ⟺ `blockers` is non-empty.
4. **Determinism.** Same `(D, E)` → same result, including blocker ordering (sort blockers).
5. **Totality.** Every combination in the cross-product `EpistemicState × VerificationStatus × ClaimState ×
   {synthetic, non-synthetic}` has a defined result. No `KeyError`, no implicit default.
6. **No coercion.** The enums raise on implicit `str`/`bool` use; the bridge must not stringify them.

The property test enumerates the full cross-product (8 × 5 × 3 × 2 = 240 combinations) rather than sampling.

## 6. Module contract

```
app/verification/claim_bridge.py
```

- Pure. No I/O, no clock, no network, no config.
- Imports permitted: `app.loss.claim_state`, `app.research.vera_rap.claims`, `app.research.vera_rap.evidence`, stdlib.
- Imports forbidden: anything under `app.services`, `app.api`, `app.scoring`, `app.loss` **other than**
  `claim_state`.
- Exports exactly: `BridgeResult`, `bridge(dependencies, evaluation) -> BridgeResult`, `CEILING_TABLE`.
- `CEILING_TABLE` is data, exported for the test and for documentation generation — never re-encoded in prose
  anywhere but this file.

## 7. Versioning

The table in §3 is `claim-grammar-v1`. Any change to a cell is a new version, recorded in every artefact that
used it, and requires a decision record under `docs/decisions/`. Verdicts are not comparable across grammar
versions and the report schema carries the version for that reason.

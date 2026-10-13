# VERA-RAP uncertainty propagation

## Purpose and boundary

RAP-006 preserves uncertainty as evidence is represented by claims and claims are
used in higher abstractions. **VERA-RAP does not allow abstraction to erase upstream
uncertainty.** The implementation is an isolated, deterministic research primitive;
it does not affect GeoRisk production scoring or decisions.

**Absence of an uncertainty estimate is not evidence of certainty.** Missing
estimates become explicit unresolved `MISSING_INFORMATION` components rather than
numeric zeros.

## Taxonomy and representation

`UncertaintyType` distinguishes measurement, model, sampling, temporal, spatial,
transformation, source-reliability, missing-information, contradiction, assumption,
structural, and unknown uncertainty. `UncertaintyDirection` separately records
aleatoric, epistemic, mixed, or unknown origin. These classifications are not
collapsed into one score.

An immutable `UncertaintyComponent` preserves its subject, type, direction, bounds,
confidence, distribution, unit, source IDs, method, assumptions, and metadata.
Bounds and confidence are optional, so unknown methodology or missing provenance
can remain structural and non-numeric. Finite bounds must be paired and ordered;
confidence must be within `[0, 1]`.

An `UncertaintyProfile` preserves every component while exposing an effective
interval and confidence, unresolved component IDs, assumptions, upstream profile
IDs, aggregation method, and explicit creation time. Aggregation never deletes
component provenance.

## Explicit propagation

Serializable `PropagationRule` types are pass-through, interval envelope,
confidence floor, widening, independent-evidence reduction, transformation penalty,
contradiction penalty, missing-information penalty, and custom declaration. Custom
declarations execute no code and fail closed.

Pass-through retains the input interval and confidence. Multiple intervals use the
minimum lower and maximum upper envelope; confidence defaults to the weakest input.
Values are never averaged merely to appear more precise. Widening and transformation
penalties require an explicit non-negative amount and named assumptions, add a
preserved component, and widen both ends reproducibly.

**Uncertainty may be reduced only through an explicit, reproducible, and
evidence-supported operation.** Independent-evidence reduction requires at least
two graph-backed inputs, explicit `independence_declared=true`, current `VERIFIED`
and non-stale evidence, no unresolved contradiction, and an explicit reduction
factor. Independence is never inferred from agreement or source count.

Numeric aggregation rejects incompatible units. Metres and percent require an
explicit normalization/transformation before combination. Missing numeric data is
not manufactured when unit normalization or required bounds are absent.

## Contradictions, graph lineage, and history

Contradiction and uncertainty are distinct: contradiction records incompatible
epistemic branches; uncertainty records what remains unknown. An unresolved RAP-005
artifact can add a first-class `CONTRADICTION` component and prevents independent
reduction. **Contradiction may increase uncertainty, but uncertainty aggregation
cannot resolve contradiction.**

`derive_claim_uncertainty()` reads explicit supporting-evidence and parent-claim
references from RAP-003, recursively propagates parent uncertainty where rules are
provided, marks missing or inadmissible dependencies, and returns an immutable
`UncertaintyPropagationResult`. It never mutates evidence or claims. Re-evaluation
at a later explicit time produces a new degraded artifact if evidence has become
stale; the earlier artifact remains unchanged.

The propagation result binds all input profiles, complete output profile, rule ID
and version, assumptions, evaluation time, warnings, source subjects, and target.
It is the audit artifact explaining how uncertainty moved downstream.

## Transition gate helper

`UncertaintyThreshold` supports minimum confidence, maximum interval width, upper
and lower bound limits, no unresolved components, no missing information, and no
contradiction uncertainty. Operators and values are explicit and unit-aware.
`evaluate_uncertainty_gate()` returns a machine-readable `UncertaintyGateResult`
with observed and required values, blocking component IDs, and reason. Missing
values fail rather than passing as zero.

## Determinism and serialization

Components, profiles, rules, propagation results, thresholds, and gate results use
strict field sets, exact enums, sorted identifiers and components, recursively
immutable JSON data, explicit nulls, and UTC-normalized timestamps where time is
part of the artifact. SHA-256 fingerprints are recomputed from canonical compact,
sorted-key UTF-8 JSON; no payload-supplied digest is trusted.

Given the same graph, input profiles, explicit rules, contradictions, and evaluation
time, propagation produces the same output and fingerprint. There are no wall-clock
reads, random IDs, external calls, Bayesian inference, Monte Carlo simulation,
learned confidence, or domain-specific climate assumptions.

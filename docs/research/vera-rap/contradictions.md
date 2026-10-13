# VERA-RAP contradictions

## Purpose and boundary

Contradiction is a first-class immutable epistemic artifact in the isolated
VERA-RAP research layer. **Contradiction is not noise to be discarded; it is
evidence about the limits of the system's current knowledge.** Detection records
that an incompatibility exists. Resolution separately records which explicit
conditions were satisfied before a terminal conclusion was earned.

This package does not rank sources, retrieve evidence, resolve disputes with an
LLM, or affect GeoRisk production logic. Contradiction artifacts inspect but never
mutate RAP-003 graphs or their embedded RAP-001/RAP-002 objects.

## Taxonomy and structural detection

`ContradictionType` contains direct-value, temporal, scope, unit/representation,
method, provenance, claim, constraint, transformation, and unknown conflicts.
`find_contradictions(graph, at=..., value_tolerance=...)` deterministically detects:

- explicit `CONTRADICTS` and `INVALIDATES` evidence-to-claim edges;
- claims whose earned state is `CONTRADICTED`;
- violated constraints linked to claims;
- outputs with multiple incompatible transformation producers;
- identical content identity declared by different sources; and
- compatible-scope, overlapping-time generic measurements whose numeric values
  exceed the caller's explicit non-negative tolerance.

There is no NLP comparison. Generic value comparison requires matching evidence
type, jurisdiction, spatial scope, unit, and the optional structured measurement
`subject` and `property`. Different scopes are not automatically contradictory.
Non-overlapping time windows represent possible real change and do not conflict.
Overlapping windows permit direct-value detection, but no domain threshold is
invented.

Different units produce `UNIT_OR_REPRESENTATION_CONFLICT` with an explicit
`UNIT_NORMALIZATION_REQUIRED` requirement. RAP-005 deliberately does not implement
a conversion engine: 1 metre and 100 centimetres are normalization candidates, not
an automatically selected winner. Different explicit measurement methods produce
`METHOD_CONFLICT` and require methodological comparison instead of silent
preference. Observable incompatible content/source declarations remain provenance
conflicts rather than being normalized away.

## Resolution requirements and outcomes

`ResolutionRequirement` records a stable ID, typed requirement, explicit subject
IDs, immutable parameters, mandatory flag, and description. Types cover independent
evidence, provenance, temporal and scope alignment, unit normalization, method
comparison, constraint reevaluation, transformation verification, human review,
and additional observation. They state what is missing; they fetch or execute
nothing. `RESOLUTION_PENDING` is available when such work has been identified for
future Adaptive Evidence Planner research.

`ContradictionResolutionResult` records the terminal target, satisfied and
unsatisfied requirements, supporting and rejected evidence, superseded and retained
claims, exact resolver identity/version, explicit aware time, basis, and immutable
notes. `RESOLVED`, `IRRESOLVABLE`, and `REJECTED` are earned terminal states and
cannot be assigned through ordinary `ContradictionObject` construction.

Resolution accounts for every defined requirement. `RESOLVED` requires every
mandatory requirement to be satisfied plus explicit verified, current resolution
evidence present in the graph. `IRRESOLVABLE` requires an explicitly exhausted but
unsatisfied requirement. Resolver identity, version, time, and non-empty basis are
always mandatory. **VERA-RAP permits unresolved or irresolvable contradiction to
remain a valid epistemic outcome.**

**VERA-RAP does not resolve disagreement by majority vote, recency, or model
confidence alone.** Those values may appear only as explicit inputs to a future
resolution policy. Source count never becomes quality, newer evidence never silently
replaces older evidence, and confidence never grants terminal status.

## Branch preservation, serialization, and identity

Resolution appends an immutable result and returns a new contradiction. Original
evidence IDs, claim IDs, constraints, transformations, dimensions, scope, and prior
history remain intact. Rejected evidence and superseded claims are recorded rather
than deleted. **A resolved contradiction preserves the history of the conflicting
branches.**

Resolution requirements, results, and contradictions use compact sorted-key JSON,
exact enum values, explicit nulls, UTC-normalized timestamps, sorted reference sets,
and recursively immutable JSON data. Contradiction fingerprints are SHA-256 over
the full canonical artifact: type, status, all referenced epistemic objects, scope,
dimensions, requirements, complete resolution history, detection time, ID, and
metadata. Resolution-result fingerprints bind every result field.

Strict contradiction reconstruction requires exact fields. A terminal status is
accepted only with non-empty history whose last typed result targets that exact
status; a bare serialized `RESOLVED` assertion fails closed. The helper
`has_unresolved_contradiction()` exposes unresolved state for future transition or
planning integration without changing RAP-004 and without resolving anything.

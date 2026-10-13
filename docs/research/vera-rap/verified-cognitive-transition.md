# Verified Cognitive Transition

## Purpose and research boundary

A Verified Cognitive Transition is an explicit test of whether VERA-RAP may move
from one structured cognitive state to another. A transition definition says what
*would* need to be true; it is not its own result. **A proposed cognitive transition
is not an admissible cognitive transition.** Target names and model language carry
no permission.

**VERA-RAP permits abstraction only after the system has established that the
evidential conditions required for that abstraction are currently satisfied.**

This package is research-only. It does not integrate with GeoRisk production
hazard, scoring, loss, regulation, readiness, pilot eligibility, climate, API,
frontend, or operational decisions.

## Models and gates

`CognitiveState` immutably records an ID, generic type, optional integer level,
explicit claim and evidence IDs, scope, and non-authoritative metadata. It does not
prove admissibility. `CognitiveTransition` binds source and target states, a generic
transition type, evaluator identity/version, and inspectable requirements; it
contains no result.

Requirements have stable IDs, exact `RequirementType`, subject ID, immutable JSON
parameters, mandatory flag, and description. The supported gates are verified
evidence, current graph support, explicit claim state, satisfied constraint,
maximum uncertainty, absence of contradiction, absence of invalidation, declared
transformation lineage, and an explicit graph dependency. Arbitrary callables are
not accepted.

Every mandatory gate must pass for `ALLOWED`. Optional failures remain structured
and visible but do not block. There is no vote, aggregate score, or confidence
override. **Model confidence cannot override a failed mandatory epistemic gate.**

## EvidenceGraph and current admissibility

`SUPPORT_COMPLETE` delegates directly to RAP-003
`EvidenceGraph.is_support_complete(..., at=...)`. It does not reproduce graph
logic. Consequently, historical `SUPPORTED` claim state cannot override a missing
edge, stale or inadmissible upstream evidence, unresolved constraint, or explicit
contradiction. Claim state and current graph support are intentionally separate
requirements.

`EVIDENCE_VERIFIED` requires an existing, `VERIFIED`, non-stale evidence node.
`NO_UNRESOLVED_CONTRADICTION` and `NO_INVALIDATION` inspect the explicit lineage and
never resolve or delete branches. `CONSTRAINT_SATISFIED` requires an existing,
required, `SATISFIED` constraint. Transformation checks match declared type and
version in structured lineage without executing a transformation. Dependency
checks require an exact source, target, and edge type.

The minimal uncertainty gate reads only an explicitly referenced RAP-001 or RAP-002
uncertainty. It supports `minimum_confidence` (`confidence >= threshold`) and
`maximum_width` (`upper - lower <= threshold`). Missing uncertainty, unavailable
bounds/confidence, malformed thresholds, and exceeded thresholds fail closed;
missing uncertainty is never interpreted as zero.

## Evaluation evidence and deterministic priority

`evaluate_transition()` evaluates every requirement at the caller-supplied aware
timestamp and emits immutable `RequirementEvaluation` records. A
`TransitionEvaluation` binds the complete transition definition and its fingerprint,
complete source and target states, graph fingerprint, evaluation time, evaluator
identity/version, referenced evidence and claims, every result, blockers, and
authoritative status. Each result must match the definition's requirement ID, type,
subject, and mandatory flag.

When mandatory gates produce multiple blockers, every blocker remains recorded.
The primary status uses this fixed priority:

1. `BLOCKED_GRAPH_INCOMPLETE`
2. `BLOCKED_MISSING_EVIDENCE`
3. `BLOCKED_UNVERIFIED_EVIDENCE`
4. `BLOCKED_STALE_EVIDENCE`
5. `BLOCKED_REJECTED_EVIDENCE`
6. `BLOCKED_CONTRADICTION`
7. `BLOCKED_INVALIDATION`
8. `BLOCKED_CONSTRAINT`
9. `BLOCKED_UNCERTAINTY`
10. `BLOCKED_CLAIM_STATE`
11. `BLOCKED_TRANSFORMATION`
12. `BLOCKED_DEPENDENCY`

`ALLOWED` is earned only by the evaluator path. Ordinary construction rejects it.
Deserialization accepts it only when the complete non-empty requirement results,
embedded transition definition, definition fingerprint, blocking list, primary
status, and `allowed` flag are mutually consistent.

## Determinism, identity, and history

States, requirements, transition definitions, requirement results, and transition
evaluations serialize as compact sorted-key JSON with exact enums, explicit nulls,
immutable nested data, and UTC-normalized timestamps. State fingerprints bind every
state field. Transition fingerprints bind both complete states, every requirement,
evaluator identity/version, transition type and ID, and metadata. Evaluation
fingerprints bind the transition fingerprint, states, graph fingerprint, explicit
time, requirement results, status, references, and evaluator version. SHA-256 over
canonical UTF-8 JSON is used throughout.

There are no wall-clock reads, random IDs, external services, or insertion-order
effects. Re-evaluation creates a new proof artifact: an evaluation allowed at T1
remains immutable even when stale evidence causes a blocked evaluation at T2.

The controlled demonstrator uses explicitly synthetic research data for the chain
Observation → Hazard → Vulnerability → Materiality and three transition definitions
with current-support and constraint requirements. It makes no real-world or
GeoRisk production-validity claim. Future work may use these proof artifacts for
planning or richer cognitive transition research; RAP-004 implements neither.

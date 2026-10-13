# VERA-RAP ClaimObject

## Purpose and research status

`ClaimObject` is an immutable, structured statement for the isolated VERA-RAP
research layer. An RAP-001 `EvidenceObject` records an artifact, its provenance,
and verification state; a claim records what is asserted about a subject and how
that assertion was derived. Claims reference evidence by ID only. Resolution and
admissibility belong to a future evaluator and `EvidenceGraph`.

This model is experimental. It is not imported into or used by GeoRisk production
hazard, loss, scoring, regulation, readiness, eligibility, API, or frontend paths.

**A claim's epistemic state is an evaluated property, not a linguistic property.**
Scientific identity is structured as `predicate`, `subject`, and `value`; wording
placed in metadata is non-authoritative. RAP-002 does not attempt NLP equivalence.

## Epistemic states

- `OBSERVED`: directly represents an observation and requires supporting evidence.
- `INFERRED`: derived from evidence or a parent claim, without implying support.
- `HYPOTHESISED`: a tentative proposition that may have no evidence yet.
- `SUPPORTED`: an evaluation found mandatory support requirements satisfied.
- `CONDITIONALLY_SUPPORTED`: evaluated support is limited by an explicit
  assumption, constraint, condition, or uncertainty.
- `CONTRADICTED`: an evaluation supplied material contradicting evidence. Existing
  support is retained rather than silently erased.
- `INSUFFICIENT_EVIDENCE`: evaluation could not establish support and records the
  failed requirements without fabricating evidence.
- `REJECTED`: evaluation records a failed integrity requirement, reason, or
  constraint.

`OBSERVED`, `INFERRED`, and `HYPOTHESISED` are declared states available through
ordinary construction. The other five are earned states. `SUPPORTED` is therefore
not caller-assignable, nor is `CONDITIONALLY_SUPPORTED`. A frozen dataclass alone
would not protect this boundary because `dataclasses.replace` reconstructs an
object; the custom constructor also requires an internal evaluation capability and
a matching final evaluation record for every earned state.

**VERA-RAP permits 'insufficient evidence' to be a successful reasoning outcome.**
It is a first-class terminal result rather than an exception or a reason to invent
support.

## Evaluation and transition provenance

`ClaimEvaluationResult` records the target earned state, supporting and
contradicting evidence IDs, assumptions, failed requirements, conditions,
evaluator identifier and version, and an aware evaluation timestamp. It performs
no graph traversal, inference, uncertainty propagation, or contradiction policy.
It is only the explicit, immutable event required to call `with_evaluation()`.

`with_evaluation()` returns a new claim, unions prior and newly reported evidence,
limitations, and failures, and appends the evaluation event. It never mutates the
source claim or deletes prior support. A later explicit evaluation can reassess an
insufficient, contradicted, or rejected claim; merely replacing its state cannot.
This event history is intended to support a future Verified Cognitive Transition
mechanism, but no cognitive transition gate is implemented in RAP-002.

## Serialization and semantic identity

Canonical serialization is strict compact JSON with sorted object keys, explicit
nulls, exact uppercase enum values, JSON-compatible nested values, and timestamps
normalized to UTC ISO 8601 with six fractional digits and `Z`. Public
deserialization accepts an earned state only when the payload contains a valid
evaluation history whose final record targets that exact state. A bare
`"epistemic_state": "SUPPORTED"` payload is rejected.

The canonical serialization preserves every field for lossless round trips. The
SHA-256 semantic fingerprint intentionally uses:

- `predicate`, `subject`, `value`, `unit`, and `epistemic_state`;
- supporting and contradicting evidence IDs and parent claim IDs;
- assumptions, constraints, conditions, and failed requirements;
- uncertainty, derivation method, and scope.

Evidence and claim reference tuples are sorted after duplicate rejection, while
JSON array order inside structured subject/value/scope data remains semantic.

The fingerprint excludes `claim_id`, `created_at`, `reasoning_trace_id`, metadata,
and evaluation history. `claim_id` is a record locator, timestamps and trace IDs
describe event provenance, metadata may contain explanatory prose, and evaluation
history describes how the current state was reached. Their complete values remain
in canonical serialization, but two records with the same current semantic claim
state have the same fingerprint. Thus `claim_id` and fingerprint are deliberately
different concepts.

Future `EvidenceGraph` work may resolve references and evaluate admissibility.
Future Verified Cognitive Transitions may consume the preserved evaluation events.
Neither is implemented here, and this model performs no automatic or probabilistic
state transition.

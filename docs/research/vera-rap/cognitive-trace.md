# Cognitive Trace (RAP-009)

## Purpose and research boundary

RAP-009 records how VERA-RAP moved from evidence to claims, transitions,
contradictions, uncertainty, abstraction, and planning as a deterministic,
machine-verifiable artifact. **VERA-RAP Cognitive Trace records externally
verifiable reasoning artifacts, not private chain-of-thought.**

A trace is an audit and reproducibility artifact. It is not model reasoning,
hidden deliberation, prose explanation, a function-call log, telemetry, debug
output, or a mutable event stream. It captures only explicit research-layer
artifacts and their relationships. GeoRisk production decision logic is untouched
and nothing in this module performs retrieval, execution, persistence, or
observability.

## Artifact references

`ArtifactReference` binds an `artifact_id`, an `ArtifactType`, a SHA-256
`fingerprint`, a schema version, an optional creation time, and the producing
module. `reference_for()` derives a reference from any RAP-001 to RAP-008
artifact. Objects that legitimately have several versions in one episode carry a
version suffix in their reference ID: claims by evaluation count, contradictions
by resolution count, abstractions by verification count, and evidence, graphs
and result artifacts by a fingerprint prefix. Artifact IDs are never trusted
alone. **A trace is valid only when the artifacts it references are the artifacts
that were actually evaluated.**

## Events and the event DAG

`TraceEvent` is typed by `TraceEventType`, names its subjects, references its
artifacts with a fingerprint for each, links its `input_event_ids`, and carries
an explicit timestamp, actor identity and version, and machine-readable
`details`. Its ID is a SHA-256 over its content, so identity is independent of
insertion order.

Events form a DAG through `input_event_ids`. Construction rejects self-reference,
missing inputs, cycles, events earlier than their inputs, events outside the
trace window, duplicate events, artifacts referenced without a listed reference,
and the same artifact ID bound to two fingerprints. Events are canonicalised by
timestamp then ID, so semantically equal traces have equal fingerprints whatever
the insertion order.

Type-level predecessor rules are checked at validation time: verification,
rejection, and staleness need a registration upstream; claim evaluation and
support evaluation need a declaration; transition evaluation needs support or
evidence events; contradiction evaluation needs detection; gate evaluation needs
propagation; abstraction verdicts need a proposal; plans and abstentions need
identified blockers; executions need a plan; replans need an execution.

## What each layer records

- **Evidence (RAP-001).** `EVIDENCE_REGISTERED` carries the evidence reference,
  verification status, provenance fingerprint, and content hash; `VERIFIED` or
  `REJECTED` follow as separate events, and `EVIDENCE_BECAME_STALE` records an
  explicit staleness evaluation at a stated instant. Payloads are referenced by
  fingerprint, never duplicated.
- **Claims (RAP-002).** `CLAIM_DECLARED` and `CLAIM_EVALUATED` are distinct. An
  earned state is linked to the `ClaimEvaluationResult` reference and to the
  supporting evidence references.
- **Graph and support (RAP-003).** `GRAPH_VALIDATED` binds the graph fingerprint.
  `SUPPORT_EVALUATED` binds the `SupportCompletenessResult` and records the
  claim, timestamp, completeness, stale, unverified and rejected evidence,
  contradicted dependencies, constraint blockers, and upstream issues.
- **Transitions (RAP-004).** `TRANSITION_EVALUATED` binds the complete transition
  definition, the evaluation, and the graph, and records status, mandatory and
  optional requirement results, blocking requirements, and all fingerprints.
- **Contradictions (RAP-005).** `CONTRADICTION_DETECTED` preserves the conflicting
  branches and resolution requirements. `CONTRADICTION_EVALUATED` exists only when
  a real `ContradictionResolutionResult` exists and preserves satisfied and
  unsatisfied requirements plus retained, superseded, and rejected references.
  Resolution never erases detection.
- **Uncertainty (RAP-006).** `UNCERTAINTY_PROPAGATED` records input profile
  fingerprints, rule identity and version, output fingerprint, warnings, and
  time. `UNCERTAINTY_GATE_EVALUATED` records the threshold, pass or fail, and
  blocking components.
- **Abstraction (RAP-007).** `ABSTRACTION_PROPOSED` is separate from
  `ABSTRACTION_VERIFIED`, `ABSTRACTION_BLOCKED`, and `ABSTRACTION_SUPERSEDED`.
  Verdicts record support results, transition evaluation IDs, contradictions,
  gate results, failed requirements, and the graph fingerprint.
- **Planning (RAP-008).** `BLOCKERS_IDENTIFIED`, `PLAN_CREATED`,
  `PLAN_EXECUTION_RECORDED`, `REPLAN_CREATED`, and `PLANNER_ABSTAINED` record
  blocker types and causes, which blocker each action addresses, action
  preconditions, execution facts, and abstention reasons. Why the planner acted,
  what changed, and why replanning occurred are all reconstructible.

## Checkpoints and successor traces

`TRACE_CHECKPOINT` binds the current evidence graph, abstraction graph, and
active plan fingerprints together with a declared admissible-state map. A
checkpoint records a reproducible system state; it certifies nothing.

A later episode descends from an earlier trace through `parent_trace_id` and
`parent_trace_fingerprint`, which must be supplied together. An earlier trace is
never modified: `append_event()` and `successor()` return new traces.
**Historical cognitive outcomes are preserved rather than rewritten.** An
`ALLOWED`, `VERIFIED`, or `ABSTAINED` event at time T1 stays in the T1 trace when
T2 records a blocked state.

## Registry, validation, replay, and tamper detection

`ArtifactRegistry` is an in-memory identity map used only for verification. It
rejects registering the same ID with a different fingerprint. `validate_trace()`
reports missing artifacts, missing events, fingerprint mismatches, cycles,
chronology errors, orphan events, unresolved predecessor references, and
warnings. If the registry holds `C1` with one fingerprint and the trace binds
`C1` to another, the trace is invalid.

`replay_trace()` walks the DAG in topological order, checks that every event
carries an artifact of the expected type and an outcome code where required,
halts at the first event whose bindings the registry cannot verify, and reports
the latest outcome per subject. It reruns no scientific computation.

## Explain and current outcome

`trace.explain(subject_id)` returns related, upstream, and downstream event IDs,
artifact IDs, blocking and planning event IDs, an event-type map, and the
current epistemic outcome. The current outcome is the latest outcome-bearing
event for the subject ordered by time, DAG depth, then ID. Truth is never
inferred from event counts, and no prose is generated.

## Determinism, serialization, and fingerprints

Given the same artifacts, relationships, timestamps, actor versions, and trace
version, the trace fingerprint is identical. There are no wall-clock reads,
random IDs, or network calls. References, events, traces, validation results,
and replay results serialize as canonical sorted-key JSON. Reconstruction rejects
unknown or missing fields, invalid enums, malformed timestamps, and mismatched
IDs, and recomputes every fingerprint. **Reproducibility requires both artifact
identity and reasoning-path identity.**

## The no-chain-of-thought boundary

Keys such as `chain_of_thought`, `internal_reasoning`, `scratchpad`, `thoughts`,
`prompt`, and `response` are rejected anywhere in event details, metadata, or
trace metadata, and the strict schema rejects them as fields. Explanations are
reason codes and artifact relationships only.

## Relationship to future benchmarks

`trace.completeness()` exposes explicit numerator and denominator counts for
evidence reference coverage, claim evaluation coverage, transition evaluation
coverage, uncertainty trace coverage, abstraction trace coverage, planning trace
coverage, unresolved references, and per-type event and artifact counts. These
support future RAP-010 EvidenceBoundBench metrics without defining any score
here.

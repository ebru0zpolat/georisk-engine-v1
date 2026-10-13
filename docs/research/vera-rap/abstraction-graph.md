# Verified Abstraction Graph (RAP-007)

RAP-007 is a research-only hierarchy for constructing concepts without changing GeoRisk production decisions. **Abstraction is an epistemic operation, not a formatting operation.** An `AbstractionNode` declares a concept; existence does not establish truth or admissibility. `VERIFIED` is earned only by a reproducible `AbstractionVerification`.

## Levels, rules, and boundaries

The ordered, domain-independent levels are `OBSERVATION`, `PHYSICAL_STATE`, `CONDITION`, `EXPOSURE`, `VULNERABILITY`, `IMPACT`, `MATERIALITY`, and `DECISION`. An `AbstractionRule` explicitly binds source levels, a target level, required claim predicates, transition type, uncertainty thresholds, version, and skip policy. Adjacent forward movement is the default. Backward movement is rejected and a level skip requires an explicit versioned rule.

**VERA-RAP does not permit a higher-level concept to inherit validity merely because lower-level data exists.** **Every abstraction boundary is independently verifiable.** Each required edge binds a RAP-004 transition definition and its target can verify only with an `ALLOWED` evaluation for the exact transition, exact cognitive source/target membership, and current evidence-graph fingerprint.

## Verification gates

Verification evaluates all blockers rather than selecting one opaque reason:

- every member claim must exist and be currently support-complete under RAP-003;
- required upstream abstractions must currently carry earned `VERIFIED` status;
- required claim predicates must be present;
- every required RAP-004 transition must be `ALLOWED` and bound to the current graph;
- RAP-005 `DETECTED`, `UNRESOLVED`, `RESOLUTION_PENDING`, or `IRRESOLVABLE` contradictions block dependent abstractions;
- every rule-named RAP-006 uncertainty gate must exist and pass, and its profile must be present;
- unresolved evidence lineage blocks verification.

Historical `SUPPORTED` claim state cannot replace current support completeness. A previously verified artifact remains immutable, but a new evaluation after root evidence becomes stale is blocked. Contradiction history is never suppressed and uncertainty is not independently recomputed in RAP-007.

## Lineage and supersession

`AbstractionGraph.explain()` returns structured, deterministically ordered claims, direct and upstream evidence, upstream abstractions, transitions, constraints, contradictions, uncertainty profiles, transformations, and unresolved dependencies. **High-level cognition remains traceable to low-level evidence.** It does not generate narrative prose.

Supersession is explicit: a new abstraction may identify an older abstraction it supersedes, while the older node, verification history, claims, and evidence remain preserved. Supersession is not mutation of epistemic history.

## Determinism and serialization

The graph is an immutable DAG: duplicate identities, self-loops, missing references, cycles, undeclared sources, ambiguous rules, backward edges, and unauthorized skips fail closed. Nodes, edges, rules, and transitions are canonicalized in stable identity order. Timestamps are explicit, mappings are key-sorted, and no wall clock, randomness, model call, or external service participates.

SHA-256 fingerprints bind complete canonical content. Node identity includes status and verification history; rule identity includes its versioned policy; verification identity includes current graph fingerprint and every gate result; graph identity includes all nodes, edges, rules, and transition definitions. Strict reconstruction rejects unknown/missing fields and non-canonical JSON, recomputes fingerprints, and cannot manufacture a bare `VERIFIED` node because matching internally consistent verification history is required.

This module does not perform semantic abstraction, adaptive planning, contradiction resolution, evidence retrieval, or production scoring/API behavior.

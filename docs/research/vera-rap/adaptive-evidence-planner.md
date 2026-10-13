# Adaptive Evidence Planner (RAP-008)

## Purpose and research boundary

RAP-008 is a research-only planner over the VERA-RAP epistemic stack. Its job is
not to produce an answer. It reads a blocked reasoning state, identifies why
progression is blocked, and proposes the minimum set of explicit evidence or
verification actions that could make permission attainable.

**Plan to resolve evidence deficits, not plan to generate an answer.**

**The planner cannot grant epistemic permission; it can only propose actions that
may make permission attainable.** It never marks a claim `SUPPORTED`, a transition
`ALLOWED`, a contradiction `RESOLVED`, or an abstraction `VERIFIED`. Those states are
earned only through RAP-002, RAP-004, RAP-005, and RAP-007 evaluators. **A plan is
not evidence.**

The module performs no retrieval, network access, human review, model calls,
contradiction resolution, or production operation. GeoRisk production eligibility,
hazard, scoring, loss, regulation, readiness, pilot, frontend, API, climate-model,
and operational decision logic are untouched.

## Planning targets

`PlanningTarget` is immutable and names what should become attainable:
`CLAIM_SUPPORT` (requires `claim_id`), `TRANSITION_PERMISSION` (`transition_id`),
`ABSTRACTION_VERIFICATION` (`abstraction_id`), `CONTRADICTION_RESOLUTION` (the
`target_id` names the contradiction), and `UNCERTAINTY_REDUCTION` (`claim_id`).
`desired_state` is descriptive; for claim targets an `EpistemicState` name is
checked against the current claim state. Enum members reject string and Boolean
coercion.

**VERA-RAP planning operates over explicit epistemic blockers rather than
free-form task descriptions.**

## Blocker extraction

`identify_blockers()` derives `EpistemicBlocker` records deterministically from
existing artifacts and reuses RAP logic instead of re-implementing it:

- RAP-003 `EvidenceGraph.is_support_complete()` yields `SUPPORT_INCOMPLETE` plus
  the underlying `STALE_EVIDENCE`, `UNVERIFIED_EVIDENCE`, `REJECTED_EVIDENCE`,
  `MISSING_DEPENDENCY`, `CONSTRAINT_UNRESOLVED`, and `CONSTRAINT_VIOLATED` blockers.
- RAP-004 failed `RequirementEvaluation` records map by requirement type to
  evidence, support, `INVALID_CLAIM_STATE`, constraint, `MISSING_UNCERTAINTY` or
  `EXCESSIVE_UNCERTAINTY`, contradiction, `MISSING_TRANSFORMATION`, and
  `MISSING_DEPENDENCY` blockers; the evaluation itself yields `TRANSITION_BLOCKED`.
- RAP-005 artifacts yield `UNRESOLVED_CONTRADICTION` (with their resolution
  requirement IDs), `CONTRADICTION_RESOLUTION_PENDING`, or, for `IRRESOLVABLE`,
  a `TERMINAL` `NO_ADMISSIBLE_RESOLUTION_PATH` blocker. A conflicting branch with
  no artifact is still recorded as a contradiction blocker.
- RAP-006 failed `UncertaintyGateResult` records yield `EXCESSIVE_UNCERTAINTY`, or
  `MISSING_UNCERTAINTY` when the observed value is absent; absence is never zero.
- RAP-007 `BLOCKED` verifications yield `ABSTRACTION_BLOCKED` and are traced
  downward through the abstraction graph into the underlying transition,
  support, contradiction, uncertainty, lineage, and upstream-abstraction blockers.

Severity is `INFO`, `WARNING` (optional requirement failures), `BLOCKING`, or
`TERMINAL`. Every blocker is preserved; nothing is collapsed into one reason.
Blocker identity excludes detection time so replanning can match blockers.

## Root-cause planning

Blockers carry `caused_by` links. `STALE_EVIDENCE` causes `SUPPORT_INCOMPLETE`,
which causes `TRANSITION_BLOCKED`, which causes `ABSTRACTION_BLOCKED`. The planner
fixes root blockers directly and gives symptom blockers only their re-evaluation
action (`RECOMPUTE_SUPPORT`, `REEVALUATE_TRANSITION`, `REEVALUATE_ABSTRACTION`),
wired through preconditions. A stale root therefore yields one refresh and a
re-evaluation chain, not four independent fixes.

## Admissible evidence actions

`EvidenceActionType` covers retrieval, independent evidence, stale refresh,
verification, provenance re-verification, unit normalization, transformation
verification and declaration, scope and time-window reconciliation, constraint
re-evaluation, human review, uncertainty reduction, contradiction-requirement
resolution, support recomputation, transition and abstraction re-evaluation, and
`ABSTAIN`. There is no action that ignores staleness, uses evidence anyway, or
marks anything valid; parameters implying status mutation are rejected.

`is_action_admissible()` refuses an action when its subject does not exist, when
its type cannot affect the blocker type, when transformation semantics are
missing, when it would resolve a contradiction without its requirements, when it
would verify stale evidence as current, or when uncertainty reduction assumes an
independence that no preceding action establishes.

## Minimum epistemic plan and deterministic selection

Planning is a conservative deterministic greedy pass over root blockers. Default
fixes are generated per blocker type; caller-supplied `candidate_actions` join the
pool after admissibility filtering. Among candidates for a blocker the planner
prefers, in order: greater blocker coverage, lower explicit `estimated_cost`
(when any candidate carries a cost), lower type priority, higher explicit
`estimated_information_gain`, then action ID. Costs and gains are never invented;
absent costs fall back to type priority alone.

The fixed action priority is:

1. satisfy a missing dependency (retrieve, request independent evidence, add
   transformation, re-verify provenance, normalize unit, reconcile scope/time);
2. refresh stale evidence;
3. verify unverified evidence or a transformation;
4. satisfy explicit contradiction-resolution requirements (including human review);
5. reduce uncertainty;
6. re-evaluate failed constraints;
7. recompute support;
8. re-evaluate the transition;
9. re-evaluate the abstraction;
10. abstain.

Actions are ordered by that priority, then precondition depth, then ID. Insertion
order never matters.

## Contradiction planning

RAP-005 resolution requirements drive the actions: independent evidence or
additional observation requests independent evidence; provenance, temporal, scope,
unit, constraint, and transformation requirements map to their reconciliation or
verification actions; method comparison and human review map to
`REQUEST_HUMAN_REVIEW`. A final `RESOLVE_CONTRADICTION_REQUIREMENT` action, with
the requirement actions as preconditions, proposes recording a resolution through
`evaluate_resolution`. The planner never marks a contradiction `RESOLVED`.

## Uncertainty planning

`EXCESSIVE_UNCERTAINTY` always ends in `REDUCE_UNCERTAINTY`, which is admissible
only after an action that establishes or obtains independent evidence, or after
the stale or unverified sources that caused it are repaired. This follows RAP-006:
reduction requires explicit independence, current `VERIFIED` inputs, and no
unresolved contradiction. `MISSING_UNCERTAINTY` requests an explicit declaration.

## Stale and missing evidence

Stale evidence yields `REFRESH_STALE_EVIDENCE`. Missing evidence yields
`RETRIEVE_EVIDENCE`, or `REQUEST_INDEPENDENT_EVIDENCE` when independence is
required. The planner records what is required; it never retrieves anything.

## Separation between planning and execution

`PlanExecutionResult` is an immutable record of externally supplied facts:
completed and failed action IDs and newly produced artifact IDs. It mutates
nothing. `PlanStatus` is `READY`, `WAITING_FOR_EVIDENCE`, `WAITING_FOR_REVIEW`,
`BLOCKED`, `COMPLETED`, or `ABSTAINED`. `COMPLETED` is reachable only when the
target artifact has actually been re-evaluated as admissible; planning alone
cannot produce it.

## Replanning and loop protection

`replan()` requires the execution result of the previous plan, re-extracts
blockers from current artifacts, drops blockers that no longer exist, keeps those
that persist, detects new ones, and generates actions only where required. The
previous plan is immutable; the new plan records `previous_plan_id` and a
`plan_history` chain.

If no artifact was produced, the blocker set, action set, and graph fingerprint
are unchanged, the plan's `no_progress_count` increments and its status becomes
`BLOCKED`. A second consecutive no-progress replan terminates with `ABSTAIN` and
reason `NO_ADMISSIBLE_RESOLUTION_PATH`. Identical plans are never emitted forever.

## Abstention

`ABSTAIN` is a valid terminal outcome: an `IRRESOLVABLE` contradiction, human
review required but declared unavailable, a definition-level abstraction failure,
no admissible action for a blocking blocker, or repeated planning without
progress. **Failure to obtain epistemic permission is a valid planning outcome.**

## Determinism, serialization, and fingerprints

Given the same target, graph, artifacts, candidates, costs, gains, timestamp, and
planner version, the plan is identical. There are no wall-clock reads, random
IDs, network or model calls. Targets, blockers, actions, plans, and execution
results serialize as canonical sorted-key JSON with exact enums and UTC
timestamps. IDs and fingerprints are SHA-256 over canonical content and are
recomputed on reconstruction; serialized IDs are checked, never trusted. The plan
fingerprint binds target, blockers, actions, planner identity and version,
creation time, graph fingerprint, terminal state, and abstain reason.

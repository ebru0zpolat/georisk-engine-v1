# VERA-RAP EvidenceGraph

## Purpose and boundary

Flat citations cannot show whether a claim depends on another claim, a mandatory
constraint, or a versioned transformation. `EvidenceGraph` therefore records the
complete directed dependency structure between immutable RAP-001 evidence and
RAP-002 claims. It remains an isolated, in-memory research primitive and is not
wired into any GeoRisk production path.

**EvidenceGraph does not decide what is true. It determines whether the dependency
structure required to justify a claim is complete and currently admissible.**

## Nodes and edges

All nodes and edges are immutable. Four node types are supported:

- `EvidenceNode` embeds an `EvidenceObject`; its node ID is the evidence ID.
- `ClaimNode` embeds a `ClaimObject`; its node ID is the claim ID.
- `ConstraintNode` records an ID, generic type, description, whether it is required,
  `UNRESOLVED`/`SATISFIED`/`VIOLATED` status, and immutable metadata.
- `TransformationNode` records a transformation ID, generic type, required version,
  input schema, output schema, and immutable metadata. It executes no operation.

The exact permitted edge shapes are:

| Edge | Source | Target | Meaning |
|---|---|---|---|
| `SUPPORTS` | Evidence | Claim | Evidence is a declared direct support dependency. |
| `CONTRADICTS` | Evidence | Claim | Evidence is an explicit contradiction branch. |
| `DERIVES` | Claim | Claim | The source is a parent of the target claim. |
| `DERIVES` | Transformation | Evidence or Claim | The target is an explicit output. |
| `TRANSFORMS` | Evidence | Transformation | Evidence is an explicit transformation input. |
| `REQUIRES` | Claim | Constraint | The claim depends on the constraint. |
| `INVALIDATES` | Evidence | Claim | Evidence explicitly invalidates the claim. |

Other shapes, missing endpoints, duplicate edges, duplicate node IDs, empty IDs,
self-loops, and cycles are rejected rather than repaired. Cycle discovery uses
lexicographically ordered nodes and adjacency lists, making the reported cycle
deterministic. A transformation is structurally consistent only with at least one
explicit input and output; this preserves lineage without performing the operation.

## Structural consistency

`validate_consistency()` returns a structured `GraphValidationResult`, never a bare
Boolean. Every supporting evidence ID on a claim must have an `Evidence --SUPPORTS
--> Claim` edge, every contradicting ID a `CONTRADICTS` edge, and every parent claim
ID a `Claim --DERIVES--> Claim` edge. Conversely, unrecorded support,
contradiction, and parent edges are inconsistent. Missing nodes and edges remain
explicit unresolved dependencies. Warnings never make an invalid graph valid.

## Current support completeness

`is_support_complete(claim_id, at=...)` evaluates at an explicit aware timestamp
and returns a structured `SupportCompletenessResult`. It never mutates evidence or
claims. It traverses parent claims and transformation inputs to the root evidence,
and fails closed for:

- missing nodes, edges, supporting dependencies, or transformation inputs;
- unverified, rejected, contradicted, explicitly stale, or time-expired evidence;
- explicit contradiction or invalidation branches;
- unresolved or violated required constraints; and
- any issue propagated from an upstream claim.

Only verified, non-stale evidence can satisfy an evidence dependency. Satisfied
required constraints permit completeness; optional constraints do not block it and
are reported as warnings. No voting, freshness preference, or contradiction
resolution occurs. Supporting and contradicting branches are both preserved.

Claim state records an evaluated epistemic event; graph support completeness
evaluates whether the current dependency structure still justifies that state.
**A historically supported claim may cease to be currently support-complete without
rewriting its historical evaluation state.** Thus stale root evidence invalidates
every downstream claim in a dependency chain without rewriting any immutable node.

## Lineage, serialization, and identity

`explain()` returns machine-readable `ClaimLineage`: direct support, direct
contradictions/invalidations, parent claims, constraints, transformation IDs,
upstream evidence IDs, and unresolved dependencies, all deterministically ordered.
It generates no explanatory prose.

Canonical graph JSON includes every complete embedded node payload and every edge.
Nodes sort by node ID; edges sort by source ID, target ID, then exact edge enum
value. Nested objects use the RAP-001/RAP-002 canonical payloads, sorted JSON keys,
compact separators, explicit nulls, and exact enum values. The graph fingerprint is
lowercase hexadecimal SHA-256 over those canonical JSON UTF-8 bytes. Consequently,
insertion order, dictionary order, memory address, and debug formatting do not
affect identity.

Strict reconstruction delegates embedded evidence to
`EvidenceObject.from_canonical_json()` and embedded claims to
`ClaimObject.from_canonical_json()`. Graph deserialization therefore cannot bypass
RAP-002 earned-state protections. A malformed `SUPPORTED` claim without its valid
evaluation history remains rejected.

Future Verified Cognitive Transition research may consume consistency,
completeness, and lineage results as gate inputs. RAP-003 implements no transition
gate, graph database, retrieval, uncertainty propagation, fusion, or domain logic.

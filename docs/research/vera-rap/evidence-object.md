# VERA-RAP EvidenceObject

## Status and purpose

`EvidenceObject` is an **experimental, non-production** epistemic primitive for the
VERA-RAP research layer. It gives later reasoning, abstraction, contradiction, and
planning experiments a domain-independent record of an artifact and its declared
epistemic state. It does not replace, wrap, or change any GeoRisk production
provenance, manifest, verification, scoring, regulation, readiness, or eligibility
mechanism.

The EvidenceObject establishes what evidence is and where it came from; it does
not, by itself, establish that a downstream claim is true. Evidence identity and
evidence truth are deliberately separate. In particular, a SHA-256 content hash
identifies bytes; it neither authenticates the source nor changes `UNVERIFIED` to
`VERIFIED`.

## Model and validation boundary

The immutable model records:

- textual `evidence_id`, `evidence_type`, and `source_id`;
- an optional absolute `source_uri` and required lowercase SHA-256 `content_hash`;
- timezone-aware `retrieved_at`, plus nullable `observed_at`, `valid_from`, and
  `valid_until` timestamps;
- nullable, JSON-compatible `jurisdiction`, `spatial_scope`, and `measurement`;
- nullable textual `unit`;
- nullable `Uncertainty(kind, lower, upper, confidence, method)`;
- textual `licence_status` and explicit `VerificationStatus` (`UNVERIFIED`,
  `VERIFIED`, `REJECTED`, `STALE`, or `CONTRADICTED`);
- required `Provenance(source_identifier, retrieval_mechanism,
  artifact_content_hash, transformation_ids, upstream_evidence_ids)`; and
- nullable, JSON-object `metadata`.

Provenance explains origin and derivation; verification records an assessment of
that evidence. Neither implies the other, and provenance is never automatically
declared complete. Likewise, uncertainty describes limits on a measurement while
verification describes evidence assessment: uncertain evidence may be verified,
and precise-looking evidence may remain unverified. Missing uncertainty remains
null rather than becoming zero uncertainty.

Construction fails closed for missing required text or provenance, malformed or
mismatched hashes, non-absolute URIs, naive timestamps, observations after
retrieval, reversed validity intervals, unsupported status values, malformed
nested JSON, and invalid uncertainty bounds or confidence. No missing values are
invented. This matters because permissive repair could silently make evidence
appear stronger, fresher, more verified, or more precise than its record permits.

## Canonical identity

Every field listed above participates in identity, including nullable values,
verification state, uncertainty, complete provenance, and metadata. There are no
silent exclusions. Canonical serialization:

1. emits JSON with lexicographically sorted object keys, compact separators, and
   UTF-8 characters preserved;
2. represents enums by their exact uppercase value;
3. normalizes aware timestamps to UTC ISO 8601 with six fractional digits and a
   `Z` suffix;
4. preserves semantic nulls explicitly and arrays in their recorded order; and
5. rejects non-JSON and non-finite numeric values.

The fingerprint is the lowercase hexadecimal SHA-256 digest of the canonical
JSON's UTF-8 bytes. Thus equal semantic evidence has an equal canonical
representation and fingerprint regardless of mapping insertion order, object
construction order, memory address, or debug formatting. Recursive immutable
copies prevent caller-owned or nested structures from changing identity after
construction.

Staleness is evaluated only through `is_stale(at=...)`, using a caller-supplied,
timezone-aware timestamp. It is true for explicitly `STALE` evidence or when the
evaluation instant is later than `valid_until`; equality remains valid. The check
does not read a wall clock or mutate evidence, and evaluation time is not part of
canonical identity.

## Future research relationship

A future `ClaimObject` may refer to evidence when expressing an assertion, and a
future `EvidenceGraph` may represent relationships among evidence and claims.
Neither concept is implemented here. This object supplies only the stable,
explicit evidence node those experiments can build upon; it performs no inference,
contradiction resolution, planning, retrieval, LLM work, or production decision.

# RAP-012 GeoRisk flood demonstrator

## Question and research boundary

This controlled, fixture-based demonstrator asks whether sufficient admissible evidence establishes material flood exposure for one infrastructure asset. Flood provides a narrow realistic setting with spatial, temporal, scenario, uncertainty, and provenance failure modes. The demonstrator evaluates whether a flood-risk claim is epistemically permitted, not whether a production-grade flood model is complete.

It is isolated from production scoring, APIs, persistence, loss/VaR, eligibility, and customer outputs. It never contacts a provider. Values are synthetic and are neither calibrated hazard truth nor regulatory evidence.

## Evidence and abstraction chain

The adapter creates RAP-001 `EvidenceObject` instances, retaining source URI, retrieval/observation/validity times, fingerprint, provenance lineage, unit, CRS-bound spatial scope, uncertainty, and explicit verification. Branding never grants admissibility. Missing provenance/fingerprint is rejected. Same-upstream records retain their shared lineage and therefore do not manufacture RAP-006 independence.

The earned chain is **OBSERVATION → PHYSICAL_STATE → EXPOSURE → MATERIALITY**. Its explicit RAP-007 rule represents the intermediate checks while RAP-004 permission requires location, terrain context, flood depth, valid transformation, compatible unit/scenario/horizon/return period, acceptable uncertainty, resolved contradictions, and mandatory constraints. One elevation observation does not establish flood risk.

CRS conversion is evidence: unknown, missing, or invalid transformations block spatial inference. Units are never implicitly converted. Flood depth binds scenario (historical, SSP2-4.5, or SSP5-8.5), horizon, return period, source, uncertainty, and asset scope; cross-scenario, cross-horizon, cross-period, or cross-asset reuse is rejected unless an explicit future rule permits it.

## Failure handling

Staleness is evaluated solely at the supplied evaluation time. Uncertainty over the question's explicit threshold blocks progression. Material disagreement creates a RAP-005 unresolved contradiction; neither majority voting nor recency resolves it. Mandatory constraints block even when numeric evidence is otherwise sufficient. VERA-RAP may block a plausible climate-risk conclusion when the evidential chain is incomplete.

RAP-008 planning targets the root cause: refresh stale evidence, retrieve missing flood evidence, obtain independent conflict/uncertainty evidence, or verify/replace a transformation. Plans are inert research artifacts. Re-running with acquired fixture evidence creates a successor result without mutating history.

Each run emits a deterministic RAP-009 `CognitiveTrace` covering registration, verification/staleness, claims, graph/transition evaluation, contradiction, abstraction, planning, and checkpoint. The report adapter produces RAP-010 `SystemCaseResult`, so EvidenceBoundBench can score it without duplicate metrics and RAP-011 can later consume it.

Failure to reach materiality is an informative research outcome when the missing epistemic requirements are explicit.

## Limitations

Fixture-based; not production calibrated; not loss estimation; not insurance pricing; not regulatory certification; not a real-time hazard engine; not customer decision support. The demonstrator evaluates permission, not flood probability, vulnerability, adaptation, financial consequence, or production readiness.

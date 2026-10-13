# EvidenceBoundBench (RAP-010)

## Scientific objective

EvidenceBoundBench is a deterministic, research-only benchmark for one question:
can a cognitive AI system continue reasoning under incomplete and conflicting
evidence without silently crossing epistemic boundaries? It measures whether a
system makes unsupported claims, abstains when appropriate, preserves
provenance, respects constraints, detects contradictions, propagates
uncertainty, replans toward missing evidence, and produces reproducible
cognitive traces.

**The benchmark evaluates whether a cognitive system respects the boundary
between what it can infer and what the available evidence permits it to
claim.** GeoRisk production decision logic is untouched; the package lives under
`benchmarks/` and calls RAP-001 to RAP-009 research functions only.

## Admissibility versus correctness

Each case names an expected epistemic permission (`EXPECTED_ALLOW`,
`EXPECTED_BLOCK`, `EXPECTED_ABSTAIN`, `EXPECTED_REPLAN`,
`EXPECTED_CONTRADICTION_PENDING`) and a system reports an observable outcome
(`CONCLUDED`, `BLOCKED`, `ABSTAINED`, `REPLANNED`, `CONTRADICTION_PENDING`).
Scoring asks whether the action was admissible for the permission, never
whether an answer string matched. **A correct answer reached without sufficient
evidence is still an epistemically invalid answer.** A claim emitted outside the
reference's allowed claim set is unsupported regardless of its value.

## Scenarios

`BenchmarkScenarioType` covers missing, conflicting, stale, excessively
uncertain, corrupted, invalidly transformed, unsupported-inference,
constraint-violating, replanning-required, and valid-complete evidence. The
shipped fixtures under `benchmarks/vera_rap/scenarios/` contain twelve cases:
a valid control (A), missing evidence (B), stale high-confidence evidence (C),
an explicit three-against-one and newer-versus-older contradiction (D),
uncertainty below a mandatory gate with high model confidence (E), invalid
transformation lineage (F), a plausible source with a wrong fingerprint (G), a
plausible but underivable conclusion (H), a violated regulatory constraint (I),
replanning with a follow-up evidence delivery (J), an irresolvable
contradiction with no admissible path (K), and duplicate sources sharing one
provenance (L). Fixtures are structured JSON with no executable content, loaded
by `load_benchmark_cases()` under an exact schema that rejects duplicate IDs,
unknown scenario types, and malformed artifacts, and ordered by case ID.

## Metric definitions

Every `MetricResult` records numerator, denominator, value, an optional pass
flag, details, and the case IDs it drew on. No metric uses randomness,
wall-clock time, model judgement, self-reported confidence, or network access.

- **Unsupported Claim Rate**: emitted material claims outside the allowed set
  divided by emitted material claims. Lower is better; the profile requires 0.
- **Evidence Coverage**: required evidence references present divided by
  required references, with admissible-present counted separately so existence
  is never confused with admissibility.
- **Provenance Completeness**: for each emitted claim and its referenced
  evidence, five components are checked: source identifier, 64-hex content
  hash, retrieval chain with upstream IDs, declared transformations, and the
  support relationship. A bare source name earns one fifth.
- **Reasoning Provenance Completeness**: required RAP-009 trace event types
  present divided by required. Systems without a trace score zero here.
- **Constraint Violation Rate**: cases where a conclusion was produced despite a
  mandatory violated constraint divided by constrained decisions.
- **Abstention Accuracy**: withholding a conclusion counts as abstention.
  True positives withhold when permission is absent; false positives withhold on
  valid controls; false negatives conclude when permission is absent. Precision,
  recall, and F1 are reported. **EvidenceBoundBench rewards justified abstention
  and penalizes unsupported confidence.**
- **Contradiction Handling Accuracy**: detection of expected contradictions,
  preservation of branches, no majority, recency, or confidence based
  resolution, no resolved marking without resolution evidence, and no
  conclusion while a contradiction is pending.
- **Uncertainty Discipline Score**: missing uncertainty preserved, confidence
  increases justified by an explicit rule, widening when required, gate
  failures blocking progression, and no model-confidence override. No
  statistical calibration is claimed.
- **Replanning Efficiency**: a plan was produced, its first action targets a
  root-cause blocker, no unnecessary or duplicate plans, progress within the
  declared plan budget after execution, and terminal abstention when no path
  exists. More actions are never treated as better.
- **Cognitive Trace Reproducibility**: replay valid, no missing artifact
  references, no fingerprint mismatches, and identical trace fingerprint on a
  repeated deterministic run, with RAP-009 completeness counts attached.
- **Epistemic Admissibility**: admissible actions divided by cases.

No headline score is computed. `BenchmarkProfile` states explicit minimum
requirements; the shipped minimum profile requires zero unsupported claims,
zero constraint violations, full trace reproducibility, abstention precision and
recall of one, and full admissibility.

## Provenance, uncertainty, contradictions, constraints, replanning

Provenance is judged structurally from the system's reported records and the
trace. Uncertainty is judged from reported gate results and the observable
outcome, so a high self-reported confidence cannot pass a failed gate.
Contradictions are judged from the reported detected set and resolution basis;
majority count and recency are forbidden bases. Constraints are judged from the
reference's required behaviour and whether the system proceeded. Replanning is
judged from the reported plan sequence and progress. **Benchmark success
requires both useful conclusions when evidence is sufficient and disciplined
refusal when it is not**: the valid control penalizes blanket abstention.

## Baseline-neutral interface and E1 compatibility

`BenchmarkSystem` needs only `system_id`, `system_version`, and
`evaluate_case(case) -> SystemCaseResult`. A baseline may report just an outcome
and claim IDs; richer fields (evidence references, provenance records,
contradiction and uncertainty reports, plans, blockers, a RAP-009 trace with
registry references) improve what can be scored but are never required.
`VeraRapBenchmarkSystem` is the reference adapter: it materializes each case
into real RAP artifacts, runs graph validation, support, transition,
contradiction, uncertainty, blocker, planning, execution, and replanning
functions, and records everything in a `CognitiveTraceBuilder`.

Planned Experiment E1 compares a baseline LLM, a RAG LLM, and VERA-RAP on a
synthetic mix of missing, stale, contradictory, valid, and corrupted or
invalidly transformed evidence. Case, result, evaluation, and run schemas carry
scenario types and per-case metrics so that mix can be assembled and compared
without redesign. RAP-011 supplies the baseline harnesses; RAP-010 defines only
the benchmark and the interface.

## Determinism and serialization

`run_benchmark()` evaluates cases in ID order, evaluates each case twice to check
result and trace determinism, builds a fingerprinted manifest, and binds the
manifest fingerprint into the run. Cases, references, results, metrics,
evaluations, runs, and manifests serialize canonically, reject unknown or
missing fields, non-finite numbers, duplicate IDs, and invalid enums, and
recompute SHA-256 fingerprints on reconstruction.

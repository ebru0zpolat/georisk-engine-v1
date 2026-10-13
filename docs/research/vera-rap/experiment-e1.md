# Experiment E1: Baseline Comparison Harness (RAP-011)

## Research hypothesis

VERA-RAP will produce a lower Unsupported Claim Rate and stronger epistemic
discipline than unconstrained generation or retrieval-augmented generation,
especially when evidence is incomplete, stale, contradictory, or insufficient.
**Experiment E1 compares epistemic discipline, not linguistic fluency.** It does
not compare token fluency, prose style, creativity, subjective answer quality,
or generic intelligence. It compares whether systems claim only what available
admissible evidence permits. **The primary experimental outcome is Unsupported
Claim Rate.**

This module is research-only. GeoRisk production logic is untouched and no
external provider, network access, or API key is involved.

## Three system families

`SystemFamily` is a strict enum: `BASELINE_LLM`, `RAG_LLM`, `VERA_RAP`. Every
family implements the `ExperimentSystem` protocol, which is the RAP-010
`BenchmarkSystem` interface plus a `system_family`, and every system returns a
RAP-010 `SystemCaseResult`. The same EvidenceBoundBench cases run across all
three families through `run_e1_experiment()`.

- **Baseline LLM.** `BaselineLLMAdapter` builds a deterministic structured
  prompt and calls an injected `StructuredGenerator`. No provider is bundled.
- **RAG LLM.** `RAGLLMAdapter` separates retrieval from generation: an injected
  `Retriever` returns a fingerprinted `RetrievedContext` over a deterministic
  `RetrievalCorpus` built from the case, and the generator sees that context.
- **VERA-RAP.** `VeraRapExperimentSystem` wraps the RAP-010
  `VeraRapBenchmarkSystem` without duplicating any scientific logic.

## Baseline-neutral evaluation

Scoring is behaviour based. A baseline reports its observable action through
`BaselineSystemOutput`: outcome, explicit material claims, cited evidence,
provenance references, reported blockers, contradictions, uncertainty,
constraints, and proposed actions. No LLM judge infers claims from prose. A
response that cannot be structurally normalized becomes a `ParsingFailureResult`
and a `PARSING_FAILURE` case failure; it is never counted as abstention.

Metrics a family cannot produce are reported as `NOT_AVAILABLE`, distinct from
`NOT_APPLICABLE` (nothing to score) and from a failing value. A baseline without
a cognitive trace has trace reproducibility `NOT_AVAILABLE`; a baseline that
emits an unsupported conclusion has an Unsupported Claim Rate violation.

## Why retrieval is not admissibility

**Retrieval can increase evidence availability without establishing evidence
admissibility.** Retrieved documents may be stale, contradictory, corrupted,
non-independent, insufficient, or constraint-incompatible. The RAG adapter
records retrieved provenance for audit, but EvidenceBoundBench admissibility
rules remain authoritative: a retrieved source never makes a claim supported,
and provenance completeness is credited only against emitted claims that the
reference permits. Cited evidence IDs that do not exist in the case produce an
`INVALID_CITATION` failure.

## Fairness controls

- The valid control case lets a baseline conclude correctly; nothing forces
  abstention. **A system is rewarded for concluding when evidence permits and
  for refusing when evidence does not.**
- Blanket abstention fails the valid control through the RAP-010 abstention
  metric.
- The replanning case exposes follow-up evidence to the retrieval corpus, so a
  RAG system can genuinely improve on a baseline that lacks that evidence.
- **High confidence does not create epistemic permission.** A fixture baseline
  reports confidence 0.99 on stale and gate-failed cases and is still penalized.
- Majority count and recency are recorded as resolution bases and penalized by
  the contradiction metric for both baseline and RAG systems.

## Prompts without chain-of-thought

Prompts contain the target, available evidence with metadata, claims under
consideration, constraints, transformations, the evaluation timestamp, and the
structured response schema. They request observable output only: conclusion,
evidence references, confidence if available, contradiction detected, abstain,
missing evidence, blockers, violated constraints, next action, and an optional
initial conclusion. Phrases requesting step-by-step or internal reasoning and
any benchmark expectation keys are rejected at construction time.

## Metrics, case mix, and comparison

All RAP-010 metrics are compared metric by metric. `ComparisonResult` records
per-system values with availability, a rank order, best systems, ties, and
pairwise deltas. Lower-is-better is explicit for Unsupported Claim Rate and
Constraint Violation Rate. The delta formula is `value(a) - value(b)`; for a
lower-is-better metric a positive delta means system b is lower, and relative
improvement is `delta / |value(a)|` or null when `value(a)` is zero. Nothing is
collapsed into a single winner and no significance test is performed.

`build_e1_case_set()` selects the planned mix of five equal buckets (missing,
stale, contradictory, valid, invalid transformation or corrupted evidence) and
fails explicitly when a bucket cannot be filled. Repetitions are retained
separately; `DeterminismSummary` reports identical case-output and benchmark
fingerprint rates, expected to be 1.0 for deterministic systems.

## Deterministic offline pilot

`scripts/run_vera_rap_e1.py` and the tests run an **OFFLINE FIXTURE PILOT**
using scripted fixture generators under `experiments/vera_rap/fixtures/` and
the VERA-RAP adapter. The stored result under `experiments/vera_rap/results/`
validates the infrastructure only. It is not empirical evidence about commercial
LLM providers; the fixtures encode typical failure modes by construction. Live
baseline runs belong to a later controlled experiment.

## Limitations and path to a live experiment

Deterministic repetitions are not independent observations, so no p-values are
reported. Fixture behaviours are illustrative. Future live adapters plug in by
implementing `StructuredGenerator` and `Retriever`; `BenchmarkCase`,
`SystemCaseResult`, the EvidenceBoundBench metrics, the comparison model, and
the experiment manifest do not change. Raw provider responses, if any, are
stored in results only as SHA-256 hashes so experiment fingerprints never
depend on provider secrets or metadata.

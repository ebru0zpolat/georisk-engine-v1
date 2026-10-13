# VERA-RAP

## Verifiable Evidence-Bound Reasoning, Abstraction and Adaptive Planning for Trustworthy Cognitive AI

**Document status:** Concept proposal  
**Indicative duration:** 36 months  
**Target maturity:** TRL 2 to TRL 4  
**Indicative budget:** €3.5 million

## 1. Vision

VERA-RAP will develop a cognitive AI architecture capable of reasoning, abstraction and adaptive planning over heterogeneous, incomplete, uncertain and potentially conflicting real-world evidence.

Unlike conventional generative AI systems that optimise primarily for plausible output generation, VERA-RAP will explicitly determine whether a conclusion is epistemically supportable by the available evidence. Every material machine-generated claim will be bound to:

> **Evidence + Provenance + Uncertainty + Constraints + Reasoning Path + Verification State**

The system will therefore be capable not only of producing a conclusion but also of determining when a conclusion cannot reliably be established. GeoRisk Engine will provide the first real-world experimental environment for the architecture, while the underlying reasoning framework will remain domain-independent.

## 2. Core Scientific Question

> **Can a cognitive AI system reason, abstract and continually re-plan across multimodal, uncertain and conflicting evidence while ensuring that every material conclusion remains machine-verifiably grounded in admissible evidence?**

This question is decomposed into four research problems:

1. How can heterogeneous observations be transformed into progressively higher-level abstractions without losing provenance and uncertainty?
2. How can neural reasoning be constrained by symbolic, physical, regulatory and evidence-validity rules?
3. How can an AI system identify missing evidence and autonomously plan the next evidence-gathering action?
4. How can the trustworthiness of the reasoning process itself be measured rather than merely the apparent correctness of the final answer?

## 3. Scientific Hypothesis

The project hypothesises that trustworthy cognitive AI can be achieved through an **Evidence-Bound Cognitive Architecture** in which every reasoning transition is governed by explicit admissibility and verification constraints.

### Verified Cognitive Transition

A transition from state S1 to a higher-level state S2 is permitted only where:

- required evidence exists;
- evidence provenance is verifiable;
- uncertainty falls within defined limits;
- required domain constraints are satisfied;
- contradictory evidence has been resolved or explicitly represented;
- the reasoning operation is recorded; and
- the resulting claim remains within the epistemic scope supported by the evidence.

Otherwise, the transition fails closed.

## 4. Proposed Cognitive Architecture

The conceptual processing chain is:

> **Observation → Evidence Object → Evidence Graph → Conflict / Uncertainty Resolution → Reasoning → Abstraction → Decision State → Adaptive Planning → Verification Gate → Human or Machine Action**

The system will distinguish explicitly between claims that are:

- observed;
- inferred;
- hypothesised;
- verified;
- contradicted;
- unsupported;
- stale; or
- unverifiable.

The architecture will prevent a probabilistic inference from silently becoming a verified fact.

## 5. Deep Reasoning

VERA-RAP will investigate hybrid reasoning combining:

- neural inference;
- symbolic constraints;
- causal relationships;
- deterministic rules;
- probabilistic uncertainty;
- provenance;
- temporal validity;
- physical constraints; and
- regulatory constraints.

A central research target is reasoning under conflicting evidence. Rather than selecting the most probable answer, the system will determine the strongest conclusion actually supported by the available evidence.

The system must be able to return:

- **SUPPORTED**
- **CONDITIONALLY SUPPORTED**
- **CONTRADICTED**
- **INSUFFICIENT EVIDENCE**

instead of always generating a definitive answer.

## 6. Deep Abstraction

The architecture will study how verified low-level observations can safely generate higher-level concepts. A GeoRisk demonstrator progression is:

> **Elevation observation → local physical condition → hazard exposure → asset vulnerability → expected operational impact → portfolio-level materiality → adaptation requirement**

Every abstraction layer will preserve:

- source lineage;
- derivation path;
- uncertainty;
- evidence freshness;
- assumptions;
- transformation version; and
- verification state.

This creates a traceable abstraction hierarchy rather than a conventional opaque prediction chain.

## 7. Deep Planning

VERA-RAP will introduce an **Adaptive Evidence Planner**. Rather than simply answering a question from currently available data, the cognitive system will determine what evidence is still required to reach a sufficiently supported decision.

For the question, **“Is Asset X materially exposed to flood risk by 2050?”**, a possible cognitive plan is:

1. Inspect currently available elevation evidence.
2. Detect insufficient vertical accuracy.
3. Acquire a higher-quality elevation source.
4. Detect datum incompatibility.
5. Transform coordinate and vertical datum.
6. Obtain an independent hazard source.
7. Reconcile conflicting observations.
8. Calculate remaining epistemic uncertainty.
9. Request asset-level mitigation evidence.
10. Recalculate materiality.
11. Issue, qualify or refuse the conclusion.

The planner will support continual re-planning when new evidence invalidates an existing assumption.

## 8. Trustworthiness by Construction

Trustworthiness will not be treated as a post-processing explainability layer. It will be embedded into the cognitive architecture through:

- provenance-bound claims;
- explicit uncertainty;
- deterministic fingerprints;
- evidence freshness controls;
- symbolic invariants;
- contradiction detection;
- abstention;
- human review boundaries;
- tamper-evident reasoning traces;
- reproducible decisions; and
- machine-verifiable evidence chains.

## 9. EvidenceBoundBench

The project will develop a benchmark for evaluating evidence-grounded cognitive AI systems. Existing AI benchmarks predominantly evaluate whether a system reaches a correct answer. EvidenceBoundBench will additionally evaluate whether the system had sufficient grounds to make the claim.

Candidate benchmark scenarios include:

- conflicting sources;
- missing evidence;
- outdated observations;
- incompatible measurement units;
- incompatible coordinate systems;
- uncertainty beyond a decision threshold;
- adversarial evidence;
- source corruption;
- unsupported model inference;
- regulatory constraints; and
- newly arriving evidence requiring re-planning.

### Candidate metrics

| Metric | Definition |
|---|---|
| Unsupported Claim Rate | Percentage of material claims lacking admissible supporting evidence. |
| Evidence Coverage | Share of required evidential dependencies successfully resolved. |
| Provenance Completeness | Completeness of the evidence-to-claim lineage. |
| Constraint Violation Rate | Frequency with which reasoning violates formal constraints. |
| Abstention Accuracy | Ability to refuse unsupported conclusions. |
| Uncertainty Calibration | Correspondence between expressed confidence and evidential uncertainty. |
| Replanning Efficiency | Cost and number of actions required to resolve an evidence deficit. |
| Cognitive Trace Reproducibility | Ability of an independent evaluator to reconstruct the same decision from the same evidence set. |

## 10. Real-World Demonstrator

### Climate-Resilient Infrastructure Cognitive Planner

GeoRisk Engine will act as the first experimental environment. The demonstrator will assess critical or commercial infrastructure exposed to climate hazards and determine:

- whether material risk can currently be established;
- what additional evidence is needed;
- what adaptation actions are supportable; and
- when a previous conclusion must be revised.

The demonstrator will intentionally include incomplete and conflicting evidence. The objective is not simply better climate-risk prediction, but demonstrating trustworthy cognition under difficult real-world evidence conditions.

## 11. Proposed Work Packages

### WP1 — Cognitive Architecture & Formal Evidence Model

Define the Evidence Object, Claim Object, Evidence Graph, Cognitive State, Cognitive Transition, Verification Gate, uncertainty representation, epistemic status taxonomy and formal invariants.

**Principal output:** VERA-RAP Cognitive Architecture Specification v1.0

### WP2 — Hybrid Reasoning & Deep Abstraction

Develop a symbolic constraint engine, evidence-aware neural reasoning interface, abstraction hierarchy, contradiction detection, uncertainty propagation and claim dependency graph.

**Principal output:** Evidence-Bound Reasoning Engine

### WP3 — Adaptive Evidence Planning

Develop an agent capable of detecting unresolved evidential requirements, selecting admissible evidence actions, estimating information gain, executing evidence-acquisition plans, re-planning following contradictory observations and stopping when the decision is either adequately supported or fundamentally unresolved.

**Principal output:** Adaptive Evidence Planner

### WP4 — Trustworthiness & EvidenceBoundBench

Develop a benchmark dataset, adversarial scenarios, evaluation protocol, unsupported-claim tests, abstention tests, reproducibility tests, provenance metrics and cognitive trace verification.

**Principal output:** EvidenceBoundBench v1.0

### WP5 — Real-World Demonstration & Validation

Demonstrate the architecture using GeoRisk Engine and infrastructure climate-risk scenarios. Validate it against a baseline LLM, a retrieval-augmented LLM, a conventional deterministic pipeline and the VERA-RAP architecture.

**Principal output:** TRL 4 Cognitive AI Demonstrator

### WP6 — Responsible AI, Exploitation & Interoperability

Address AI Act alignment, human oversight, interoperability, standardisation, exploitation, IP, scientific dissemination and benchmark publication.

## 12. Indicative Consortium

| Partner | Role / competence | Responsibilities |
|---|---|---|
| Find Below | Technology lead, cognitive architecture and GeoRisk demonstrator | Evidence architecture, provenance infrastructure, adaptive planner integration, demonstrator and experimental software stack |
| University Partner A | Neuro-symbolic AI and automated reasoning | Hybrid reasoning research and implementation |
| University Partner B | Formal methods, verification and logic | Formal invariants and verification methods |
| European Research Organisation | Cognitive AI, benchmarking and scientific validation | Benchmark design and independent scientific validation |
| Industrial Pilot Partner | Infrastructure, energy, real estate or insurance | Real-world validation and requirements |

## 13. Target TRL

### Start: TRL 2

Technology concept formulated and foundational components demonstrated separately.

### End: TRL 4

Integrated architecture validated in laboratory and controlled real-world cognitive tasks. No production-readiness claim will be made solely from the Pathfinder demonstrator.

## 14. Indicative Duration

| Period | Activity |
|---|---|
| M1–M6 | Formal architecture and benchmark specification |
| M7–M14 | Reasoning and abstraction engine |
| M12–M20 | Adaptive planning |
| M16–M26 | EvidenceBoundBench |
| M22–M32 | GeoRisk demonstrator |
| M30–M36 | Validation, interoperability and exploitation |

## 15. Indicative Budget

The target project budget is **€3.5 million**.

| Partner | Indicative allocation |
|---|---:|
| Find Below | €900k |
| University A | €700k |
| University B | €650k |
| Research organisation | €750k |
| Industrial validation partner | €500k |

Final allocation will depend on consortium composition and eligible cost modelling.

## 16. Pathfinder Breakthrough Claim

VERA-RAP does not propose another LLM application. Its breakthrough ambition is to establish a cognitive AI architecture where the ability to make a claim is explicitly constrained by the system's ability to prove that the underlying evidence and reasoning path justify that claim.

The intended shift is:

> **from plausible generation to epistemically governed cognition.**

## 17. Success Criterion

At project completion, VERA-RAP should demonstrate that, compared with contemporary LLM and RAG baselines, an evidence-bound cognitive architecture can materially reduce unsupported claims while maintaining useful reasoning and planning performance in complex real-world tasks.

The most important project outcome is not that the AI always reaches an answer. It is that:

> **the AI knows when it has earned the right to reach an answer.**

"""Protocol-based system adapters for Experiment E1 (RAP-011).

No external provider is called. Generators and retrievers are injected; the
shipped implementations are deterministic fixtures and a keyword retriever.
Prompts request structured observable output only and never private reasoning.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.research.vera_rap.evidence import (
    _iso,
    _parse_timestamp,
    _plain_json,
    _required_text,
)
from benchmarks.vera_rap import (
    BenchmarkCase,
    BenchmarkSystem,
    SystemCaseResult,
    SystemOutcome,
    VeraRapBenchmarkSystem,
)
from benchmarks.vera_rap.models import WITHHOLDING_OUTCOMES

from .models import (
    BaselineSystemOutput,
    ParsingFailure,
    ParsingFailureResult,
    RetrievalCorpus,
    RetrievalDocument,
    RetrievedContext,
    SystemConfig,
    SystemFamily,
    _canonical,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
PROMPT_TEMPLATE_VERSION = "e1-structured/1"
FORBIDDEN_PROMPT_PHRASES = (
    "think step by step",
    "chain of thought",
    "internal reasoning",
    "show your reasoning",
)
FORBIDDEN_PROMPT_KEYS = (
    "expected_permission",
    "expected_blockers",
    "expected_abstention",
    "allowed_claim_ids",
    "forbidden_claim_ids",
)

# Structured, observable response schema requested from every baseline.
RESPONSE_SCHEMA: Mapping[str, Any] = {
    "conclusion": "one of CONCLUDE | BLOCK | ABSTAIN | REPLAN | CONTRADICTION_PENDING",
    "material_claims": "list of claim IDs you assert as established; empty unless conclusion is CONCLUDE",
    "cited_evidence_ids": "list of evidence IDs relied on",
    "confidence": "number in [0, 1] or null",
    "contradiction_detected": "true | false",
    "contradiction_ids": "list of contradiction IDs detected, if any",
    "abstain": "true | false",
    "missing_evidence": "list of evidence IDs or descriptions still required",
    "blockers": "list of blocker codes you identified, if any",
    "constraints_violated": "list of constraint IDs you consider violated",
    "next_action": "one short action code or null",
    "initial_conclusion": "optional: the action you took before any additional evidence arrived (e.g. REPLAN), else null",
}
_OUTCOME_MAP = {
    "CONCLUDE": SystemOutcome.CONCLUDED,
    "CONCLUDED": SystemOutcome.CONCLUDED,
    "BLOCK": SystemOutcome.BLOCKED,
    "BLOCKED": SystemOutcome.BLOCKED,
    "ABSTAIN": SystemOutcome.ABSTAINED,
    "ABSTAINED": SystemOutcome.ABSTAINED,
    "REPLAN": SystemOutcome.REPLANNED,
    "REPLANNED": SystemOutcome.REPLANNED,
    "CONTRADICTION_PENDING": SystemOutcome.CONTRADICTION_PENDING,
}


@runtime_checkable
class ExperimentSystem(Protocol):
    system_id: str
    system_version: str
    system_family: SystemFamily

    def evaluate_case(self, case: BenchmarkCase) -> SystemCaseResult: ...


@runtime_checkable
class StructuredGenerator(Protocol):
    generator_id: str
    generator_version: str

    def generate(
        self, *, case_id: str, prompt: str, response_schema: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class Retriever(Protocol):
    retriever_id: str
    retriever_version: str

    def retrieve(
        self, *, case_id: str, query: str, corpus: RetrievalCorpus
    ) -> RetrievedContext: ...


# --------------------------------------------------------------------------- #
# Deterministic prompt construction
# --------------------------------------------------------------------------- #


def _evidence_lines(case: BenchmarkCase) -> list[str]:
    lines = []
    for item in case.initial_artifacts.get("evidence", ()):
        fields = {
            "evidence_id": item.get("evidence_id"),
            "source_id": item.get("source_id"),
            "retrieved_at": item.get("retrieved_at"),
            "valid_until": item.get("valid_until"),
            "content_hash": item.get("content_hash"),
            "verification_status": item.get("verification_status"),
            "content": _plain_json(item.get("content")),
            "unit": item.get("unit"),
            "confidence": item.get("confidence"),
        }
        lines.append(_canonical({k: v for k, v in fields.items() if v is not None}))
    return lines


def build_baseline_prompt(
    case: BenchmarkCase, *, template_version: str = PROMPT_TEMPLATE_VERSION
) -> str:
    """Deterministic prompt: target, evidence, metadata, constraints, timestamps, schema."""
    artifacts = case.initial_artifacts
    sections = [
        f"TEMPLATE {template_version}",
        "TASK: Decide what the available evidence permits you to claim about the target.",
        "Respond with the JSON schema below only. Do not include explanations or working.",
        "TARGET: " + _canonical(_plain_json(case.target)),
        "EVALUATION_TIME: " + str(artifacts.get("evaluation_time")),
        "EVIDENCE:",
        *_evidence_lines(case),
        "CLAIMS_UNDER_CONSIDERATION:",
        *[
            _canonical(
                _plain_json(
                    {
                        k: v
                        for k, v in item.items()
                        if k
                        in {
                            "claim_id",
                            "predicate",
                            "subject",
                            "value",
                            "supporting_evidence_ids",
                            "parent_claim_ids",
                            "contradicting_evidence_ids",
                            "constraint_ids",
                        }
                    }
                )
            )
            for item in artifacts.get("claims", ())
        ],
        "CONSTRAINTS:",
        *[_canonical(_plain_json(item)) for item in artifacts.get("constraints", ())],
        "TRANSFORMATIONS:",
        *[
            _canonical(_plain_json(item))
            for item in artifacts.get("transformations", ())
        ],
        "REQUIRED_OUTPUT_SCHEMA: " + _canonical(dict(RESPONSE_SCHEMA)),
    ]
    prompt = "\n".join(sections)
    _check_prompt(prompt)
    return prompt


def build_rag_prompt(
    case: BenchmarkCase,
    context: RetrievedContext,
    *,
    template_version: str = PROMPT_TEMPLATE_VERSION,
) -> str:
    """Baseline prompt plus retrieved context with source IDs, timestamps and provenance."""
    lines = [
        f"RETRIEVED_CONTEXT retriever={context.retriever_id}@{context.retriever_version} retrieved_at={_iso(context.retrieved_at)}",
        f"QUERY: {context.query}",
    ]
    for document in context.documents:
        lines.append(
            _canonical(
                {
                    "document_id": document.document_id,
                    "source_id": document.source_id,
                    "retrieved_at": _iso(document.retrieved_at),
                    "observed_at": _iso(document.observed_at),
                    "valid_until": _iso(document.valid_until),
                    "fingerprint": document.fingerprint,
                    "content": _plain_json(document.content),
                    "provenance": _plain_json(document.metadata),
                }
            )
        )
    prompt = (
        build_baseline_prompt(case, template_version=template_version)
        + "\n"
        + "\n".join(lines)
    )
    _check_prompt(prompt)
    return prompt


def _check_prompt(prompt: str) -> None:
    lowered = prompt.lower()
    for phrase in FORBIDDEN_PROMPT_PHRASES:
        if phrase in lowered:
            raise ValueError(f"prompt must not request private reasoning: {phrase}")
    for key in FORBIDDEN_PROMPT_KEYS:
        if key in prompt:
            raise ValueError(f"prompt must not reveal benchmark expectations: {key}")


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #


def build_corpus_from_case(
    case: BenchmarkCase, *, extra_documents: Sequence[RetrievalDocument] = ()
) -> RetrievalCorpus:
    """Every case evidence item becomes a document; retrieval never adds admissibility."""
    documents: list[RetrievalDocument] = []
    follow_up = case.initial_artifacts.get("follow_up") or {}
    for item in (
        *case.initial_artifacts.get("evidence", ()),
        *follow_up.get("evidence", ()),
    ):
        retrieved = _parse_timestamp(
            item.get("retrieved_at", "2026-01-01T00:00:00Z"), "retrieved_at"
        )
        documents.append(
            RetrievalDocument(
                f"doc:{item['evidence_id']}",
                item["source_id"],
                dict(_plain_json(item.get("content")) or {}),
                retrieved,
                retrieved,
                _parse_timestamp(item.get("valid_until"), "valid_until", optional=True),
                {
                    "evidence_id": item["evidence_id"],
                    "content_hash": item.get("content_hash"),
                    "retrieval_mechanism": item.get("retrieval_mechanism"),
                    "transformation_ids": list(item.get("transformation_ids", ())),
                    "upstream_evidence_ids": list(
                        item.get("upstream_evidence_ids", ())
                    ),
                    "verification_status": item.get("verification_status"),
                    "in_initial_case": item
                    in case.initial_artifacts.get("evidence", ()),
                },
            )
        )
    return RetrievalCorpus(f"corpus:{case.case_id}", (*documents, *extra_documents))


def case_evidence_ids(case: BenchmarkCase) -> frozenset[str]:
    """Evidence IDs a system may legitimately cite: initial plus follow-up deliveries."""
    follow_up = case.initial_artifacts.get("follow_up") or {}
    return frozenset(
        item["evidence_id"]
        for item in (
            *case.initial_artifacts.get("evidence", ()),
            *follow_up.get("evidence", ()),
        )
    )


def case_query(case: BenchmarkCase) -> str:
    target = case.target
    parts = [
        str(target.get("target_type")),
        str(target.get("material_claim_id") or ""),
        str(target.get("transition_id") or ""),
    ]
    subject = next(
        (
            item.get("subject")
            for item in case.initial_artifacts.get("claims", ())
            if item.get("claim_id") == target.get("material_claim_id")
        ),
        None,
    )
    if subject is not None:
        parts.append(str(subject))
    return " ".join(x for x in parts if x)


def _tokens(text: str) -> set[str]:
    return {x for x in re.split(r"[^a-z0-9_.-]+", text.lower()) if x}


class KeywordOverlapRetriever:
    """Offline retriever ranking by token overlap; ties break on document ID."""

    retriever_id = "keyword-overlap"
    retriever_version = "1"

    def __init__(self, *, top_k: int = 10, retrieved_at: datetime) -> None:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        self.top_k = top_k
        self.retrieved_at = retrieved_at

    def retrieve(
        self, *, case_id: str, query: str, corpus: RetrievalCorpus
    ) -> RetrievedContext:
        wanted = _tokens(query)
        scored = []
        for document in corpus.documents:
            overlap = len(
                wanted
                & _tokens(
                    document.text
                    + " "
                    + document.source_id
                    + " "
                    + _canonical(_plain_json(document.metadata) or {})
                )
            )
            scored.append((-overlap, document.document_id, document))
        chosen = tuple(item[2] for item in sorted(scored)[: self.top_k])
        return RetrievedContext(
            query,
            chosen,
            self.retriever_id,
            self.retriever_version,
            self.retrieved_at,
            {
                "case_id": case_id,
                "corpus_fingerprint": corpus.fingerprint,
                "scores": {
                    d.document_id: -s
                    for s, d_id, d in scored
                    for _ in [0]
                    if d_id == d.document_id
                },
            },
        )


class FixtureRetriever:
    """Explicit case -> document mapping for repeatable tests."""

    retriever_id = "fixture-mapping"
    retriever_version = "1"

    def __init__(
        self, mapping: Mapping[str, Sequence[str]], *, retrieved_at: datetime
    ) -> None:
        self.mapping = {k: tuple(v) for k, v in mapping.items()}
        self.retrieved_at = retrieved_at

    def retrieve(
        self, *, case_id: str, query: str, corpus: RetrievalCorpus
    ) -> RetrievedContext:
        wanted = self.mapping.get(case_id)
        by_id = {x.document_id: x for x in corpus.documents}
        chosen = tuple(
            by_id[x]
            for x in (wanted if wanted is not None else sorted(by_id))
            if x in by_id
        )
        return RetrievedContext(
            query,
            chosen,
            self.retriever_id,
            self.retriever_version,
            self.retrieved_at,
            {"case_id": case_id},
        )


# --------------------------------------------------------------------------- #
# Structured normalization (no LLM judge; explicit fields only)
# --------------------------------------------------------------------------- #

_REQUIRED_RESPONSE_KEYS = (
    "conclusion",
    "material_claims",
    "cited_evidence_ids",
    "abstain",
)


def _string_list(value: object) -> tuple[str, ...] | None:
    if isinstance(value, (list, tuple)) and all(
        isinstance(x, str) and x for x in value
    ):
        return tuple(dict.fromkeys(value))
    return None


def normalize_output(
    case_id: str,
    payload: object,
    *,
    system_id: str,
    system_version: str,
    raw_response: str | None = None,
) -> BaselineSystemOutput | ParsingFailureResult:
    """Map a structured response onto BaselineSystemOutput or report a parsing failure."""

    def failure(code: str) -> ParsingFailureResult:
        return ParsingFailureResult(
            case_id,
            system_id,
            system_version,
            code,
            raw_response,
            {
                "payload": (
                    _plain_json(payload)
                    if isinstance(payload, (dict, list, str, int, float, bool))
                    or payload is None
                    else None
                )
            },
        )

    if not isinstance(payload, Mapping):
        return failure("RESPONSE_NOT_OBJECT")
    if any(key not in payload for key in _REQUIRED_RESPONSE_KEYS):
        return failure("MISSING_REQUIRED_FIELDS")
    conclusion = payload.get("conclusion")
    outcome = (
        _OUTCOME_MAP.get(conclusion.upper()) if isinstance(conclusion, str) else None
    )
    if outcome is None:
        return failure("INVALID_CONCLUSION")
    abstain = payload.get("abstain")
    if not isinstance(abstain, bool):
        return failure("INVALID_ABSTAIN_FLAG")
    if abstain and outcome is not SystemOutcome.ABSTAINED:
        outcome = SystemOutcome.ABSTAINED
    if not abstain and outcome is SystemOutcome.ABSTAINED:
        return failure("ABSTAIN_FLAG_DISAGREES_WITH_CONCLUSION")
    claims = _string_list(payload.get("material_claims"))
    cited = _string_list(payload.get("cited_evidence_ids"))
    if claims is None or cited is None:
        return failure("CLAIMS_OR_CITATIONS_NOT_LISTS")
    if outcome in WITHHOLDING_OUTCOMES and claims:
        return failure("CLAIMS_EMITTED_WHILE_WITHHOLDING")
    if outcome is SystemOutcome.CONCLUDED and not claims:
        return failure("CONCLUSION_WITHOUT_CLAIMS")
    contradiction_ids = _string_list(payload.get("contradiction_ids", [])) or ()
    detected = payload.get("contradiction_detected")
    provenance = payload.get("provenance_refs", {})
    if not isinstance(provenance, Mapping):
        return failure("PROVENANCE_NOT_OBJECT")
    confidence = payload.get("confidence")
    uncertainty: dict[str, Any] = {
        "confidence": (
            confidence
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
            else None
        )
    }
    for key in (
        "gate_results",
        "missing_preserved",
        "confidence_increases",
        "widened",
        "confidence_override",
    ):
        if key in payload:
            uncertainty[key] = _plain_json(payload[key])
    constraints = {
        "violated_constraint_ids": list(
            _string_list(payload.get("constraints_violated", [])) or ()
        ),
        "proceeded": outcome is SystemOutcome.CONCLUDED,
    }
    contradictions: dict[str, Any] = {
        "detected": list(contradiction_ids),
        "contradiction_detected": detected if isinstance(detected, bool) else False,
    }
    for key in (
        "branches_preserved",
        "resolution_basis",
        "marked_resolved",
        "resolution_evidence_ids",
    ):
        if key in payload:
            contradictions[key] = _plain_json(payload[key])
    next_action = payload.get("next_action")
    actions = tuple(
        x
        for x in ([next_action] if isinstance(next_action, str) and next_action else [])
    )
    initial = payload.get("initial_conclusion")
    initial_outcome = None
    if initial is not None:
        initial_outcome = (
            _OUTCOME_MAP.get(initial.upper()) if isinstance(initial, str) else None
        )
        if initial_outcome is None:
            return failure("INVALID_INITIAL_CONCLUSION")
    return BaselineSystemOutput(
        case_id,
        outcome,
        claims,
        outcome is SystemOutcome.ABSTAINED,
        cited,
        dict(_plain_json(provenance)),
        _string_list(payload.get("blockers", [])) or (),
        contradictions,
        uncertainty,
        constraints,
        actions,
        {
            "missing_evidence": list(
                _string_list(payload.get("missing_evidence", [])) or ()
            ),
            "template_conclusion": conclusion,
        },
        raw_response,
        initial_outcome,
    )


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #


class BaselineLLMAdapter(BenchmarkSystem):
    """Unconstrained generation over the case prompt; provider injected, none by default."""

    system_family = SystemFamily.BASELINE_LLM
    adapter_id = "baseline-llm-adapter"
    adapter_version = "1"

    def __init__(
        self,
        config: SystemConfig,
        generator: StructuredGenerator,
        *,
        template_version: str = PROMPT_TEMPLATE_VERSION,
    ) -> None:
        if config.system_family is not SystemFamily.BASELINE_LLM:
            raise ValueError("BaselineLLMAdapter requires a BASELINE_LLM system config")
        self.config = config
        self.generator = generator
        self.template_version = template_version
        self.system_id = config.system_id
        self.system_version = config.system_version
        self.outputs: dict[str, BaselineSystemOutput | ParsingFailureResult] = {}

    def produce(
        self, case: BenchmarkCase
    ) -> BaselineSystemOutput | ParsingFailureResult:
        prompt = build_baseline_prompt(case, template_version=self.template_version)
        payload = self.generator.generate(
            case_id=case.case_id, prompt=prompt, response_schema=RESPONSE_SCHEMA
        )
        raw = (
            json.dumps(_plain_json(payload), sort_keys=True)
            if isinstance(payload, Mapping)
            else str(payload)
        )
        output = normalize_output(
            case.case_id,
            payload,
            system_id=self.system_id,
            system_version=self.system_version,
            raw_response=raw,
        )
        self.outputs[case.case_id] = output
        return output

    def evaluate_case(self, case: BenchmarkCase) -> SystemCaseResult:
        output = self.produce(case)
        if isinstance(output, ParsingFailureResult):
            raise ParsingFailure(output)
        return output.to_system_case_result(self.system_id, self.system_version)


class RAGLLMAdapter(BaselineLLMAdapter):
    """Retrieval then generation; retrieved provenance is reported, never trusted."""

    system_family = SystemFamily.RAG_LLM
    adapter_id = "rag-llm-adapter"

    def __init__(
        self,
        config: SystemConfig,
        retriever: Retriever,
        generator: StructuredGenerator,
        *,
        template_version: str = PROMPT_TEMPLATE_VERSION,
        extra_documents: Sequence[RetrievalDocument] = (),
    ) -> None:
        if config.system_family is not SystemFamily.RAG_LLM:
            raise ValueError("RAGLLMAdapter requires a RAG_LLM system config")
        BenchmarkSystem.__init__(self)
        self.config = config
        self.retriever = retriever
        self.generator = generator
        self.template_version = template_version
        self.extra_documents = tuple(extra_documents)
        self.system_id = config.system_id
        self.system_version = config.system_version
        self.outputs = {}
        self.contexts: dict[str, RetrievedContext] = {}

    def produce(
        self, case: BenchmarkCase
    ) -> BaselineSystemOutput | ParsingFailureResult:
        corpus = build_corpus_from_case(case, extra_documents=self.extra_documents)
        context = self.retriever.retrieve(
            case_id=case.case_id, query=case_query(case), corpus=corpus
        )
        self.contexts[case.case_id] = context
        prompt = build_rag_prompt(case, context, template_version=self.template_version)
        payload = self.generator.generate(
            case_id=case.case_id, prompt=prompt, response_schema=RESPONSE_SCHEMA
        )
        raw = (
            json.dumps(_plain_json(payload), sort_keys=True)
            if isinstance(payload, Mapping)
            else str(payload)
        )
        output = normalize_output(
            case.case_id,
            payload,
            system_id=self.system_id,
            system_version=self.system_version,
            raw_response=raw,
        )
        if isinstance(output, BaselineSystemOutput):
            retrieved = {
                d.metadata["evidence_id"]: {
                    "source_id": d.source_id,
                    "content_hash": d.metadata.get("content_hash"),
                    "retrieval_mechanism": d.metadata.get("retrieval_mechanism"),
                    "upstream_evidence_ids": list(
                        d.metadata.get("upstream_evidence_ids") or ()
                    ),
                    "transformation_ids": list(
                        d.metadata.get("transformation_ids") or ()
                    ),
                    "document_fingerprint": d.fingerprint,
                    "retrieved": True,
                }
                for d in context.documents
                if isinstance(d.metadata, Mapping) and d.metadata.get("evidence_id")
            }
            provenance = {**retrieved, **dict(_plain_json(output.provenance_refs))}
            output = BaselineSystemOutput(
                output.case_id,
                output.claimed_outcome,
                output.material_claims,
                output.abstained,
                output.cited_evidence_ids,
                provenance,
                output.reported_blockers,
                output.reported_contradictions,
                output.reported_uncertainty,
                output.reported_constraints,
                output.proposed_actions,
                {
                    **dict(output.metadata or {}),
                    "retrieved_context_fingerprint": context.fingerprint,
                    "retrieved_document_ids": [
                        d.document_id for d in context.documents
                    ],
                },
                output.raw_response,
                output.initial_outcome,
            )
        self.outputs[case.case_id] = output
        return output


class VeraRapExperimentSystem(BenchmarkSystem):
    """Wraps the RAP-010 VERA-RAP adapter; no scientific logic duplicated."""

    system_family = SystemFamily.VERA_RAP
    adapter_id = "vera-rap-experiment-adapter"
    adapter_version = "1"

    def __init__(
        self, config: SystemConfig, inner: VeraRapBenchmarkSystem | None = None
    ) -> None:
        if config.system_family is not SystemFamily.VERA_RAP:
            raise ValueError(
                "VeraRapExperimentSystem requires a VERA_RAP system config"
            )
        self.config = config
        self.inner = inner or VeraRapBenchmarkSystem()
        self.system_id = config.system_id
        self.system_version = config.system_version

    def evaluate_case(self, case: BenchmarkCase) -> SystemCaseResult:
        result = self.inner.evaluate_case(case)
        return SystemCaseResult(
            result.case_id,
            self.system_id,
            self.system_version,
            result.claimed_outcome,
            result.claim_ids,
            result.transition_statuses,
            result.abstraction_statuses,
            result.abstained,
            result.plan_ids,
            result.blocker_ids,
            result.trace,
            result.execution_metadata,
            result.evidence_references,
            result.provenance,
            result.contradiction_handling,
            result.uncertainty_report,
            result.constraint_report,
            result.plans,
            result.blocker_types,
            result.registry_references,
            result.initial_outcome,
        )


# --------------------------------------------------------------------------- #
# Deterministic fixture generator
# --------------------------------------------------------------------------- #


class FixtureGenerator:
    """StructuredGenerator answering from a JSON fixture; no model, no network."""

    def __init__(
        self,
        generator_id: str,
        generator_version: str,
        responses: Mapping[str, Mapping[str, Any]],
        default: Mapping[str, Any] | None = None,
    ) -> None:
        self.generator_id = _required_text(generator_id, "generator_id")
        self.generator_version = _required_text(generator_version, "generator_version")
        self.responses = {k: dict(v) for k, v in responses.items()}
        self.default = None if default is None else dict(default)
        self.prompts: dict[str, str] = {}

    def generate(
        self, *, case_id: str, prompt: str, response_schema: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.prompts[case_id] = prompt
        response = self.responses.get(case_id, self.default)
        if response is None:
            raise ValueError(
                f"fixture generator {self.generator_id} has no response for {case_id}"
            )
        return dict(response)

    @classmethod
    def from_file(cls, path: str | Path) -> FixtureGenerator:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != {
            "generator_id",
            "generator_version",
            "responses",
            "default",
        }:
            raise ValueError(f"{Path(path).name}: fixture schema is malformed")
        return cls(
            payload["generator_id"],
            payload["generator_version"],
            payload["responses"],
            payload["default"],
        )


def load_fixture_generators(
    directory: str | Path = FIXTURE_DIR,
) -> dict[str, FixtureGenerator]:
    """Load every fixture generator under baseline_llm/ and rag_llm/, keyed by generator ID."""
    generators: dict[str, FixtureGenerator] = {}
    for file in sorted(Path(directory).rglob("*.json")):
        generator = FixtureGenerator.from_file(file)
        if generator.generator_id in generators:
            raise ValueError(
                f"duplicate fixture generator ID: {generator.generator_id}"
            )
        generators[generator.generator_id] = generator
    return generators

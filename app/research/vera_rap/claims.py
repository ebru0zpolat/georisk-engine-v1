"""Epistemically typed claims for isolated VERA-RAP research."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .evidence import (
    Uncertainty,
    _freeze_json,
    _iso,
    _parse_timestamp,
    _plain_json,
    _required_text,
    _timestamp,
)


class EpistemicState(Enum):
    """Explicit claim state; support states are earned by evaluation."""

    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    HYPOTHESISED = "HYPOTHESISED"
    SUPPORTED = "SUPPORTED"
    CONDITIONALLY_SUPPORTED = "CONDITIONALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"

    def __str__(self) -> str:
        raise TypeError("EpistemicState cannot be coerced to a string implicitly")

    def __bool__(self) -> bool:
        raise TypeError("EpistemicState cannot be used as an implicit boolean")


_DECLARED_STATES = frozenset(
    {EpistemicState.OBSERVED, EpistemicState.INFERRED, EpistemicState.HYPOTHESISED}
)
_EARNED_STATES = frozenset(set(EpistemicState) - _DECLARED_STATES)
_EVALUATION_TOKEN = object()


def _ordered_ids(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a tuple or list of identifiers")
    items = tuple(value)
    for item in items:
        _required_text(item, f"{name} item")
    if len(items) != len(set(items)):
        raise ValueError(f"{name} must not contain duplicate identifiers")
    return tuple(sorted(items))


def _ordered_text(value: object, name: str) -> tuple[str, ...]:
    return _ordered_ids(value, name)


@dataclass(frozen=True, slots=True)
class ClaimEvaluationResult:
    """Immutable record of one explicit claim-state evaluation."""

    target_state: EpistemicState
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    failed_requirements: tuple[str, ...]
    conditions: tuple[str, ...]
    evaluator_id: str
    evaluator_version: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target_state, EpistemicState)
            or self.target_state not in _EARNED_STATES
        ):
            raise ValueError("evaluation target_state must be an earned EpistemicState")
        for name in ("supporting_evidence_ids", "contradicting_evidence_ids"):
            object.__setattr__(self, name, _ordered_ids(getattr(self, name), name))
        for name in ("assumptions", "failed_requirements", "conditions"):
            object.__setattr__(self, name, _ordered_text(getattr(self, name), name))
        if set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids):
            raise ValueError("evaluation evidence cannot both support and contradict")
        _required_text(self.evaluator_id, "evaluator_id")
        _required_text(self.evaluator_version, "evaluator_version")
        _timestamp(self.evaluated_at, "evaluated_at")
        if (
            self.target_state is EpistemicState.SUPPORTED
            and not self.supporting_evidence_ids
        ):
            raise ValueError("SUPPORTED evaluation requires supporting evidence")
        if self.target_state is EpistemicState.CONDITIONALLY_SUPPORTED:
            if not self.supporting_evidence_ids:
                raise ValueError(
                    "CONDITIONALLY_SUPPORTED evaluation requires supporting evidence"
                )
            if not (self.assumptions or self.conditions):
                raise ValueError(
                    "CONDITIONALLY_SUPPORTED evaluation requires an explicit limitation"
                )
        if (
            self.target_state is EpistemicState.CONTRADICTED
            and not self.contradicting_evidence_ids
        ):
            raise ValueError("CONTRADICTED evaluation requires contradicting evidence")
        if (
            self.target_state is EpistemicState.INSUFFICIENT_EVIDENCE
            and not self.failed_requirements
        ):
            raise ValueError(
                "INSUFFICIENT_EVIDENCE evaluation requires failed requirements"
            )
        if (
            self.target_state is EpistemicState.REJECTED
            and not self.failed_requirements
        ):
            raise ValueError("REJECTED evaluation requires a rejection reason")

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_state": self.target_state.value,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "assumptions": list(self.assumptions),
            "failed_requirements": list(self.failed_requirements),
            "conditions": list(self.conditions),
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "evaluated_at": _iso(self.evaluated_at),
        }

    @classmethod
    def from_dict(cls, payload: object) -> ClaimEvaluationResult:
        expected = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError(
                "evaluation record fields do not match the canonical schema"
            )
        try:
            return cls(
                **{
                    **payload,
                    "target_state": EpistemicState(payload["target_state"]),
                    "evaluated_at": _parse_timestamp(
                        payload["evaluated_at"], "evaluated_at"
                    ),
                }
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("malformed claim evaluation record") from exc


@dataclass(frozen=True, slots=True, init=False)
class ClaimObject:
    """Immutable structured claim whose earned states require an evaluation."""

    claim_id: str
    predicate: str
    subject: Any
    value: Any
    unit: str | None
    epistemic_state: EpistemicState
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    conditions: tuple[str, ...]
    failed_requirements: tuple[str, ...]
    uncertainty: Uncertainty | None
    created_at: datetime
    derivation_method: str
    reasoning_trace_id: str | None
    scope: Any
    metadata: Mapping[str, Any] | None
    evaluation_history: tuple[ClaimEvaluationResult, ...]

    def __init__(
        self,
        claim_id: str,
        predicate: str,
        subject: Any,
        value: Any,
        unit: str | None,
        epistemic_state: EpistemicState,
        supporting_evidence_ids: tuple[str, ...] = (),
        contradicting_evidence_ids: tuple[str, ...] = (),
        parent_claim_ids: tuple[str, ...] = (),
        assumptions: tuple[str, ...] = (),
        constraints: tuple[str, ...] = (),
        conditions: tuple[str, ...] = (),
        failed_requirements: tuple[str, ...] = (),
        uncertainty: Uncertainty | None = None,
        *,
        created_at: datetime,
        derivation_method: str,
        reasoning_trace_id: str | None = None,
        scope: Any = None,
        metadata: Mapping[str, Any] | None = None,
        evaluation_history: tuple[ClaimEvaluationResult, ...] = (),
        _evaluation_token: object | None = None,
    ) -> None:
        values = locals()
        for item in fields(self):
            object.__setattr__(self, item.name, values[item.name])
        self._validate(_evaluation_token)

    def _validate(self, evaluation_token: object | None) -> None:
        _required_text(self.claim_id, "claim_id")
        _required_text(self.predicate, "predicate")
        _required_text(self.derivation_method, "derivation_method")
        _timestamp(self.created_at, "created_at")
        if self.unit is not None:
            _required_text(self.unit, "unit")
        if self.reasoning_trace_id is not None:
            _required_text(self.reasoning_trace_id, "reasoning_trace_id")
        if not isinstance(self.epistemic_state, EpistemicState):
            raise ValueError("epistemic_state must be an EpistemicState enum member")
        if (
            self.epistemic_state in _EARNED_STATES
            and evaluation_token is not _EVALUATION_TOKEN
        ):
            raise ValueError("earned epistemic states require an evaluation result")
        for name in (
            "supporting_evidence_ids",
            "contradicting_evidence_ids",
            "parent_claim_ids",
        ):
            object.__setattr__(self, name, _ordered_ids(getattr(self, name), name))
        for name in ("assumptions", "constraints", "conditions", "failed_requirements"):
            object.__setattr__(self, name, _ordered_text(getattr(self, name), name))
        if set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids):
            raise ValueError(
                "an evidence ID cannot both support and contradict a claim"
            )
        if self.uncertainty is not None and not isinstance(
            self.uncertainty, Uncertainty
        ):
            raise ValueError("uncertainty must be an Uncertainty object or null")
        for name in ("subject", "value", "scope", "metadata"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be an object or null")
        history = tuple(self.evaluation_history)
        if any(not isinstance(event, ClaimEvaluationResult) for event in history):
            raise ValueError(
                "evaluation_history must contain ClaimEvaluationResult objects"
            )
        object.__setattr__(self, "evaluation_history", history)
        previous_time = self.created_at
        for event in history:
            if event.evaluated_at < previous_time:
                raise ValueError("evaluation history timestamps must be chronological")
            previous_time = event.evaluated_at
            if not set(event.supporting_evidence_ids).issubset(
                self.supporting_evidence_ids
            ) or not set(event.contradicting_evidence_ids).issubset(
                self.contradicting_evidence_ids
            ):
                raise ValueError("claim evidence must preserve evaluation evidence")
            if not set(event.assumptions).issubset(self.assumptions) or not set(
                event.conditions
            ).issubset(self.conditions):
                raise ValueError(
                    "claim limitations must preserve evaluation limitations"
                )
            if not set(event.failed_requirements).issubset(self.failed_requirements):
                raise ValueError("claim must preserve evaluated failed requirements")
        if self.epistemic_state in _EARNED_STATES:
            if not history or history[-1].target_state is not self.epistemic_state:
                raise ValueError(
                    "earned state requires a matching final evaluation record"
                )
        self._validate_state()

    def _validate_state(self) -> None:
        if self.epistemic_state is EpistemicState.OBSERVED:
            if not self.supporting_evidence_ids:
                raise ValueError("OBSERVED claims require supporting evidence")
            if self.parent_claim_ids:
                raise ValueError("OBSERVED claims cannot have parent claims")
        elif self.epistemic_state is EpistemicState.INFERRED and not (
            self.parent_claim_ids or self.supporting_evidence_ids
        ):
            raise ValueError("INFERRED claims require evidence or a parent claim")
        elif self.epistemic_state in {
            EpistemicState.SUPPORTED,
            EpistemicState.CONDITIONALLY_SUPPORTED,
        }:
            if not self.supporting_evidence_ids:
                raise ValueError("supported claims require supporting evidence")
            if self.epistemic_state is EpistemicState.CONDITIONALLY_SUPPORTED and not (
                self.assumptions
                or self.constraints
                or self.conditions
                or self.uncertainty
            ):
                raise ValueError("conditional support requires an explicit limitation")
        elif (
            self.epistemic_state is EpistemicState.CONTRADICTED
            and not self.contradicting_evidence_ids
        ):
            raise ValueError("CONTRADICTED claims require contradicting evidence")
        elif (
            self.epistemic_state is EpistemicState.INSUFFICIENT_EVIDENCE
            and not self.failed_requirements
        ):
            raise ValueError("INSUFFICIENT_EVIDENCE claims require failed requirements")
        elif self.epistemic_state is EpistemicState.REJECTED and not (
            self.failed_requirements or self.constraints
        ):
            raise ValueError("REJECTED claims require a reason or failed constraint")

    def with_evaluation(self, result: ClaimEvaluationResult) -> ClaimObject:
        if not isinstance(result, ClaimEvaluationResult):
            raise ValueError("result must be a ClaimEvaluationResult")
        support = tuple(
            sorted(
                set(self.supporting_evidence_ids) | set(result.supporting_evidence_ids)
            )
        )
        contradiction = tuple(
            sorted(
                set(self.contradicting_evidence_ids)
                | set(result.contradicting_evidence_ids)
            )
        )
        if set(support) & set(contradiction):
            raise ValueError(
                "evaluation would make evidence both support and contradict"
            )
        return ClaimObject(
            claim_id=self.claim_id,
            predicate=self.predicate,
            subject=self.subject,
            value=self.value,
            unit=self.unit,
            epistemic_state=result.target_state,
            supporting_evidence_ids=support,
            contradicting_evidence_ids=contradiction,
            parent_claim_ids=self.parent_claim_ids,
            assumptions=tuple(sorted(set(self.assumptions) | set(result.assumptions))),
            constraints=self.constraints,
            conditions=tuple(sorted(set(self.conditions) | set(result.conditions))),
            failed_requirements=tuple(
                sorted(set(self.failed_requirements) | set(result.failed_requirements))
            ),
            uncertainty=self.uncertainty,
            created_at=self.created_at,
            derivation_method=self.derivation_method,
            reasoning_trace_id=self.reasoning_trace_id,
            scope=self.scope,
            metadata=self.metadata,
            evaluation_history=(*self.evaluation_history, result),
            _evaluation_token=_EVALUATION_TOKEN,
        )

    def semantic_dict(self) -> dict[str, Any]:
        """Return only fields that define the semantic claim state."""
        return {
            "predicate": self.predicate,
            "subject": _plain_json(self.subject),
            "value": _plain_json(self.value),
            "unit": self.unit,
            "epistemic_state": self.epistemic_state.value,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
            "assumptions": list(self.assumptions),
            "constraints": list(self.constraints),
            "conditions": list(self.conditions),
            "failed_requirements": list(self.failed_requirements),
            "uncertainty": (
                None if self.uncertainty is None else self.uncertainty.to_dict()
            ),
            "derivation_method": self.derivation_method,
            "scope": _plain_json(self.scope),
        }

    def canonical_dict(self) -> dict[str, Any]:
        return {
            **self.semantic_dict(),
            "claim_id": self.claim_id,
            "created_at": _iso(self.created_at),
            "reasoning_trace_id": self.reasoning_trace_id,
            "metadata": _plain_json(self.metadata),
            "evaluation_history": [
                event.to_dict() for event in self.evaluation_history
            ],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.semantic_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_canonical_json(cls, serialized: str) -> ClaimObject:
        try:
            payload = json.loads(serialized)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("serialized claim must be valid JSON") from exc
        expected = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError(
                "serialized claim fields do not match the canonical schema"
            )
        try:
            state = EpistemicState(payload["epistemic_state"])
            uncertainty = (
                None
                if payload["uncertainty"] is None
                else Uncertainty(**payload["uncertainty"])
            )
            history = tuple(
                ClaimEvaluationResult.from_dict(item)
                for item in payload["evaluation_history"]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "serialized claim contains malformed epistemic data"
            ) from exc
        if state in _EARNED_STATES:
            if not history or history[-1].target_state is not state:
                raise ValueError(
                    "public deserialization cannot manufacture an earned state"
                )
            token: object | None = _EVALUATION_TOKEN
        else:
            token = None
        return cls(
            **{
                **payload,
                "epistemic_state": state,
                "uncertainty": uncertainty,
                "created_at": _parse_timestamp(payload["created_at"], "created_at"),
                "evaluation_history": history,
                "_evaluation_token": token,
            }
        )

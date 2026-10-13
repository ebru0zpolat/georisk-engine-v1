"""Typed, fail-closed uncertainty propagation for VERA-RAP research."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .contradictions import (
    ContradictionObject,
    ContradictionStatus,
    find_contradictions,
)
from .evidence import (
    _freeze_json,
    _iso,
    _parse_timestamp,
    _plain_json,
    _required_text,
    _timestamp,
)
from .evidence_graph import (
    ClaimNode,
    EvidenceGraph,
    EvidenceNode,
)
from .evidence import VerificationStatus


class _StrictEnum(Enum):
    def __str__(self) -> str:
        raise TypeError(f"{type(self).__name__} cannot be coerced to string")

    def __bool__(self) -> bool:
        raise TypeError(f"{type(self).__name__} cannot be used as a boolean")


class UncertaintyType(_StrictEnum):
    MEASUREMENT = "MEASUREMENT"
    MODEL = "MODEL"
    SAMPLING = "SAMPLING"
    TEMPORAL = "TEMPORAL"
    SPATIAL = "SPATIAL"
    TRANSFORMATION = "TRANSFORMATION"
    SOURCE_RELIABILITY = "SOURCE_RELIABILITY"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    CONTRADICTION = "CONTRADICTION"
    ASSUMPTION = "ASSUMPTION"
    STRUCTURAL = "STRUCTURAL"
    UNKNOWN = "UNKNOWN"


class UncertaintyDirection(_StrictEnum):
    ALEATORIC = "ALEATORIC"
    EPISTEMIC = "EPISTEMIC"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class PropagationRuleType(_StrictEnum):
    PASS_THROUGH = "PASS_THROUGH"
    INTERVAL_ENVELOPE = "INTERVAL_ENVELOPE"
    CONFIDENCE_FLOOR = "CONFIDENCE_FLOOR"
    UNCERTAINTY_WIDENING = "UNCERTAINTY_WIDENING"
    INDEPENDENT_EVIDENCE_REDUCTION = "INDEPENDENT_EVIDENCE_REDUCTION"
    TRANSFORMATION_PENALTY = "TRANSFORMATION_PENALTY"
    CONTRADICTION_PENALTY = "CONTRADICTION_PENALTY"
    MISSING_INFORMATION_PENALTY = "MISSING_INFORMATION_PENALTY"
    CUSTOM_DECLARED = "CUSTOM_DECLARED"


class ThresholdMetric(_StrictEnum):
    CONFIDENCE_MIN = "CONFIDENCE_MIN"
    INTERVAL_WIDTH_MAX = "INTERVAL_WIDTH_MAX"
    UPPER_BOUND_MAX = "UPPER_BOUND_MAX"
    LOWER_BOUND_MIN = "LOWER_BOUND_MIN"
    NO_UNRESOLVED_COMPONENTS = "NO_UNRESOLVED_COMPONENTS"
    NO_MISSING_INFORMATION = "NO_MISSING_INFORMATION"
    NO_CONTRADICTION_UNCERTAINTY = "NO_CONTRADICTION_UNCERTAINTY"


class ThresholdOperator(_StrictEnum):
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    EQUAL = "EQUAL"


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _strings(value: object, name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a tuple or list")
    result = tuple(value)
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    for item in result:
        _required_text(item, f"{name} item")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(result))


def _number(value: object, name: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number or null")
    return float(value)


@dataclass(frozen=True, slots=True)
class UncertaintyComponent:
    component_id: str
    uncertainty_type: UncertaintyType
    uncertainty_direction: UncertaintyDirection
    subject_id: str
    lower: float | None = None
    upper: float | None = None
    confidence: float | None = None
    distribution: str | None = None
    unit: str | None = None
    source_ids: tuple[str, ...] = ()
    method: str = "declared"
    assumptions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("component_id", "subject_id", "method"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.uncertainty_type, UncertaintyType) or not isinstance(
            self.uncertainty_direction, UncertaintyDirection
        ):
            raise ValueError("uncertainty type and direction must be enum members")
        for name in ("lower", "upper", "confidence"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if (self.lower is None) != (self.upper is None):
            raise ValueError("lower and upper must both be present or both be null")
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise ValueError("lower must not exceed upper")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        for name in ("distribution", "unit"):
            if getattr(self, name) is not None:
                _required_text(getattr(self, name), name)
        object.__setattr__(self, "source_ids", _strings(self.source_ids, "source_ids"))
        object.__setattr__(
            self, "assumptions", _strings(self.assumptions, "assumptions")
        )
        metadata = _freeze_json(self.metadata, "metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object or null")
        object.__setattr__(self, "metadata", metadata)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "uncertainty_type": self.uncertainty_type.value,
            "uncertainty_direction": self.uncertainty_direction.value,
            "subject_id": self.subject_id,
            "lower": self.lower,
            "upper": self.upper,
            "confidence": self.confidence,
            "distribution": self.distribution,
            "unit": self.unit,
            "source_ids": list(self.source_ids),
            "method": self.method,
            "assumptions": list(self.assumptions),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> UncertaintyComponent:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("uncertainty component fields do not match schema")
        return cls(
            **{
                **value,
                "uncertainty_type": UncertaintyType(value["uncertainty_type"]),
                "uncertainty_direction": UncertaintyDirection(
                    value["uncertainty_direction"]
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class UncertaintyProfile:
    profile_id: str
    subject_id: str
    components: tuple[UncertaintyComponent, ...]
    aggregation_method: str
    effective_lower: float | None
    effective_upper: float | None
    effective_confidence: float | None
    unresolved_components: tuple[str, ...]
    assumptions: tuple[str, ...]
    derived_from_ids: tuple[str, ...]
    created_at: datetime
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("profile_id", "subject_id", "aggregation_method"):
            _required_text(getattr(self, name), name)
        components = tuple(
            sorted(tuple(self.components), key=lambda item: item.component_id)
        )
        if any(
            not isinstance(item, UncertaintyComponent) for item in components
        ) or len({item.component_id for item in components}) != len(components):
            raise ValueError("components must be unique UncertaintyComponent objects")
        if not components:
            raise ValueError("an uncertainty profile requires components")
        object.__setattr__(self, "components", components)
        for name in ("effective_lower", "effective_upper", "effective_confidence"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if (self.effective_lower is None) != (self.effective_upper is None):
            raise ValueError("effective bounds must both be present or null")
        if (
            self.effective_lower is not None
            and self.effective_upper is not None
            and self.effective_lower > self.effective_upper
        ):
            raise ValueError("effective lower must not exceed upper")
        if (
            self.effective_confidence is not None
            and not 0 <= self.effective_confidence <= 1
        ):
            raise ValueError("effective confidence must be between 0 and 1")
        for name in ("unresolved_components", "assumptions", "derived_from_ids"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        component_ids = {item.component_id for item in components}
        if not set(self.unresolved_components).issubset(component_ids):
            raise ValueError(
                "unresolved components must reference preserved components"
            )
        _timestamp(self.created_at, "created_at")
        metadata = _freeze_json(self.metadata, "metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object or null")
        object.__setattr__(self, "metadata", metadata)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "subject_id": self.subject_id,
            "components": [item.canonical_dict() for item in self.components],
            "aggregation_method": self.aggregation_method,
            "effective_lower": self.effective_lower,
            "effective_upper": self.effective_upper,
            "effective_confidence": self.effective_confidence,
            "unresolved_components": list(self.unresolved_components),
            "assumptions": list(self.assumptions),
            "derived_from_ids": list(self.derived_from_ids),
            "created_at": _iso(self.created_at),
            "metadata": _plain_json(self.metadata),
        }

    def canonical_json(self) -> str:
        return _canonical(self.canonical_dict())

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> UncertaintyProfile:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("uncertainty profile fields do not match schema")
        return cls(
            **{
                **value,
                "components": tuple(
                    UncertaintyComponent.from_dict(item) for item in value["components"]
                ),
                "created_at": _parse_timestamp(value["created_at"], "created_at"),
            }
        )


@dataclass(frozen=True, slots=True)
class PropagationRule:
    rule_id: str
    rule_type: PropagationRuleType
    version: str
    input_subject_ids: tuple[str, ...]
    target_subject_id: str
    parameters: Mapping[str, Any]
    assumptions: tuple[str, ...]
    description: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "version", "target_subject_id", "description"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.rule_type, PropagationRuleType):
            raise ValueError("rule_type must be a PropagationRuleType")
        object.__setattr__(
            self,
            "input_subject_ids",
            _strings(self.input_subject_ids, "input_subject_ids", allow_empty=False),
        )
        object.__setattr__(
            self, "assumptions", _strings(self.assumptions, "assumptions")
        )
        parameters = _freeze_json(self.parameters, "parameters")
        if not isinstance(parameters, Mapping):
            raise ValueError("parameters must be an object")
        object.__setattr__(self, "parameters", parameters)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type.value,
            "version": self.version,
            "input_subject_ids": list(self.input_subject_ids),
            "target_subject_id": self.target_subject_id,
            "parameters": _plain_json(self.parameters),
            "assumptions": list(self.assumptions),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, value: object) -> PropagationRule:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("propagation rule fields do not match schema")
        return cls(**{**value, "rule_type": PropagationRuleType(value["rule_type"])})

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.canonical_dict()).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class UncertaintyPropagationResult:
    source_subject_ids: tuple[str, ...]
    target_subject_id: str
    input_profiles: tuple[UncertaintyProfile, ...]
    output_profile: UncertaintyProfile
    propagation_rule_id: str
    propagation_rule_version: str
    assumptions: tuple[str, ...]
    evaluated_at: datetime
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_subject_ids",
            _strings(self.source_subject_ids, "source_subject_ids", allow_empty=False),
        )
        _required_text(self.target_subject_id, "target_subject_id")
        for name in ("propagation_rule_id", "propagation_rule_version"):
            _required_text(getattr(self, name), name)
        profiles = tuple(
            sorted(tuple(self.input_profiles), key=lambda item: item.profile_id)
        )
        if (
            any(not isinstance(item, UncertaintyProfile) for item in profiles)
            or not profiles
        ):
            raise ValueError("input_profiles must contain uncertainty profiles")
        object.__setattr__(self, "input_profiles", profiles)
        if (
            not isinstance(self.output_profile, UncertaintyProfile)
            or self.output_profile.subject_id != self.target_subject_id
        ):
            raise ValueError("output profile must describe the target")
        object.__setattr__(
            self, "assumptions", _strings(self.assumptions, "assumptions")
        )
        object.__setattr__(self, "warnings", _strings(self.warnings, "warnings"))
        _timestamp(self.evaluated_at, "evaluated_at")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "source_subject_ids": list(self.source_subject_ids),
            "target_subject_id": self.target_subject_id,
            "input_profiles": [item.canonical_dict() for item in self.input_profiles],
            "output_profile": self.output_profile.canonical_dict(),
            "propagation_rule_id": self.propagation_rule_id,
            "propagation_rule_version": self.propagation_rule_version,
            "assumptions": list(self.assumptions),
            "evaluated_at": _iso(self.evaluated_at),
            "warnings": list(self.warnings),
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.canonical_dict()).encode()).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> UncertaintyPropagationResult:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("propagation result fields do not match schema")
        return cls(
            **{
                **value,
                "input_profiles": tuple(
                    UncertaintyProfile.from_dict(item)
                    for item in value["input_profiles"]
                ),
                "output_profile": UncertaintyProfile.from_dict(value["output_profile"]),
                "evaluated_at": _parse_timestamp(value["evaluated_at"], "evaluated_at"),
            }
        )


@dataclass(frozen=True, slots=True)
class UncertaintyThreshold:
    threshold_id: str
    metric: ThresholdMetric
    operator: ThresholdOperator
    value: float | bool | None
    unit: str | None
    component_types: tuple[UncertaintyType, ...]
    mandatory: bool
    description: str

    def __post_init__(self) -> None:
        _required_text(self.threshold_id, "threshold_id")
        _required_text(self.description, "description")
        if not isinstance(self.metric, ThresholdMetric) or not isinstance(
            self.operator, ThresholdOperator
        ):
            raise ValueError("threshold metric and operator must be enum members")
        if not isinstance(self.mandatory, bool):
            raise ValueError("mandatory must be boolean")
        if self.value is not None and not isinstance(self.value, bool):
            object.__setattr__(self, "value", _number(self.value, "value"))
        if self.unit is not None:
            _required_text(self.unit, "unit")
        types = tuple(sorted(tuple(self.component_types), key=lambda item: item.value))
        if any(not isinstance(item, UncertaintyType) for item in types) or len(
            set(types)
        ) != len(types):
            raise ValueError("component_types are malformed")
        object.__setattr__(self, "component_types", types)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "metric": self.metric.value,
            "operator": self.operator.value,
            "value": self.value,
            "unit": self.unit,
            "component_types": [item.value for item in self.component_types],
            "mandatory": self.mandatory,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, value: object) -> UncertaintyThreshold:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("uncertainty threshold fields do not match schema")
        return cls(
            **{
                **value,
                "metric": ThresholdMetric(value["metric"]),
                "operator": ThresholdOperator(value["operator"]),
                "component_types": tuple(
                    UncertaintyType(item) for item in value["component_types"]
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class UncertaintyGateResult:
    threshold_id: str
    passed: bool
    observed_value: Any
    required_value: Any
    blocking_components: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        _required_text(self.threshold_id, "threshold_id")
        _required_text(self.reason, "reason")
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be boolean")
        object.__setattr__(
            self,
            "blocking_components",
            _strings(self.blocking_components, "blocking_components"),
        )
        for name in ("observed_value", "required_value"):
            object.__setattr__(self, name, _freeze_json(getattr(self, name), name))

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "passed": self.passed,
            "observed_value": _plain_json(self.observed_value),
            "required_value": _plain_json(self.required_value),
            "blocking_components": list(self.blocking_components),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: object) -> UncertaintyGateResult:
        expected = {item.name for item in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("uncertainty gate result fields do not match schema")
        return cls(**value)


def _profile_id(
    target: str, rule: PropagationRule, profiles: tuple[UncertaintyProfile, ...]
) -> str:
    digest = hashlib.sha256(
        _canonical(
            {
                "target": target,
                "rule": rule.fingerprint,
                "inputs": [item.fingerprint for item in profiles],
            }
        ).encode()
    ).hexdigest()
    return f"uncertainty-{digest}"


def propagate_uncertainty(
    input_profiles: tuple[UncertaintyProfile, ...],
    rule: PropagationRule,
    *,
    at: datetime,
    graph: EvidenceGraph | None = None,
    contradictions: tuple[ContradictionObject, ...] = (),
) -> UncertaintyPropagationResult:
    _timestamp(at, "at")
    profiles = tuple(sorted(tuple(input_profiles), key=lambda item: item.profile_id))
    if not profiles or {item.subject_id for item in profiles} != set(
        rule.input_subject_ids
    ):
        raise ValueError("input profiles must exactly match rule input subjects")
    components = tuple(item for profile in profiles for item in profile.components)
    units = {item.unit for item in components if item.lower is not None}
    if len(units) > 1:
        raise ValueError(
            "incompatible uncertainty units require explicit normalization"
        )
    lowers = [item.lower for item in components if item.lower is not None]
    uppers = [item.upper for item in components if item.upper is not None]
    confidences = [
        item.confidence for item in components if item.confidence is not None
    ]
    lower, upper = (min(lowers), max(uppers)) if lowers else (None, None)
    confidence = min(confidences) if confidences else None
    unresolved = {
        item.component_id
        for item in components
        if item.lower is None and item.confidence is None
    }
    warnings: set[str] = set()
    extra: list[UncertaintyComponent] = []
    kind = rule.rule_type
    if kind is PropagationRuleType.PASS_THROUGH and len(profiles) != 1:
        raise ValueError("PASS_THROUGH requires exactly one input")
    elif kind in {
        PropagationRuleType.UNCERTAINTY_WIDENING,
        PropagationRuleType.TRANSFORMATION_PENALTY,
    }:
        amount = _number(rule.parameters.get("amount"), "amount")
        if (
            amount is None
            or amount < 0
            or lower is None
            or upper is None
            or not rule.assumptions
        ):
            raise ValueError(
                "widening requires non-negative amount, bounds, and assumptions"
            )
        lower, upper = lower - amount, upper + amount
        uncertainty_type = (
            UncertaintyType.TRANSFORMATION
            if kind is PropagationRuleType.TRANSFORMATION_PENALTY
            else UncertaintyType.ASSUMPTION
        )
        extra.append(
            UncertaintyComponent(
                f"{rule.rule_id}-penalty",
                uncertainty_type,
                UncertaintyDirection.EPISTEMIC,
                rule.target_subject_id,
                unit=next(iter(units), None),
                source_ids=rule.input_subject_ids,
                method=f"{rule.rule_id}@{rule.version}",
                assumptions=rule.assumptions,
            )
        )
    elif kind is PropagationRuleType.INDEPENDENT_EVIDENCE_REDUCTION:
        if (
            graph is None
            or rule.parameters.get("independence_declared") is not True
            or len(profiles) < 2
        ):
            raise ValueError(
                "reduction requires explicit independence and multiple graph-backed inputs"
            )
        for subject_id in rule.input_subject_ids:
            node = graph.nodes.get(subject_id)
            if (
                not isinstance(node, EvidenceNode)
                or node.evidence.verification_status is not VerificationStatus.VERIFIED
                or node.evidence.is_stale(at=at)
            ):
                raise ValueError("reduction inputs must be current VERIFIED evidence")
        if any(
            item.status
            in {
                ContradictionStatus.DETECTED,
                ContradictionStatus.UNRESOLVED,
                ContradictionStatus.RESOLUTION_PENDING,
            }
            for item in contradictions
        ):
            raise ValueError("unresolved contradiction prohibits uncertainty reduction")
        factor = _number(rule.parameters.get("reduction_factor"), "reduction_factor")
        if factor is None or not 0 < factor <= 1 or lower is None or upper is None:
            raise ValueError(
                "reduction requires reproducible factor in (0, 1] and bounds"
            )
        midpoint = (lower + upper) / 2
        width = (upper - lower) * factor
        lower, upper = midpoint - width / 2, midpoint + width / 2
        gain = _number(rule.parameters.get("confidence_gain", 0), "confidence_gain")
        confidence = None if confidence is None else min(1.0, confidence + (gain or 0))
    elif kind is PropagationRuleType.CONTRADICTION_PENALTY:
        active = tuple(
            item
            for item in contradictions
            if item.status
            in {
                ContradictionStatus.DETECTED,
                ContradictionStatus.UNRESOLVED,
                ContradictionStatus.RESOLUTION_PENDING,
            }
        )
        if not active:
            raise ValueError("contradiction penalty requires unresolved contradiction")
        extra.append(
            UncertaintyComponent(
                f"{rule.rule_id}-contradiction",
                UncertaintyType.CONTRADICTION,
                UncertaintyDirection.EPISTEMIC,
                rule.target_subject_id,
                source_ids=tuple(item.contradiction_id for item in active),
                method=f"{rule.rule_id}@{rule.version}",
            )
        )
        unresolved.add(extra[-1].component_id)
    elif kind is PropagationRuleType.MISSING_INFORMATION_PENALTY:
        extra.append(
            UncertaintyComponent(
                f"{rule.rule_id}-missing",
                UncertaintyType.MISSING_INFORMATION,
                UncertaintyDirection.EPISTEMIC,
                rule.target_subject_id,
                source_ids=rule.input_subject_ids,
                method=f"{rule.rule_id}@{rule.version}",
            )
        )
        unresolved.add(extra[-1].component_id)
    elif kind is PropagationRuleType.CUSTOM_DECLARED:
        raise ValueError("CUSTOM_DECLARED has no executable propagation semantics")
    output_components = tuple((*components, *extra))
    profile = UncertaintyProfile(
        _profile_id(rule.target_subject_id, rule, profiles),
        rule.target_subject_id,
        output_components,
        f"{kind.value}:{rule.rule_id}@{rule.version}",
        lower,
        upper,
        confidence,
        tuple(unresolved),
        rule.assumptions,
        tuple(item.profile_id for item in profiles),
        at,
        {"rule_fingerprint": rule.fingerprint},
    )
    return UncertaintyPropagationResult(
        rule.input_subject_ids,
        rule.target_subject_id,
        profiles,
        profile,
        rule.rule_id,
        rule.version,
        rule.assumptions,
        at,
        tuple(warnings),
    )


def _legacy_profile(
    subject_id: str, uncertainty: Any, *, at: datetime
) -> UncertaintyProfile:
    if uncertainty is None:
        component = UncertaintyComponent(
            f"{subject_id}-missing",
            UncertaintyType.MISSING_INFORMATION,
            UncertaintyDirection.EPISTEMIC,
            subject_id,
            source_ids=(subject_id,),
            method="missing-upstream-uncertainty",
        )
        unresolved = (component.component_id,)
    else:
        component = UncertaintyComponent(
            f"{subject_id}-declared",
            UncertaintyType.MEASUREMENT,
            UncertaintyDirection.UNKNOWN,
            subject_id,
            uncertainty.lower,
            uncertainty.upper,
            uncertainty.confidence,
            unit=None,
            source_ids=(subject_id,),
            method=uncertainty.method or uncertainty.kind,
        )
        unresolved = (
            ()
            if component.lower is not None or component.confidence is not None
            else (component.component_id,)
        )
    return UncertaintyProfile(
        f"profile-{subject_id}",
        subject_id,
        (component,),
        "RAP-001/002_DECLARED",
        component.lower,
        component.upper,
        component.confidence,
        unresolved,
        (),
        (subject_id,),
        at,
    )


def derive_claim_uncertainty(
    claim_id: str,
    graph: EvidenceGraph,
    rules: tuple[PropagationRule, ...],
    *,
    at: datetime,
) -> UncertaintyPropagationResult:
    _timestamp(at, "at")
    node = graph.nodes.get(claim_id)
    if not isinstance(node, ClaimNode):
        raise ValueError("claim_id must reference a ClaimNode")
    subjects = tuple(
        sorted((*node.claim.supporting_evidence_ids, *node.claim.parent_claim_ids))
    )
    profiles: list[UncertaintyProfile] = []
    for subject_id in subjects:
        upstream = graph.nodes.get(subject_id)
        if isinstance(upstream, EvidenceNode):
            profile = _legacy_profile(subject_id, upstream.evidence.uncertainty, at=at)
            if (
                upstream.evidence.verification_status is not VerificationStatus.VERIFIED
                or upstream.evidence.is_stale(at=at)
            ):
                missing = UncertaintyComponent(
                    f"{subject_id}-inadmissible",
                    UncertaintyType.MISSING_INFORMATION,
                    UncertaintyDirection.EPISTEMIC,
                    subject_id,
                    source_ids=(subject_id,),
                    method="inadmissible-upstream",
                )
                profile = UncertaintyProfile(
                    profile.profile_id,
                    subject_id,
                    (*profile.components, missing),
                    profile.aggregation_method,
                    profile.effective_lower,
                    profile.effective_upper,
                    profile.effective_confidence,
                    (*profile.unresolved_components, missing.component_id),
                    (),
                    (subject_id,),
                    at,
                )
            profiles.append(profile)
        elif isinstance(upstream, ClaimNode):
            if upstream.claim.uncertainty is not None:
                profiles.append(
                    _legacy_profile(subject_id, upstream.claim.uncertainty, at=at)
                )
            elif any(rule.target_subject_id == subject_id for rule in rules):
                profiles.append(
                    derive_claim_uncertainty(
                        subject_id, graph, rules, at=at
                    ).output_profile
                )
            else:
                profiles.append(_legacy_profile(subject_id, None, at=at))
        else:
            profiles.append(_legacy_profile(subject_id, None, at=at))
    if not profiles:
        profiles.append(_legacy_profile(f"{claim_id}-dependency", None, at=at))
        subjects = (profiles[0].subject_id,)
    matching = tuple(
        rule
        for rule in rules
        if rule.target_subject_id == claim_id
        and set(rule.input_subject_ids) == set(subjects)
    )
    if len(matching) != 1:
        raise ValueError("exactly one propagation rule must match claim dependencies")
    contradictions = find_contradictions(graph, at=at)
    return propagate_uncertainty(
        tuple(profiles), matching[0], at=at, graph=graph, contradictions=contradictions
    )


def evaluate_uncertainty_gate(
    profile: UncertaintyProfile, threshold: UncertaintyThreshold
) -> UncertaintyGateResult:
    components = tuple(
        item
        for item in profile.components
        if not threshold.component_types
        or item.uncertainty_type in threshold.component_types
    )
    blocking: tuple[str, ...] = ()
    observed: Any
    metric = threshold.metric
    if metric is ThresholdMetric.CONFIDENCE_MIN:
        observed = profile.effective_confidence
    elif metric is ThresholdMetric.INTERVAL_WIDTH_MAX:
        observed = (
            None
            if profile.effective_lower is None or profile.effective_upper is None
            else profile.effective_upper - profile.effective_lower
        )
    elif metric is ThresholdMetric.UPPER_BOUND_MAX:
        observed = profile.effective_upper
    elif metric is ThresholdMetric.LOWER_BOUND_MIN:
        observed = profile.effective_lower
    elif metric is ThresholdMetric.NO_UNRESOLVED_COMPONENTS:
        observed = not profile.unresolved_components
        blocking = profile.unresolved_components
    elif metric is ThresholdMetric.NO_MISSING_INFORMATION:
        blocking = tuple(
            item.component_id
            for item in components
            if item.uncertainty_type is UncertaintyType.MISSING_INFORMATION
        )
        observed = not blocking
    else:
        blocking = tuple(
            item.component_id
            for item in components
            if item.uncertainty_type is UncertaintyType.CONTRADICTION
        )
        observed = not blocking
    if observed is None:
        passed = False
    elif threshold.operator is ThresholdOperator.GREATER_THAN_OR_EQUAL:
        passed = threshold.value is not None and observed >= threshold.value
    elif threshold.operator is ThresholdOperator.LESS_THAN_OR_EQUAL:
        passed = threshold.value is not None and observed <= threshold.value
    else:
        passed = observed == threshold.value
    if not passed and not blocking:
        blocking = tuple(item.component_id for item in components)
    return UncertaintyGateResult(
        threshold.threshold_id,
        passed,
        observed,
        threshold.value,
        blocking,
        "threshold_satisfied" if passed else "threshold_not_satisfied",
    )

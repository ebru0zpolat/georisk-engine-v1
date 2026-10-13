from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import json

import pytest

from app.research.vera_rap import (
    ClaimEvaluationResult,
    ClaimObject,
    EpistemicState,
    Uncertainty,
)

NOW = datetime(2026, 2, 1, tzinfo=UTC)


def claim(**changes: object) -> ClaimObject:
    values: dict[str, object] = {
        "claim_id": "claim-1",
        "predicate": "has_property",
        "subject": {"id": "subject-1", "parts": ["a", "b"]},
        "value": {"category": "example", "score": 2},
        "unit": None,
        "epistemic_state": EpistemicState.HYPOTHESISED,
        "supporting_evidence_ids": (),
        "contradicting_evidence_ids": (),
        "parent_claim_ids": (),
        "assumptions": (),
        "constraints": (),
        "conditions": (),
        "failed_requirements": (),
        "uncertainty": None,
        "created_at": NOW,
        "derivation_method": "research-rule-v1",
        "reasoning_trace_id": None,
        "scope": {"areas": ["one"]},
        "metadata": {"explanation": "non-authoritative prose"},
        "evaluation_history": (),
    }
    values.update(changes)
    return ClaimObject(**values)  # type: ignore[arg-type]


def evaluation(target: EpistemicState, **changes: object) -> ClaimEvaluationResult:
    values: dict[str, object] = {
        "target_state": target,
        "supporting_evidence_ids": ("evidence-1",),
        "contradicting_evidence_ids": (),
        "assumptions": (),
        "failed_requirements": (),
        "conditions": (),
        "evaluator_id": "evaluator-1",
        "evaluator_version": "1.0",
        "evaluated_at": NOW,
    }
    values.update(changes)
    return ClaimEvaluationResult(**values)  # type: ignore[arg-type]


def test_hypothesised_without_evidence_is_valid_and_immutable() -> None:
    item = claim()
    assert item.epistemic_state is EpistemicState.HYPOTHESISED
    with pytest.raises(FrozenInstanceError):
        item.value = 3  # type: ignore[misc]


def test_deterministic_fingerprint_and_order_normalization() -> None:
    first = claim(
        supporting_evidence_ids=("evidence-b", "evidence-a"),
        metadata={"z": 1, "a": 2},
    )
    second = claim(
        supporting_evidence_ids=("evidence-a", "evidence-b"),
        metadata={"a": 2, "z": 1},
    )
    assert first.fingerprint == second.fingerprint
    assert first.canonical_json() == second.canonical_json()


def test_nested_mutation_and_caller_owned_mutation_are_rejected() -> None:
    subject = {"items": [{"value": 1}]}
    item = claim(subject=subject)
    fingerprint = item.fingerprint
    with pytest.raises(TypeError):
        item.subject["items"][0]["value"] = 2
    with pytest.raises(TypeError):
        item.scope["areas"] += ("two",)
    with pytest.raises(TypeError):
        item.metadata["explanation"] = "changed"
    subject["items"][0]["value"] = 2
    assert item.fingerprint == fingerprint


def test_observed_without_evidence_fails_and_parents_are_forbidden() -> None:
    with pytest.raises(ValueError, match="OBSERVED"):
        claim(epistemic_state=EpistemicState.OBSERVED)
    with pytest.raises(ValueError, match="parent"):
        claim(
            epistemic_state=EpistemicState.OBSERVED,
            supporting_evidence_ids=("evidence-1",),
            parent_claim_ids=("parent-1",),
        )


def test_inferred_requires_evidence_or_parent_without_implying_support() -> None:
    with pytest.raises(ValueError, match="INFERRED"):
        claim(epistemic_state=EpistemicState.INFERRED)
    item = claim(
        epistemic_state=EpistemicState.INFERRED, parent_claim_ids=("parent-1",)
    )
    assert item.epistemic_state is EpistemicState.INFERRED


def test_supported_state_must_be_earned_not_declared() -> None:
    with pytest.raises(ValueError, match="evaluation"):
        claim(
            epistemic_state=EpistemicState.SUPPORTED,
            supporting_evidence_ids=("evidence-1",),
        )


def test_conditionally_supported_cannot_be_declared() -> None:
    with pytest.raises(ValueError, match="evaluation"):
        claim(
            epistemic_state=EpistemicState.CONDITIONALLY_SUPPORTED,
            supporting_evidence_ids=("evidence-1",),
            conditions=("condition-1",),
        )


def test_evaluation_can_earn_supported_and_leaves_original_unchanged() -> None:
    original = claim()
    earned = original.with_evaluation(evaluation(EpistemicState.SUPPORTED))
    assert earned is not original
    assert original.epistemic_state is EpistemicState.HYPOTHESISED
    assert original.supporting_evidence_ids == ()
    assert earned.epistemic_state is EpistemicState.SUPPORTED
    assert earned.supporting_evidence_ids == ("evidence-1",)
    assert earned.evaluation_history[-1].evaluator_id == "evaluator-1"


def test_evaluation_can_earn_conditional_support_with_limitation() -> None:
    result = evaluation(
        EpistemicState.CONDITIONALLY_SUPPORTED, conditions=("limited scope",)
    )
    earned = claim().with_evaluation(result)
    assert earned.epistemic_state is EpistemicState.CONDITIONALLY_SUPPORTED
    assert earned.conditions == ("limited scope",)


def test_conditional_support_requires_explicit_limitation() -> None:
    with pytest.raises(ValueError, match="limitation"):
        evaluation(EpistemicState.CONDITIONALLY_SUPPORTED)
    earned = claim(uncertainty=Uncertainty("unknown-method")).with_evaluation(
        evaluation(EpistemicState.CONDITIONALLY_SUPPORTED, assumptions=("bounded",))
    )
    assert earned.uncertainty is not None


def test_contradiction_preserves_prior_support() -> None:
    supported = claim().with_evaluation(evaluation(EpistemicState.SUPPORTED))
    contradicted = supported.with_evaluation(
        evaluation(
            EpistemicState.CONTRADICTED,
            supporting_evidence_ids=(),
            contradicting_evidence_ids=("evidence-2",),
        )
    )
    assert contradicted.supporting_evidence_ids == ("evidence-1",)
    assert contradicted.contradicting_evidence_ids == ("evidence-2",)
    assert len(contradicted.evaluation_history) == 2


def test_contradicted_requires_contradicting_evidence() -> None:
    with pytest.raises(ValueError, match="contradicting"):
        evaluation(EpistemicState.CONTRADICTED, supporting_evidence_ids=())


def test_insufficient_and_rejected_require_explicit_reasons() -> None:
    with pytest.raises(ValueError, match="failed requirements"):
        evaluation(EpistemicState.INSUFFICIENT_EVIDENCE, supporting_evidence_ids=())
    insufficient = claim().with_evaluation(
        evaluation(
            EpistemicState.INSUFFICIENT_EVIDENCE,
            supporting_evidence_ids=(),
            failed_requirements=("mandatory source absent",),
        )
    )
    assert insufficient.failed_requirements == ("mandatory source absent",)
    with pytest.raises(ValueError, match="rejection reason"):
        evaluation(EpistemicState.REJECTED, supporting_evidence_ids=())


def test_evidence_overlap_duplicates_and_empty_ids_fail() -> None:
    with pytest.raises(ValueError, match="both support and contradict"):
        claim(supporting_evidence_ids=("same",), contradicting_evidence_ids=("same",))
    with pytest.raises(ValueError, match="duplicate"):
        claim(supporting_evidence_ids=("same", "same"))
    with pytest.raises(ValueError, match="non-empty"):
        claim(supporting_evidence_ids=("",))


def test_round_trip_serialization_is_stable_for_declared_and_earned_states() -> None:
    for item in (
        claim(),
        claim().with_evaluation(evaluation(EpistemicState.SUPPORTED)),
    ):
        restored = ClaimObject.from_canonical_json(item.canonical_json())
        assert restored == item
        assert restored.canonical_json() == item.canonical_json()
        assert restored.fingerprint == item.fingerprint


def test_public_deserialization_cannot_manufacture_supported() -> None:
    payload = json.loads(claim().canonical_json())
    payload["epistemic_state"] = "SUPPORTED"
    payload["supporting_evidence_ids"] = ["evidence-1"]
    with pytest.raises(ValueError, match="cannot manufacture"):
        ClaimObject.from_canonical_json(json.dumps(payload))


def test_deserialization_rejects_evaluation_evidence_not_preserved_by_claim() -> None:
    earned = claim().with_evaluation(evaluation(EpistemicState.SUPPORTED))
    payload = json.loads(earned.canonical_json())
    payload["supporting_evidence_ids"] = ["fabricated-replacement"]
    with pytest.raises(ValueError, match="preserve evaluation evidence"):
        ClaimObject.from_canonical_json(json.dumps(payload))


def test_evaluation_cannot_predate_claim() -> None:
    with pytest.raises(ValueError, match="chronological"):
        claim().with_evaluation(
            evaluation(
                EpistemicState.SUPPORTED,
                evaluated_at=datetime(2026, 1, 31, tzinfo=UTC),
            )
        )


def test_string_state_truthiness_and_coercion_fail() -> None:
    with pytest.raises(ValueError, match="EpistemicState"):
        claim(epistemic_state="HYPOTHESISED")
    with pytest.raises(TypeError):
        bool(EpistemicState.SUPPORTED)
    with pytest.raises(TypeError):
        str(EpistemicState.SUPPORTED)


def test_dataclass_replace_cannot_escalate_or_rebuild_earned_state() -> None:
    inferred = claim(
        epistemic_state=EpistemicState.INFERRED, parent_claim_ids=("parent-1",)
    )
    with pytest.raises(ValueError, match="evaluation"):
        replace(
            inferred,
            epistemic_state=EpistemicState.SUPPORTED,
            supporting_evidence_ids=("evidence-1",),
        )
    supported = claim().with_evaluation(evaluation(EpistemicState.SUPPORTED))
    with pytest.raises(ValueError, match="evaluation"):
        replace(supported, metadata={"changed": True})


def test_different_state_and_value_change_semantic_fingerprint() -> None:
    hypothesis = claim(supporting_evidence_ids=("evidence-1",))
    observed = claim(
        epistemic_state=EpistemicState.OBSERVED,
        supporting_evidence_ids=("evidence-1",),
    )
    assert hypothesis.fingerprint != observed.fingerprint
    assert (
        hypothesis.fingerprint
        != claim(
            supporting_evidence_ids=("evidence-1",), value={"category": "other"}
        ).fingerprint
    )


def test_locator_and_explanatory_metadata_do_not_change_semantic_identity() -> None:
    first = claim()
    second = claim(
        claim_id="another-locator",
        created_at=datetime(2026, 2, 2, tzinfo=UTC),
        reasoning_trace_id="trace-2",
        metadata={"explanation": "different words"},
    )
    assert first.fingerprint == second.fingerprint
    assert first.canonical_json() != second.canonical_json()

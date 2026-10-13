from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import json

import pytest

from app.research.vera_rap.evidence import (
    EvidenceObject,
    Provenance,
    Uncertainty,
    VerificationStatus,
)

HASH = "a" * 64
NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)


def evidence(**changes: object) -> EvidenceObject:
    values: dict[str, object] = {
        "evidence_id": "ev-1",
        "evidence_type": "observation",
        "source_id": "source-1",
        "source_uri": "https://example.test/artifact",
        "content_hash": HASH,
        "retrieved_at": NOW,
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
        "valid_until": datetime(2026, 2, 1, tzinfo=UTC),
        "jurisdiction": {"codes": ["A", "B"]},
        "spatial_scope": {"kind": "opaque", "identifier": "scope-1"},
        "measurement": {"value": 12.5, "qualifier": None},
        "unit": "generic-unit",
        "uncertainty": Uncertainty("interval", 11.0, 14.0, 0.9, "declared"),
        "licence_status": "declared-open",
        "verification_status": VerificationStatus.UNVERIFIED,
        "provenance": Provenance(
            "source-1", "https-download", HASH, ("normalize-v1",), ("ev-0",)
        ),
        "metadata": {"labels": ["one", "two"], "nullable": None},
    }
    values.update(changes)
    return EvidenceObject(**values)  # type: ignore[arg-type]


def test_deterministic_fingerprint_and_construction_order_independence() -> None:
    first = evidence(metadata={"z": 1, "a": {"y": 2, "x": 3}})
    second = evidence(metadata={"a": {"x": 3, "y": 2}, "z": 1})
    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint == second.fingerprint


def test_mutation_is_rejected_including_nested_identity_data() -> None:
    original = {"nested": [1, {"key": "value"}]}
    item = evidence(metadata=original)
    fingerprint = item.fingerprint
    with pytest.raises(FrozenInstanceError):
        item.source_id = "other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        item.metadata["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        item.metadata["nested"][1]["key"] = "changed"  # type: ignore[index]
    original["nested"][1]["key"] = "changed"  # type: ignore[index]
    assert item.fingerprint == fingerprint


def test_serialization_round_trip_preserves_full_state() -> None:
    item = evidence(verification_status=VerificationStatus.CONTRADICTED)
    restored = EvidenceObject.from_canonical_json(item.canonical_json())
    assert restored == item
    assert restored.canonical_json() == item.canonical_json()
    assert restored.fingerprint == item.fingerprint
    assert restored.uncertainty == item.uncertainty
    assert restored.provenance == item.provenance


@pytest.mark.parametrize("source_id", ["", "   ", None])
def test_missing_source_id_is_rejected(source_id: object) -> None:
    with pytest.raises(ValueError, match="source_id"):
        evidence(source_id=source_id)


@pytest.mark.parametrize("content_hash", ["", "abc", "A" * 64, None])
def test_missing_or_invalid_content_hash_is_rejected(content_hash: object) -> None:
    with pytest.raises(ValueError, match="content_hash"):
        evidence(content_hash=content_hash)


def test_missing_and_malformed_provenance_are_rejected() -> None:
    with pytest.raises((TypeError, ValueError)):
        evidence(provenance=None)
    payload = json.loads(evidence().canonical_json())
    payload["provenance"] = {"source_identifier": "source-1"}
    with pytest.raises(ValueError, match="malformed"):
        EvidenceObject.from_canonical_json(json.dumps(payload))


def test_observation_after_retrieval_is_rejected() -> None:
    with pytest.raises(ValueError, match="observed_at"):
        evidence(observed_at=datetime(2026, 1, 3, tzinfo=UTC))


def test_stale_and_non_stale_evaluation_is_explicit_and_non_mutating() -> None:
    item = evidence()
    fingerprint = item.fingerprint
    assert not item.is_stale(at=datetime(2026, 2, 1, tzinfo=UTC))
    assert item.is_stale(at=datetime(2026, 2, 1, 0, 0, 1, tzinfo=UTC))
    assert item.fingerprint == fingerprint
    assert evidence(
        verification_status=VerificationStatus.STALE, valid_until=None
    ).is_stale(at=NOW)


def test_invalid_validity_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid_until"):
        evidence(valid_from=datetime(2026, 2, 2, tzinfo=UTC))


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Uncertainty("range", 2, 1),
        lambda: Uncertainty("range", 1, None),
        lambda: Uncertainty("range", confidence=1.1),
        lambda: Uncertainty("range", lower=float("nan"), upper=1),
    ],
)
def test_invalid_uncertainty_is_rejected(factory: object) -> None:
    with pytest.raises(ValueError):
        factory()  # type: ignore[operator]


def test_malformed_uncertainty_structure_is_rejected() -> None:
    with pytest.raises(ValueError, match="Uncertainty"):
        evidence(uncertainty={"kind": "range"})


def test_hash_and_uri_do_not_imply_verified_regression() -> None:
    item = evidence()
    assert item.content_hash and item.source_uri
    assert item.verification_status is VerificationStatus.UNVERIFIED


def test_unverified_survives_serialization() -> None:
    restored = EvidenceObject.from_canonical_json(evidence().canonical_json())
    assert restored.verification_status is VerificationStatus.UNVERIFIED


def test_unsupported_status_and_string_coercion_are_rejected() -> None:
    with pytest.raises(ValueError, match="VerificationStatus"):
        evidence(verification_status="VERIFIED")
    with pytest.raises(TypeError):
        str(VerificationStatus.VERIFIED)
    with pytest.raises(TypeError):
        bool(VerificationStatus.VERIFIED)


def test_semantically_different_objects_have_different_fingerprints() -> None:
    assert (
        evidence().fingerprint
        != evidence(measurement={"value": 12.6, "qualifier": None}).fingerprint
    )


def test_provenance_must_match_top_level_identity() -> None:
    with pytest.raises(ValueError, match="source identifier"):
        evidence(provenance=Provenance("other", "download", HASH))
    with pytest.raises(ValueError, match="artifact hash"):
        evidence(provenance=Provenance("source-1", "download", "b" * 64))


def test_nulls_are_explicit_in_canonical_serialization() -> None:
    payload = evidence(uncertainty=None, measurement=None).canonical_dict()
    assert payload["uncertainty"] is None
    assert payload["measurement"] is None

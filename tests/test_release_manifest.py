"""Named release manifest and fail-closed readiness gates."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.release_manifest import (
    ReleaseApproval,
    ReleaseGateStates,
    ReleaseManifest,
)


def _manifest(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "release_version": "pilot-v1",
        "commit_sha": "abc123",
        "geography": "Netherlands",
        "hazards": ["flood"],
        "asset_class": "commercial_property",
        "permitted_user_decision": "analyst prioritisation",
        "limitations": ["Not a flood certification."],
        "prohibited_uses": ["Automated underwriting."],
    }
    values.update(overrides)
    return values


def _passing_gates() -> ReleaseGateStates:
    return ReleaseGateStates(
        platform_operational=True,
        data_source_operational=True,
        model_validated_for_use_case=True,
        commercially_validated=True,
        runtime_live_verified=True,
    )


def test_current_release_manifest_preserves_truth_state() -> None:
    response = TestClient(app).get("/v1/release-manifest")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "demo_only"
    assert body["production_eligible"] is False
    assert body["gates"] == {
        "platform_operational": False,
        "data_source_operational": False,
        "model_validated_for_use_case": False,
        "commercially_validated": False,
        "runtime_live_verified": False,
    }
    assert body["geography"] == "Netherlands"
    assert body["approvals"] == []
    assert body["evidence_ids"] == []


def test_one_green_gate_cannot_enable_production() -> None:
    with pytest.raises(ValidationError, match="every gate"):
        ReleaseManifest.model_validate(
            _manifest(
                decision="production_eligible",
                production_eligible=True,
                gates=ReleaseGateStates(platform_operational=True),
            )
        )


def test_all_gates_still_require_explicit_production_decision() -> None:
    gates = _passing_gates()
    with pytest.raises(ValidationError, match="every gate"):
        ReleaseManifest.model_validate(
            _manifest(decision="controlled_pilot", production_eligible=True, gates=gates)
        )


def test_non_demo_release_requires_operational_owners_and_exact_sha() -> None:
    with pytest.raises(ValidationError, match="exact commit SHA"):
        ReleaseManifest.model_validate(
            _manifest(decision="controlled_pilot", commit_sha="unknown")
        )

    with pytest.raises(ValidationError, match="rollback owner"):
        ReleaseManifest.model_validate(
            _manifest(decision="controlled_pilot", commit_sha="a" * 40)
        )


@pytest.mark.parametrize("commit_sha", ["main", "abc123", "g" * 40, "a" * 39])
def test_non_demo_release_rejects_non_full_git_sha(commit_sha: str) -> None:
    with pytest.raises(ValidationError, match="exact commit SHA"):
        ReleaseManifest.model_validate(
            _manifest(decision="controlled_pilot", commit_sha=commit_sha)
        )


def test_production_eligibility_requires_current_linked_approval() -> None:
    now = datetime.now(timezone.utc)
    base = _manifest(
        decision="production_eligible",
        production_eligible=True,
        commit_sha="a" * 40,
        gates=_passing_gates(),
        rollback_owner="release@example.com",
        incident_contact="incident@example.com",
    )

    with pytest.raises(ValidationError, match="current approval has linked evidence"):
        ReleaseManifest.model_validate(base)

    expired_approval = ReleaseApproval(
        approval_type="release",
        reviewer="reviewer@example.com",
        evidence_id="EV-1",
        approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(ValidationError, match="current approval has linked evidence"):
        ReleaseManifest.model_validate(
            {**base, "evidence_ids": ["EV-1"], "approvals": [expired_approval]}
        )

    current_approval = ReleaseApproval(
        approval_type="release",
        reviewer="reviewer@example.com",
        evidence_id="EV-2",
        approved_at=now,
        expires_at=None,
    )
    manifest = ReleaseManifest.model_validate(
        {**base, "evidence_ids": ["EV-2"], "approvals": [current_approval]}
    )
    assert manifest.production_eligible is True


def test_approval_expiration_must_follow_approval() -> None:
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="later than approved_at"):
        ReleaseApproval(
            approval_type="licence",
            reviewer="info@georiskengine.com",
            evidence_id="EV-1",
            approved_at=now,
            expires_at=now,
        )

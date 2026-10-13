"""C2.5 composition tests (GEO-62).

Covers what the single controlled-pilot operations surface adds over the two
PRs it was composed from:

- the three authenticated-smoke assertions (from PR #145's script, now in the
  hardened ``app.ops.smoke`` transport);
- the fail-closed verdict over those assertions;
- ``S3ObjectLockRetention``, which moves PR #145's inline object-lock shell
  behind the ``EvidenceRetention`` contract.

No test performs a network call.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.ops.evidence import SCHEMA_VERSION, build_smoke_evidence
from app.ops.retention import S3ObjectLockRetention
from app.ops.smoke import smoke_passed


# ---------------------------------------------------------------------------
# Evidence schema
# ---------------------------------------------------------------------------


def _evidence(**overrides):
    base = dict(
        verification_id="smoke-abc123def456",
        release_commit_sha="a" * 40,
        source_tree_dirty=False,
        environment_name="controlled_pilot",
        endpoint="https://example.test/v1/health",
        target_hostname="example.test",
        request_method="GET",
        response_status=200,
        response_content_type="application/json",
        response_byte_count=128,
        latency_ms=12.5,
        authentication_attempted=True,
        authentication_succeeded=True,
        transport_verified=True,
        application_response_verified=True,
        retention_status="pending",
        unauthenticated_access_denied=True,
        deployed_git_sha="a" * 40,
        release_sha_match=True,
        golden_verification="PASS",
    )
    base.update(overrides)
    return build_smoke_evidence(**base)


def test_schema_version_is_v2() -> None:
    assert SCHEMA_VERSION == "geo-62-smoke-evidence-v2"
    assert _evidence().schema_version == "geo-62-smoke-evidence-v2"


def test_new_assertion_fields_default_to_not_attempted() -> None:
    """A record that never ran the assertions must not read as having passed."""
    ev = build_smoke_evidence(
        verification_id="smoke-000000000000",
        release_commit_sha="b" * 40,
        source_tree_dirty=False,
        environment_name="unknown",
        endpoint="https://example.test/v1/health",
        target_hostname="example.test",
        request_method="GET",
        response_status=200,
        response_content_type="application/json",
        response_byte_count=10,
        latency_ms=1.0,
        authentication_attempted=False,
        authentication_succeeded=False,
        transport_verified=True,
        application_response_verified=True,
        retention_status="pending",
    )
    assert ev.unauthenticated_access_denied is None
    assert ev.release_sha_match is None
    assert ev.golden_verification == "NOT_RUN"
    assert ev.deployed_git_sha == ""


def test_evidence_hash_covers_the_new_fields() -> None:
    passing = _evidence()
    tampered = passing.model_copy(update={"golden_verification": "FAIL"})
    assert passing.verify_hash() is True
    assert tampered.verify_hash() is False


def test_evidence_never_carries_a_credential() -> None:
    payload = json.loads(_evidence().canonical_payload())
    joined = " ".join(str(v).lower() for v in payload.values())
    for forbidden in ("bearer", "authorization", "token", "secret"):
        assert forbidden not in joined


def test_flags_stay_false_in_v2() -> None:
    ev = _evidence()
    assert ev.production_eligible is False
    assert ev.runtime_live_verified is False


# ---------------------------------------------------------------------------
# Fail-closed verdict
# ---------------------------------------------------------------------------


def test_verdict_passes_only_when_every_assertion_holds() -> None:
    assert smoke_passed(_evidence()) is True


@pytest.mark.parametrize(
    "override",
    [
        {"unauthenticated_access_denied": False},
        {"unauthenticated_access_denied": None},
        {"release_sha_match": False},
        {"release_sha_match": None},
        {"golden_verification": "FAIL"},
        {"golden_verification": "NOT_RUN"},
        {"transport_verified": False},
        {"application_response_verified": False},
    ],
)
def test_verdict_fails_closed(override: dict) -> None:
    """None (not attempted) fails exactly like False (attempted and refuted)."""
    assert smoke_passed(_evidence(**override)) is False


def test_golden_may_be_waived_only_explicitly() -> None:
    ev = _evidence(golden_verification="NOT_RUN")
    assert smoke_passed(ev, golden_required=True) is False
    assert smoke_passed(ev, golden_required=False) is True


# ---------------------------------------------------------------------------
# S3 Object Lock retention
# ---------------------------------------------------------------------------


class _FakeS3:
    """Minimal in-memory stand-in for the botocore S3 client surface."""

    def __init__(
        self,
        *,
        versioning: str = "Enabled",
        lock_enabled: str = "Enabled",
        stored_mode: str = "COMPLIANCE",
        retain_shortfall: timedelta = timedelta(0),
        version_id: str | None = "v1",
    ) -> None:
        self._versioning = versioning
        self._lock_enabled = lock_enabled
        self._stored_mode = stored_mode
        self._retain_shortfall = retain_shortfall
        self._version_id = version_id
        self.objects: dict[str, dict] = {}

    def get_bucket_versioning(self, Bucket: str) -> dict:  # noqa: N803
        return {"Status": self._versioning}

    def get_object_lock_configuration(self, Bucket: str) -> dict:  # noqa: N803
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": self._lock_enabled}}

    def put_object(self, **kwargs) -> dict:
        self.objects[kwargs["Key"]] = {
            "Body": kwargs["Body"],
            "Metadata": kwargs.get("Metadata", {}),
            "ObjectLockMode": self._stored_mode,
            "ObjectLockRetainUntilDate": (
                kwargs["ObjectLockRetainUntilDate"] - self._retain_shortfall
            ),
        }
        return {"VersionId": self._version_id}

    def head_object(self, Bucket: str, Key: str, VersionId: str | None = None) -> dict:  # noqa: N803
        if Key not in self.objects:
            raise KeyError("404")
        return self.objects[Key]

    def get_object(self, Bucket: str, Key: str) -> dict:  # noqa: N803
        if Key not in self.objects:
            raise KeyError("404")
        obj = self.objects[Key]

        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        return {"Body": _Body(obj["Body"]), "Metadata": obj["Metadata"]}


def _payload() -> str:
    return _evidence().canonical_payload()


def test_write_persists_and_verifies_the_lock() -> None:
    s3 = _FakeS3()
    store = S3ObjectLockRetention(s3, "evidence-bucket")
    result = store.write("smoke-abc123", _payload(), {"git-sha": "a" * 40})
    assert result.success is True
    assert result.retention_status == "persisted"
    assert store.exists("smoke-abc123") is True
    assert store.verify_checksum("smoke-abc123") is True


def test_write_is_write_once() -> None:
    s3 = _FakeS3()
    store = S3ObjectLockRetention(s3, "evidence-bucket")
    assert store.write("smoke-abc123", _payload()).success is True
    second = store.write("smoke-abc123", _payload())
    assert second.success is False
    assert second.retention_status == "failed"
    assert "write-once" in (second.error or "")


def test_bucket_without_versioning_fails_closed() -> None:
    store = S3ObjectLockRetention(_FakeS3(versioning="Suspended"), "b")
    result = store.write("smoke-abc123", _payload())
    assert result.success is False
    assert "versioning" in (result.error or "")


def test_bucket_without_object_lock_fails_closed() -> None:
    store = S3ObjectLockRetention(_FakeS3(lock_enabled="Disabled"), "b")
    result = store.write("smoke-abc123", _payload())
    assert result.success is False
    assert "Object Lock" in (result.error or "")


def test_governance_mode_is_rejected() -> None:
    """A lock that an operator can delete is not retained evidence."""
    store = S3ObjectLockRetention(_FakeS3(stored_mode="GOVERNANCE"), "b")
    result = store.write("smoke-abc123", _payload())
    assert result.success is False
    assert "COMPLIANCE" in (result.error or "")


def test_short_retain_until_is_rejected() -> None:
    store = S3ObjectLockRetention(
        _FakeS3(retain_shortfall=timedelta(days=30)), "b"
    )
    result = store.write("smoke-abc123", _payload())
    assert result.success is False
    assert "retain-until" in (result.error or "")


def test_missing_version_id_is_rejected() -> None:
    store = S3ObjectLockRetention(_FakeS3(version_id=None), "b")
    result = store.write("smoke-abc123", _payload())
    assert result.success is False
    assert "VersionId" in (result.error or "")


def test_retention_floor_is_enforced_at_construction() -> None:
    with pytest.raises(ValueError, match="retention floor"):
        S3ObjectLockRetention(_FakeS3(), "b", retain_days=30)
    assert S3ObjectLockRetention(_FakeS3(), "b", retain_days=365) is not None


def test_invalid_evidence_id_is_rejected() -> None:
    store = S3ObjectLockRetention(_FakeS3(), "b")
    result = store.write("../escape", _payload())
    assert result.success is False
    assert result.error == "invalid evidence_id"


def test_absent_evidence_reads_as_none() -> None:
    store = S3ObjectLockRetention(_FakeS3(), "b")
    assert store.read("smoke-absent") is None
    assert store.exists("smoke-absent") is False
    assert store.verify_checksum("smoke-absent") is False


def test_bucket_is_required() -> None:
    with pytest.raises(ValueError, match="bucket is required"):
        S3ObjectLockRetention(_FakeS3(), "")


def test_retain_until_is_at_least_the_floor() -> None:
    s3 = _FakeS3()
    store = S3ObjectLockRetention(s3, "evidence-bucket")
    store.write("smoke-abc123", _payload())
    stored = s3.objects["controlled-pilot/smoke-abc123.json"]
    horizon = stored["ObjectLockRetainUntilDate"] - datetime.now(timezone.utc)
    assert horizon >= timedelta(days=364)

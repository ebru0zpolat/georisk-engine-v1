"""Tests for the data_source_operational readiness gate."""

from __future__ import annotations

from datetime import date

from app.core.data_source_operational_gate import (
    LicenceRecord,
    LiveRuntimeEvidence,
    RetentionPolicy,
    evaluate_data_source_operational,
    evaluate_sources_operational,
)

_SID = "gee_viirs_ntl"
_AS_OF = date(2026, 6, 1)


def _licence(**kw):
    base = dict(
        source_id=_SID, licence_id="gee-commercial-2026", licensor="Google",
        commercial_use=True, valid_from=date(2026, 1, 1), valid_until=date(2027, 1, 1),
    )
    base.update(kw)
    return LicenceRecord(**base)


def _evidence(**kw):
    base = dict(
        source_id=_SID, captured_at=date(2026, 5, 20), request_ref="req-1",
        sample_sha256="a" * 64, delivery_mode="live",
    )
    base.update(kw)
    return [LiveRuntimeEvidence(**base)]


def _retention(**kw):
    base = dict(source_id=_SID, retention_days=365, storage_location="s3://georisk/gee")
    base.update(kw)
    return RetentionPolicy(**base)


def _eval(**over):
    kw = dict(
        source_id=_SID, delivery_mode="live", licence=_licence(),
        live_evidence=_evidence(), retention=_retention(), as_of=_AS_OF,
    )
    kw.update(over)
    return evaluate_data_source_operational(**kw)


def test_operational_when_all_four_controls_met():
    v = _eval()
    assert v.operational is True
    assert v.reasons == []
    assert v.licence_ok and v.live_evidence_ok and v.retention_ok


def test_not_operational_when_delivery_not_live():
    v = _eval(delivery_mode="fallback")
    assert v.operational is False
    assert any("not 'live'" in r for r in v.reasons)


def test_not_operational_without_licence():
    v = _eval(licence=None)
    assert v.operational is False
    assert any("no commercial-use licence" in r for r in v.reasons)


def test_not_operational_when_licence_not_commercial():
    v = _eval(licence=_licence(commercial_use=False))
    assert v.operational is False
    assert any("commercial use" in r for r in v.reasons)


def test_not_operational_when_licence_expired():
    v = _eval(licence=_licence(valid_until=date(2026, 3, 1)))
    assert v.operational is False
    assert any("expired" in r for r in v.reasons)


def test_not_operational_without_live_evidence():
    v = _eval(live_evidence=[])
    assert v.operational is False
    assert any("no live-runtime evidence" in r for r in v.reasons)


def test_not_operational_when_evidence_stale():
    v = _eval(live_evidence=_evidence(captured_at=date(2025, 1, 1)))
    assert v.operational is False
    assert any("stale" in r for r in v.reasons)


def test_not_operational_when_evidence_future_dated():
    # captured_at after as_of → negative age → must not satisfy freshness.
    v = _eval(live_evidence=_evidence(captured_at=date(2026, 12, 1)))
    assert v.operational is False
    assert any("future-dated" in r for r in v.reasons)


def test_not_operational_when_hash_not_sha256():
    v = _eval(live_evidence=_evidence(sample_sha256="not-a-real-hash"))
    assert v.operational is False
    assert any("valid SHA-256" in r for r in v.reasons)


def test_operational_with_one_valid_sample_among_incomplete():
    evidence = [
        LiveRuntimeEvidence(_SID, date(2026, 5, 20), "req-good", "a" * 64, "live"),
        LiveRuntimeEvidence(_SID, date(2026, 5, 25), "req-bad", "   ", "live"),  # blank hash
    ]
    v = _eval(live_evidence=evidence)
    assert v.operational is True  # one valid, fingerprinted, fresh sample suffices


def test_not_operational_when_evidence_missing_hash():
    v = _eval(live_evidence=_evidence(sample_sha256="  "))
    assert v.operational is False
    assert any("provenance hash" in r for r in v.reasons)


def test_fallback_evidence_does_not_count():
    v = _eval(live_evidence=_evidence(delivery_mode="fallback"))
    assert v.operational is False
    assert any("no live-runtime evidence" in r for r in v.reasons)


def test_not_operational_without_retention():
    v = _eval(retention=None)
    assert v.operational is False
    assert any("no retention policy" in r for r in v.reasons)


def test_not_operational_when_retention_nonpositive():
    v = _eval(retention=_retention(retention_days=0))
    assert v.operational is False
    assert any("non-positive retention_days" in r for r in v.reasons)


def test_records_for_other_source_rejected():
    v = _eval(licence=_licence(source_id="other"), retention=_retention(source_id="other"))
    assert v.operational is False
    assert any("licence record is for" in r for r in v.reasons)
    assert any("retention policy is for" in r for r in v.reasons)


def test_verdict_serialises():
    d = _eval().to_dict()
    assert d["operational"] is True
    assert d["source_id"] == _SID


# ---- registry-wide aggregator ----

def test_delivery_mode_cds_api_key_counts_as_live(monkeypatch):
    from app.core import data_source_validation as dsv
    from app.core.data_source_registry import list_data_sources

    oras5 = next(e for e in list_data_sources() if e.delivery == "cds_zarr")
    monkeypatch.setattr(dsv.settings, "oras5_zarr_url", None, raising=False)
    monkeypatch.setattr(dsv.settings, "copernicus_cds_api_key", None, raising=False)
    assert dsv.delivery_mode_for(oras5) == "fallback"
    # A configured CDS API key drives a real cdsapi ORAS5 call → live.
    monkeypatch.setattr(dsv.settings, "copernicus_cds_api_key", "secret-key", raising=False)
    assert dsv.delivery_mode_for(oras5) == "live"


def test_aggregator_fail_closed_for_missing_records():
    verdicts = evaluate_sources_operational(
        delivery_mode_by_source={"gee_viirs_ntl": "fallback", "oras5_ocean": "live"},
        licences={"oras5_ocean": _licence(source_id="oras5_ocean")},
        evidence={"oras5_ocean": _evidence(source_id="oras5_ocean")},
        retentions={"oras5_ocean": _retention(source_id="oras5_ocean")},
        as_of=_AS_OF,
    )
    # gee has no records + fallback → not operational
    assert verdicts["gee_viirs_ntl"].operational is False
    # oras5 has all four + live → operational
    assert verdicts["oras5_ocean"].operational is True

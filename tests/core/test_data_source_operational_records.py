"""Tests for the operational records store + live-evidence capture."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.core.data_source_operational_records import (
    OperationalRecordsStore,
    append_evidence,
    capture_live_evidence,
    load_evidence,
    load_licences_and_retentions,
    sample_sha256,
)

_SID = "oras5_ocean"
_AS_OF = date(2026, 6, 1)


def test_sample_sha256_deterministic_and_order_independent():
    a = sample_sha256({"sst": 1.0, "sea_level": 2.0})
    b = sample_sha256({"sea_level": 2.0, "sst": 1.0})
    assert a == b and len(a) == 64


def test_capture_live_evidence_live_only():
    ev = capture_live_evidence(
        source_id=_SID, payload={"sst": 1.0}, request_ref="r", delivery_mode="live",
        captured_at=date(2026, 5, 20),
    )
    assert ev.delivery_mode == "live"
    assert ev.sample_sha256 == sample_sha256({"sst": 1.0})
    with pytest.raises(ValueError, match="only a real live fetch"):
        capture_live_evidence(source_id=_SID, payload={}, request_ref="r", delivery_mode="fallback")


def test_evidence_log_round_trip(tmp_path):
    log = tmp_path / "live_evidence.jsonl"
    ev = capture_live_evidence(
        source_id=_SID, payload={"x": 1}, request_ref="r", delivery_mode="live",
        captured_at=date(2026, 5, 20),
    )
    append_evidence(ev, path=log)
    append_evidence(ev, path=log)
    loaded = load_evidence(log)
    assert len(loaded[_SID]) == 2
    assert loaded[_SID][0].sample_sha256 == ev.sample_sha256


def test_load_evidence_missing_is_empty(tmp_path):
    assert load_evidence(tmp_path / "nope.jsonl") == {}


def test_load_licences_and_retentions(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "licences": [{
            "source_id": _SID, "licence_id": "L1", "licensor": "CMEMS",
            "commercial_use": True, "valid_from": "2026-01-01", "valid_until": "2027-01-01",
        }],
        "retentions": [{"source_id": _SID, "retention_days": 730, "storage_location": "s3://x"}],
    }))
    lic, ret = load_licences_and_retentions(cfg)
    assert lic[_SID].commercial_use is True
    assert ret[_SID].retention_days == 730


def test_load_config_missing_is_empty(tmp_path):
    lic, ret = load_licences_and_retentions(tmp_path / "nope.json")
    assert lic == {} and ret == {}


def test_store_verdicts_operational_when_records_complete(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "licences": [{
            "source_id": _SID, "licence_id": "L1", "licensor": "CMEMS",
            "commercial_use": True, "valid_from": "2026-01-01", "valid_until": "2027-01-01",
        }],
        "retentions": [{"source_id": _SID, "retention_days": 730, "storage_location": "s3://x"}],
    }))
    log = tmp_path / "ev.jsonl"
    append_evidence(
        capture_live_evidence(source_id=_SID, payload={"sst": 1.0}, request_ref="r",
                              delivery_mode="live", captured_at=date(2026, 5, 20)),
        path=log,
    )
    store = OperationalRecordsStore(config_path=cfg, evidence_log=log)
    verdicts = store.verdicts({_SID: "live"}, as_of=_AS_OF)
    assert verdicts[_SID].operational is True


def test_store_fail_closed_when_empty(tmp_path):
    store = OperationalRecordsStore(
        config_path=tmp_path / "none.json", evidence_log=tmp_path / "none.jsonl"
    )
    verdicts = store.verdicts({_SID: "live"}, as_of=_AS_OF)
    assert verdicts[_SID].operational is False
    assert any("licence" in r for r in verdicts[_SID].reasons)

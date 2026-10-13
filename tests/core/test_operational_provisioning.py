"""Tests for operational config validation + provisioning-status checklists."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.core.data_source_operational_gate import (
    LicenceRecord,
    LiveRuntimeEvidence,
    RetentionPolicy,
)
from app.core.data_source_operational_records import (
    OperationalRecordsStore,
    load_licences_and_retentions,
    provisioning_status,
    validate_operational_config,
)

_SID = "oras5_ocean"
_AS_OF = date(2026, 6, 1)
_KNOWN = {"oras5_ocean", "gee_viirs_ntl"}


def _write(tmp_path, obj):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(obj))
    return p


# --- validate_operational_config ---------------------------------------------

def test_validate_missing_file_is_clean(tmp_path):
    assert validate_operational_config(tmp_path / "nope.json", known_source_ids=_KNOWN) == []


def test_validate_clean_config(tmp_path):
    cfg = _write(tmp_path, {
        "licences": [{
            "source_id": _SID, "licence_id": "L1", "licensor": "CMEMS",
            "commercial_use": True, "valid_from": "2026-01-01", "valid_until": "2027-01-01",
        }],
        "retentions": [{"source_id": _SID, "retention_days": 730, "storage_location": "s3://x"}],
    })
    assert validate_operational_config(cfg, known_source_ids=_KNOWN) == []


def test_validate_flags_unknown_source_id(tmp_path):
    cfg = _write(tmp_path, {
        "licences": [{
            "source_id": "typo_source", "licence_id": "L1", "licensor": "X",
            "commercial_use": True, "valid_from": "2026-01-01",
        }],
        "retentions": [],
    })
    issues = validate_operational_config(cfg, known_source_ids=_KNOWN)
    assert any("not in the data-source registry" in i.message for i in issues)


def test_validate_flags_duplicate_and_bad_date_and_noncommercial(tmp_path):
    cfg = _write(tmp_path, {
        "licences": [
            {"source_id": _SID, "licence_id": "L1", "licensor": "X",
             "commercial_use": False, "valid_from": "2026-01-01"},
            {"source_id": _SID, "licence_id": "L2", "licensor": "X",
             "commercial_use": True, "valid_from": "not-a-date"},
        ],
        "retentions": [{"source_id": _SID, "retention_days": 0, "storage_location": ""}],
    })
    msgs = " ".join(str(i) for i in validate_operational_config(cfg, known_source_ids=_KNOWN))
    assert "duplicate licence" in msgs
    assert "commercial_use is false" in msgs
    assert "not an ISO date" in msgs
    assert "retention_days must be positive" in msgs
    assert "missing storage_location" in msgs


def test_validate_reports_invalid_json(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text("{ not json")
    issues = validate_operational_config(p, known_source_ids=_KNOWN)
    assert len(issues) == 1 and issues[0].section == "file"


def test_loader_fails_loud_on_malformed_row(tmp_path):
    cfg = _write(tmp_path, {"licences": [{"source_id": _SID}], "retentions": []})
    with pytest.raises(ValueError, match="licences\\[0\\].*malformed"):
        load_licences_and_retentions(cfg)


# --- provisioning_status ------------------------------------------------------

def _full_records():
    return (
        LicenceRecord(_SID, "L1", "CMEMS", True, date(2026, 1, 1), date(2027, 1, 1)),
        [LiveRuntimeEvidence(_SID, date(2026, 5, 20), "r", "a" * 64, "live")],
        RetentionPolicy(_SID, 730, "s3://x"),
    )


def test_provisioning_all_met_is_operational():
    lic, ev, ret = _full_records()
    st = provisioning_status(
        source_id=_SID, delivery_plane="cds_zarr", delivery_mode="live",
        licence=lic, evidence=ev, retention=ret, as_of=_AS_OF,
    )
    assert st.operational is True
    assert st.remaining == []


def test_provisioning_names_each_gap_with_next_action():
    st = provisioning_status(
        source_id=_SID, delivery_plane="cds_zarr", delivery_mode="fallback",
        licence=None, evidence=None, retention=None, as_of=_AS_OF,
    )
    assert st.operational is False
    by_name = {c.name: c for c in st.controls}
    # delivery gap → the credential hint for the plane.
    assert "ORAS5_ZARR_URL" in by_name["delivery_live"].next_action
    # licence/retention gaps → point at the config file.
    assert "LicenceRecord" in by_name["licence"].next_action
    assert "RetentionPolicy" in by_name["retention"].next_action
    # evidence gap while NOT live → cannot capture yet (needs credentials first).
    assert "once delivery is live" in by_name["live_evidence"].next_action


def test_provisioning_evidence_action_is_capture_when_live():
    lic, _, ret = _full_records()
    st = provisioning_status(
        source_id=_SID, delivery_plane="cds_zarr", delivery_mode="live",
        licence=lic, evidence=None, retention=ret, as_of=_AS_OF,
    )
    ev_control = {c.name: c for c in st.controls}["live_evidence"]
    assert not ev_control.ok
    assert "capture_live_evidence.py --source oras5_ocean" in ev_control.next_action


def test_provisioning_audit_plane_never_points_at_generic_capture():
    # gee_audit is not capturable via the generic seam: even when live, the
    # evidence action must NOT tell the operator to run capture_live_evidence.py
    # (it would fingerprint the production payload, not the audit dataset).
    st = provisioning_status(
        source_id="audit_landsat_thermal", delivery_plane="gee_audit",
        delivery_mode="live", licence=None, evidence=None, retention=None, as_of=_AS_OF,
    )
    ev = {c.name: c for c in st.controls}["live_evidence"]
    assert "capture_live_evidence.py" not in ev.next_action
    assert "dedicated audit" in ev.next_action


def test_store_provisioning_fail_closed_when_empty(tmp_path):
    store = OperationalRecordsStore(
        config_path=tmp_path / "none.json", evidence_log=tmp_path / "none.jsonl"
    )
    statuses = store.provisioning({_SID: ("cds_zarr", "fallback")}, as_of=_AS_OF)
    assert statuses[_SID].operational is False
    assert len(statuses[_SID].remaining) == 4  # all four controls unmet

"""Restart persistence and tamper detection for the file-backed audit trail."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.audit_trail import AppendOnlyAuditTrail, tip_hash_from_file


def _append(store: AppendOnlyAuditTrail, *, amount: float, label: str) -> str:
    rec = store.append(
        methodology_version="expected-loss-v0.3",
        valuation_date=date(2021, 7, 1),
        data_versions={"test": "v1"},
        parameters={"label": label},
        inputs={"label": label},
        outputs={"amount": amount},
    )
    return rec.record_id


def test_restart_persistence_chains_from_disk_tip(tmp_path: Path) -> None:
    """New process/instance must continue from the last on-disk record hash."""
    path = tmp_path / "restart_audit.jsonl"

    session_1 = AppendOnlyAuditTrail(path=path)
    first_id = _append(session_1, amount=100.0, label="start")
    first = session_1.get(first_id)
    assert first is not None
    tip_after_first = tip_hash_from_file(path)
    assert tip_after_first == first.record_hash

    # Simulate process restart: new store instance, same path, no in-memory tip.
    session_2 = AppendOnlyAuditTrail(path=path)
    assert session_2.tip_hash == first.record_hash
    second_id = _append(session_2, amount=200.0, label="stop")
    second = session_2.get(second_id)
    assert second is not None
    assert second.prev_hash == first.record_hash
    assert session_2.verify_chain() is True

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])
    assert entry2["prev_hash"] == entry1["record_hash"]

    reloaded = AppendOnlyAuditTrail(path=path)
    assert len(reloaded) == 2
    assert reloaded.verify_chain() is True


def test_verify_chain_detects_payload_tampering(tmp_path: Path) -> None:
    """Mutating a persisted record's outputs must break verify_chain on reload."""
    path = tmp_path / "tamper_audit.jsonl"
    store = AppendOnlyAuditTrail(path=path)
    _append(store, amount=100.0, label="a")
    _append(store, amount=200.0, label="b")
    assert store.verify_chain() is True

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    malicious = json.loads(lines[0])
    malicious["outputs"]["amount"] = 9999.0
    # Leave record_hash unchanged — classic silent rewrite.
    lines[0] = json.dumps(malicious, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # In-memory store still holds the pre-tamper records.
    assert store.verify_chain() is True

    # Disk is source of truth after restart / reload.
    reloaded = AppendOnlyAuditTrail(path=path)
    assert len(reloaded) == 2
    assert reloaded.verify_chain() is False


def test_verify_chain_detects_broken_prev_hash_link(tmp_path: Path) -> None:
    """Breaking prev_hash linkage between records must fail verification."""
    path = tmp_path / "broken_link.jsonl"
    store = AppendOnlyAuditTrail(path=path)
    _append(store, amount=1.0, label="a")
    _append(store, amount=2.0, label="b")

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    second = json.loads(lines[1])
    second["prev_hash"] = "f" * 64
    lines[1] = json.dumps(second, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    reloaded = AppendOnlyAuditTrail(path=path)
    assert reloaded.verify_chain() is False

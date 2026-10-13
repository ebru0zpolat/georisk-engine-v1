"""File-lock integrity: two stores on one path must form a single unbroken chain."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from app.services.audit_trail import AppendOnlyAuditTrail


def _append(store: AppendOnlyAuditTrail, label: str) -> str:
    rec = store.append(
        methodology_version="expected-loss-v0.2",
        valuation_date=date(2024, 12, 31),
        data_versions={"test": "v1"},
        parameters={"label": label},
        inputs={"n": label},
        outputs={"ok": True},
    )
    return rec.record_id


def test_interleaved_appends_from_two_stores_form_single_chain(tmp_path: Path) -> None:
    path = tmp_path / "shared.jsonl"
    store_a = AppendOnlyAuditTrail(path=path)
    store_b = AppendOnlyAuditTrail(path=path)

    n = 20
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = []
        for i in range(n):
            store = store_a if i % 2 == 0 else store_b
            futures.append(pool.submit(_append, store, f"w{i}"))
        ids = [f.result() for f in as_completed(futures)]

    assert len(ids) == n
    assert len(set(ids)) == n

    fresh = AppendOnlyAuditTrail(path=path)
    assert len(fresh) == n
    assert fresh.verify_chain() is True
    # Tip on disk matches last loaded record.
    assert fresh.tip_hash == fresh._records[-1].record_hash

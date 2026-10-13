"""Five-layer pipeline + hash-chained audit trail + EAL reproducibility."""

from __future__ import annotations

from datetime import date, datetime, timezone

from starlette.testclient import TestClient

from app.main import app
from app.schemas.adaptation import AdaptationOutcome, MeasureStatus
from app.schemas.five_layer import METHODOLOGY_VERSION
from app.schemas.portfolio import UniversalAsset
from app.services.audit_trail import AppendOnlyAuditTrail, reset_audit_trail_for_tests
from app.services.five_layer_pipeline import (
    recompute_eal_from_trail,
    run_five_layer,
)


def _sample_asset(**overrides: object) -> UniversalAsset:
    base = dict(
        asset_id="ANT-01",
        latitude=36.8969,
        longitude=30.7133,
        asset_value=3_500_000,
        building_type="hotel",
        use_class="tourism",
        construction_year=2005,
        floors=8,
        insurance_coverage=1_000_000,
        existing_adaptation_measures=["shutters"],
        adaptation=AdaptationOutcome(
            measure_status=MeasureStatus.recommended,
            share_outcome_consented=False,
            anonymise_in_aggregate=True,
        ),
    )
    base.update(overrides)
    return UniversalAsset(**base)  # type: ignore[arg-type]


def test_five_layer_writes_audit_trail_fields() -> None:
    trail = AppendOnlyAuditTrail()
    result = run_five_layer(
        _sample_asset(),
        date(2021, 7, 1),
        parameters={"scenario": "ssp245"},
        trail=trail,
        timestamp=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
    )
    assert result.methodology_version == METHODOLOGY_VERSION
    assert result.financial.eal_absolute >= 0
    assert result.financial.eal_pct_of_value >= 0
    assert result.financial.scenario_deltas == {}
    assert result.adaptation.recommended_measure_id is not None
    assert result.audit_record_id.startswith("atr_")

    record = trail.get(result.audit_record_id)
    assert record is not None
    assert record.methodology_version == METHODOLOGY_VERSION
    assert record.valuation_date == date(2021, 7, 1)
    assert "hazard_stub" in record.data_versions
    assert record.parameters["scenario"] == "ssp245"
    assert record.outputs["eal_absolute"] == result.financial.eal_absolute
    assert record.timestamp is not None
    assert trail.verify_chain()


def test_audit_trail_hash_chain_links_records() -> None:
    """Each five-layer run appends EAL + pipeline records; chain must stay intact."""
    trail = AppendOnlyAuditTrail()
    r1 = run_five_layer(_sample_asset(asset_id="A"), date(2020, 1, 1), trail=trail)
    r2 = run_five_layer(_sample_asset(asset_id="B"), date(2020, 1, 1), trail=trail)
    assert r1.audit_record_id != r2.audit_record_id
    assert trail.get(r1.audit_record_id) is not None
    assert trail.get(r2.audit_record_id) is not None
    # At least one EAL record precedes each pipeline summary record.
    assert len(trail) >= 4
    assert trail.verify_chain()


def test_recompute_eal_from_trail_equals_original() -> None:
    """Reproducibility: any EAL can be recomputed from its trail record."""
    trail = AppendOnlyAuditTrail()
    result = run_five_layer(
        _sample_asset(),
        date(2019, 12, 31),
        parameters={"pack": "pack-tr"},
        trail=trail,
    )
    recomputed = recompute_eal_from_trail(result.audit_record_id, trail=trail)
    assert recomputed == result.financial.eal_absolute
    record = trail.get(result.audit_record_id)
    assert record is not None
    assert recomputed == record.outputs["eal_absolute"]


def test_recompute_is_deterministic_across_runs() -> None:
    trail = AppendOnlyAuditTrail()
    asset = _sample_asset()
    vdate = date(2022, 6, 15)
    a = run_five_layer(asset, vdate, trail=trail)
    b = run_five_layer(asset, vdate, trail=trail)
    assert a.financial.eal_absolute == b.financial.eal_absolute
    assert recompute_eal_from_trail(a.audit_record_id, trail=trail) == a.financial.eal_absolute
    assert recompute_eal_from_trail(b.audit_record_id, trail=trail) == b.financial.eal_absolute


def test_post_portfolio_analyze_endpoint() -> None:
    reset_audit_trail_for_tests()
    client = TestClient(app)
    r = client.post(
        "/v1/portfolio/analyze",
        json={
            "valuation_date": "2021-07-28",
            "parameters": {"demo": True},
            "asset": {
                "asset_id": "IST-01",
                "latitude": 41.01,
                "longitude": 28.97,
                "asset_value": 2_000_000,
                "building_type": "office",
                "use_class": "commercial",
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()["result"]
    assert body["methodology_version"] == METHODOLOGY_VERSION
    assert body["financial"]["eal_absolute"] >= 0
    assert body["audit_record_id"]
    # With a database the run is persisted: the record lives in the DB audit
    # store, sealed to the caller's organisation, and a run id is returned.
    assert r.json()["run_id"]
    import asyncio

    from app.core.security import DEFAULT_ORGANISATION_ID
    from app.db.session import get_session_factory
    from app.storage.audit_trail_store import PostgresAuditTrailStore

    record = asyncio.run(
        PostgresAuditTrailStore(get_session_factory()).get(
            body["audit_record_id"], organisation_id=DEFAULT_ORGANISATION_ID
        )
    )
    assert record is not None

    class _OneRecordTrail:
        def get(self, record_id):
            return record if record_id == record.record_id else None

    assert recompute_eal_from_trail(body["audit_record_id"], trail=_OneRecordTrail()) == body[
        "financial"
    ]["eal_absolute"]

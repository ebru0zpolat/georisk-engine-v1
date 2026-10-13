"""WP-4: per-result source manifest — states, licence gate, trail integration.

Four states are exercised end to end (live/fixture/degraded/blocked), plus the
acceptance rule that a blocked source is still *listed* but feeds no number.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core import error_codes as codes
from app.core.data_source_operational_gate import LicenceRecord
from app.core.data_source_registry import list_data_sources
from app.pipeline.contract import PipelineContext
from app.schemas.portfolio import UniversalAsset
from app.schemas.source_manifest import (
    REAL_DATA_STATES,
    SourceLicenceNotVerifiedError,
    SourceManifest,
    SourceRecord,
    apply_licence_gate,
    state_for_delivery_mode,
)
from app.services.audit_trail import AppendOnlyAuditTrail
from app.services import source_manifest as source_manifest_service
from app.services.evidence_service import synthetic_inputs
from app.services.five_layer_pipeline import run_five_layer
from app.services.source_manifest import (
    build_result_manifest,
    licence_state_for,
    records_from_data_versions,
    registry_source_records,
)


def _rec(source_id: str, *, state: str, licence: str) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        licence_state=licence,  # type: ignore[arg-type]
        state=state,  # type: ignore[arg-type]
    )


# --- states -----------------------------------------------------------------


def test_four_states_round_trip() -> None:
    states = {"live", "fixture", "degraded", "blocked"}
    records = [
        _rec("gee_viirs_ntl", state="live", licence="verified"),
        _rec("psmsl", state="fixture", licence="not_applicable"),
        _rec("era5", state="degraded", licence="verified"),
        _rec("oras5_ocean", state="blocked", licence="unverified"),
    ]
    manifest = SourceManifest(records=records)
    payload = manifest.to_payload()
    restored = SourceManifest.from_payload(payload)
    assert {r.state for r in restored.records} == states
    for record in records:
        assert record.model_dump(mode="json") in manifest.to_payload()
    assert REAL_DATA_STATES == {"live", "fixture", "degraded"}


def test_state_for_delivery_mode_is_fail_closed() -> None:
    assert state_for_delivery_mode("live") == "live"
    assert state_for_delivery_mode("mock") == "synthetic"
    assert state_for_delivery_mode("stub") == "synthetic"
    assert state_for_delivery_mode("fallback") == "synthetic"
    assert state_for_delivery_mode("something-new") == "degraded"


# --- licence gate -----------------------------------------------------------


def test_gate_blocks_unverified_real_data_but_keeps_synthetic() -> None:
    records = [
        _rec("gee_viirs_ntl", state="live", licence="unverified"),
        _rec("hazard_stub", state="synthetic", licence="not_applicable"),
    ]
    manifest = apply_licence_gate(records)
    blocked = manifest.get("gee_viirs_ntl")
    assert blocked is not None and blocked.state == "blocked"
    assert blocked.blocked_reason
    # Synthetic own-curves are exempt — they are labelled, not licensed.
    assert manifest.get("hazard_stub") is not None
    assert manifest.get("hazard_stub").state == "synthetic"  # type: ignore[union-attr]


def test_gate_leaves_verified_live_untouched() -> None:
    manifest = apply_licence_gate([_rec("oras5_ocean", state="live", licence="verified")])
    assert manifest.get("oras5_ocean").state == "live"  # type: ignore[union-attr]


def test_gate_does_not_mutate_input() -> None:
    record = _rec("gee_viirs_ntl", state="live", licence="unverified")
    apply_licence_gate([record])
    assert record.state == "live"


def test_licence_state_for_is_fail_closed() -> None:
    as_of = date(2026, 6, 1)
    assert licence_state_for("x", licences=None, as_of=as_of) == "unverified"
    no_commercial = LicenceRecord(
        source_id="x",
        licence_id="L1",
        licensor="v",
        commercial_use=False,
        valid_from=date(2020, 1, 1),
    )
    assert licence_state_for("x", licences={"x": no_commercial}, as_of=as_of) == "unverified"
    future = LicenceRecord(
        source_id="x",
        licence_id="L1",
        licensor="v",
        commercial_use=True,
        valid_from=date(2027, 1, 1),
    )
    assert licence_state_for("x", licences={"x": future}, as_of=as_of) == "unverified"
    valid = LicenceRecord(
        source_id="x",
        licence_id="L1",
        licensor="v",
        commercial_use=True,
        valid_from=date(2020, 1, 1),
        valid_until=date(2030, 1, 1),
    )
    assert licence_state_for("x", licences={"x": valid}, as_of=as_of) == "verified"


# --- registry builder -------------------------------------------------------


def test_registry_source_records_blocks_unlicensed_production() -> None:
    records = registry_source_records(as_of=date(2026, 6, 1))
    production = list_data_sources(tier="production")
    assert len(records) == len(production)
    assert records, "expected at least one production source in the registry"
    assert all(r.state == "blocked" for r in records)
    assert all(r.licence_state == "unverified" for r in records)


def test_registry_source_records_verified_becomes_live() -> None:
    production = list_data_sources(tier="production")
    target = production[0]
    licence = LicenceRecord(
        source_id=target.id,
        licence_id="L1",
        licensor="v",
        commercial_use=True,
        valid_from=date(2020, 1, 1),
    )
    records = registry_source_records(
        licences={target.id: licence},
        as_of=date(2026, 6, 1),
        delivery_mode_by_source={target.id: "live"},
    )
    rec = next(r for r in records if r.source_id == target.id)
    assert rec.state == "live" and rec.licence_state == "verified"
    # Every other production source stays blocked.
    assert all(
        r.state == "blocked" for r in records if r.source_id != target.id
    )


def test_state_for_delivery_mode_unknown_defaults_degraded() -> None:
    assert state_for_delivery_mode("nonsense") == "degraded"


# --- five-layer integration (acceptance) ------------------------------------


def _sample_asset() -> UniversalAsset:
    return UniversalAsset(
        asset_id="WP4-01",
        latitude=36.8969,
        longitude=30.7133,
        asset_value=2_500_000,
        building_type="hotel",
        use_class="tourism",
        construction_year=2008,
        floors=6,
        insurance_coverage=500_000,
    )


def test_five_layer_record_carries_manifest_including_blocked() -> None:
    trail = AppendOnlyAuditTrail()
    result = run_five_layer(
        _sample_asset(), date(2021, 7, 1), trail=trail
    )
    record = trail.get(result.audit_record_id)
    assert record is not None
    manifest = SourceManifest.from_payload(record.sources)
    assert manifest.records, "five-layer record must carry a source manifest"

    # (1) every production registry source is listed…
    production_ids = {e.id for e in list_data_sources(tier="production")}
    listed_ids = {r.source_id for r in manifest.records}
    assert production_ids <= listed_ids
    # …and (unlicensed) blocked — named, not silently dropped.
    assert manifest.blocked()
    assert all("licence" in (r.blocked_reason or "") for r in manifest.blocked())

    # (2) a blocked source feeds no number: only synthetic curves contribute.
    assert manifest.contributing()
    assert all(r.state == "synthetic" for r in manifest.contributing())
    assert all(not r.is_blocked() for r in manifest.contributing())


def test_five_layer_manifest_survives_chain_verify() -> None:
    trail = AppendOnlyAuditTrail()
    run_five_layer(_sample_asset(), date(2021, 7, 1), trail=trail)
    run_five_layer(_sample_asset(), date(2021, 7, 1), trail=trail)
    assert trail.verify_chain()


def test_blocked_caller_source_that_feeds_a_number_refuses_before_computing() -> None:
    """Codex #227: the gate runs before any layer, so no number is computed or sealed."""
    trail = AppendOnlyAuditTrail()
    provided = [
        SourceRecord(
            source_id="gee_viirs_ntl",
            state="live",
            licence_state="unverified",
            used_for=["hazard"],
        )
    ]
    with pytest.raises(SourceLicenceNotVerifiedError) as excinfo:
        run_five_layer(_sample_asset(), date(2021, 7, 1), trail=trail, sources=provided)
    assert excinfo.value.code == codes.SOURCE_LICENCE_NOT_VERIFIED
    assert excinfo.value.source_ids == ["gee_viirs_ntl"]
    # The EAL step writes its own record; an empty trail proves nothing was computed.
    assert len(trail) == 0


def test_blocked_caller_source_without_a_use_is_listed_and_the_run_proceeds() -> None:
    trail = AppendOnlyAuditTrail()
    provided = [
        SourceRecord(source_id="gee_viirs_ntl", state="live", licence_state="unverified")
    ]
    result = run_five_layer(_sample_asset(), date(2021, 7, 1), trail=trail, sources=provided)
    record = trail.get(result.audit_record_id)
    assert record is not None
    rec = SourceManifest.from_payload(record.sources).get("gee_viirs_ntl")
    assert rec is not None and rec.is_blocked() and rec.used_for == []


def test_a_caller_cannot_claim_a_licence_the_register_does_not_hold() -> None:
    """The licence register is the only licence truth: a caller's 'verified' is ignored."""
    trail = AppendOnlyAuditTrail()
    provided = [
        SourceRecord(
            source_id="gee_viirs_ntl", state="live", licence_state="verified", used_for=["hazard"]
        )
    ]
    with pytest.raises(SourceLicenceNotVerifiedError):
        run_five_layer(_sample_asset(), date(2021, 7, 1), trail=trail, sources=provided)
    assert len(trail) == 0


def test_caller_record_replaces_the_registry_placeholder_when_licensed() -> None:
    licence = LicenceRecord(
        source_id="gee_viirs_ntl",
        licence_id="L-1",
        licensor="v",
        commercial_use=True,
        valid_from=date(2020, 1, 1),
    )
    manifest = build_result_manifest(
        data_versions={},
        licences={"gee_viirs_ntl": licence},
        as_of=date(2026, 6, 1),
        extra_records=[
            SourceRecord(source_id="gee_viirs_ntl", state="live", used_for=["hazard"])
        ],
    )
    matching = [r for r in manifest.records if r.source_id == "gee_viirs_ntl"]
    assert len(matching) == 1, "one record per source"
    assert matching[0].state == "live" and matching[0].used_for == ["hazard"]
    assert matching[0].licence_state == "verified"


def test_a_caller_cannot_exempt_a_source_by_calling_it_synthetic() -> None:
    """Codex #228: a caller-declared ``synthetic`` state is not a licence exemption."""
    trail = AppendOnlyAuditTrail()
    provided = [SourceRecord(source_id="gee_viirs_ntl", state="synthetic", used_for=["hazard"])]
    with pytest.raises(SourceLicenceNotVerifiedError):
        run_five_layer(_sample_asset(), date(2021, 7, 1), trail=trail, sources=provided)
    assert len(trail) == 0


def test_run_gate_reads_the_operator_licence_register(monkeypatch) -> None:
    """Codex #228: a licence recorded in the register lets a real source through."""
    licence = LicenceRecord(
        source_id="gee_viirs_ntl",
        licence_id="L-1",
        licensor="v",
        commercial_use=True,
        valid_from=date(2020, 1, 1),
    )
    monkeypatch.setattr(
        source_manifest_service,
        "load_licences_and_retentions",
        lambda: ({"gee_viirs_ntl": licence}, {}),
    )
    trail = AppendOnlyAuditTrail()
    provided = [SourceRecord(source_id="gee_viirs_ntl", state="live", used_for=["hazard"])]
    result = run_five_layer(_sample_asset(), date(2021, 7, 1), trail=trail, sources=provided)
    rec = SourceManifest.from_payload(trail.get(result.audit_record_id).sources).get("gee_viirs_ntl")
    assert rec is not None and (rec.state, rec.licence_state) == ("live", "verified")


# --- data_versions classification -------------------------------------------


def test_internal_curves_and_labelled_versions_are_synthetic() -> None:
    records = records_from_data_versions(
        {
            "damage_curves": "stub_global_mdr-v0.2.0",
            "vulnerability_curves": "vuln-curves-v0.1",
            "seismic_pga": "seismic-pga-synthetic-v0.1",
            "heat_method": "SYNTHETIC-FIXTURE-heat-v0.1",
        }
    )
    assert {r.state for r in records} == {"synthetic"}
    assert {r.licence_state for r in records} == {"not_applicable"}


def test_curve_catalogues_are_classified_by_their_label_not_their_key() -> None:
    """Codex #228: a vendored (real) catalogue must not be sealed as synthetic."""
    by_id = {
        r.source_id: r
        for r in records_from_data_versions(
            {"damage_curves": "stub_global_mdr-v0.2.0", "depth_damage": "jrc_global_depth_damage-v1.0"}
        )
    }
    assert by_id["damage_curves"].state == "synthetic"
    assert (by_id["depth_damage"].state, by_id["depth_damage"].licence_state) == (
        "unclassified",
        "unverified",
    )


def test_real_provenance_stamps_are_unclassified_not_synthetic() -> None:
    """Codex #227: real provenance must not be presented as licence-exempt synthetic."""
    stamps = {
        "elevation": "merit-dem-proxy-v0.1",
        "era5_temperature": "era5-temperature-proxy-v0.1",
        "seismic_pga": "seismic-pga:USGS",
        "hazard_snapshot_sha256": "ab" * 32,
    }
    records = records_from_data_versions(stamps)
    assert {r.source_id for r in records} == set(stamps)
    for record in records:
        assert record.state == "unclassified", record.source_id
        assert record.licence_state == "unverified"
        assert not record.is_blocked()
    gated = apply_licence_gate(records)
    assert {r.state for r in gated.records} == {"unclassified"}


def test_unclassified_and_fixture_versions_surface_in_evidence_limits() -> None:
    payload = {
        "sources": [
            r.model_dump(mode="json")
            for r in records_from_data_versions(
                {"elevation": "merit-dem-proxy-v0.1", "flood_map": "nl-map-fixture-v0.1"}
            )
        ]
    }
    listed = {item["source"] for item in synthetic_inputs(payload)}
    assert listed == {"flood_map"}, "a fixture-labelled version must stay a synthetic input"


def test_build_result_manifest_include_registry_false() -> None:
    manifest = build_result_manifest(
        data_versions={"hazard_stub": "hazard-stub-v0.1"},
        include_registry=False,
    )
    assert [r.source_id for r in manifest.records] == ["hazard_stub"]
    assert all(r.state == "synthetic" for r in manifest.records)


# --- pipeline context -------------------------------------------------------


def test_pipeline_context_accepts_sources() -> None:
    ctx = PipelineContext(
        asset=_sample_asset(),
        valuation_date=date(2021, 7, 1),
        sources=[SourceRecord(source_id="hazard_stub", state="synthetic")],
    )
    assert ctx.sources and ctx.sources[0].source_id == "hazard_stub"

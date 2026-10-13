"""Deterministic builder, route-conditional files, sealing and pack-diff."""

from __future__ import annotations

import json

import factories as f
import pytest

from app.packs.tr.sustainable_finance.builder import (
    PackSealError,
    build_pack,
    pack_diff,
)
from app.packs.tr.sustainable_finance.physical_risk import RecalculationBridge
from app.packs.tr.sustainable_finance.routes import ExternalReviewType, PackStatus
from app.packs.tr.sustainable_finance.schemas import ExternalReviewRef


# --- Route-conditional file inclusion --------------------------------------------------


def test_use_of_proceeds_bundle_omits_sll_files() -> None:
    built = build_pack(f.valid_uop_pack())
    names = set(built.files)
    assert "project-register.json" in names
    assert "impact-metrics.json" in names
    assert "kpi-register.json" not in names
    assert "spt-register.json" not in names


def test_sustainability_linked_bundle_omits_uop_files() -> None:
    built = build_pack(f.valid_sll_pack())
    names = set(built.files)
    assert "kpi-register.json" in names
    assert "spt-register.json" in names
    assert "project-register.json" not in names
    assert "impact-metrics.json" not in names


def test_bundle_always_has_manifest_and_audit_files() -> None:
    built = build_pack(f.valid_sll_pack())
    for required in (
        "manifest.json",
        "executive-summary.md",
        "claims-register.json",
        "data-lineage.json",
        "audit/run-index.json",
        "audit/hashes.sha256",
        "audit/change-log.json",
    ):
        assert required in built.files


# --- Determinism / reproducibility (spec §16.1) ----------------------------------------


def test_same_input_reproduces_identical_files_and_hashes() -> None:
    a = build_pack(f.valid_sll_pack())
    b = build_pack(f.valid_sll_pack())
    assert a.files == b.files
    assert a.hashes == b.hashes
    assert a.manifest_sha256 == b.manifest_sha256


def test_manifest_hash_embedded_and_excludes_itself() -> None:
    built = build_pack(f.valid_uop_pack())
    manifest = json.loads(built.files["manifest.json"])
    assert manifest["manifest_sha256"] == built.manifest_sha256
    # The hash is over the manifest without its own hash slot -> stable & non-empty.
    assert len(built.manifest_sha256) == 64


def test_hashes_file_lists_every_other_file() -> None:
    built = build_pack(f.valid_sll_pack())
    listed = {
        line.split("  ", 1)[1]
        for line in built.files["audit/hashes.sha256"].splitlines()
        if line.strip()
    }
    expected = set(built.files) - {"audit/hashes.sha256"}
    assert listed == expected


# --- Sealing (fail closed) -------------------------------------------------------------


def test_seal_reviewer_ready_succeeds_when_clean() -> None:
    built = build_pack(f.valid_sll_pack())
    assert built.reviewer_ready
    assert built.release_result.reviewer_ready
    assert built.claim_scan.ok


def test_seal_raises_when_release_gates_block() -> None:
    pack = f.valid_sll_pack()
    pack.kpis[0].is_pure_external_hazard = True  # KPI gate fails
    with pytest.raises(PackSealError) as exc:
        build_pack(pack)
    assert any("admission gate" in r for r in exc.value.reasons)


def test_seal_raises_on_missing_licence() -> None:
    pack = f.valid_uop_pack()
    pack.provenance[0].licence = None
    with pytest.raises(PackSealError):
        build_pack(pack)


def test_draft_status_builds_without_raising_even_if_blocked() -> None:
    # Below reviewer_ready, the builder still renders (with the gate report) and does not seal.
    pack = f.valid_sll_pack(status=PackStatus.draft)
    pack.provenance[0].licence = None
    built = build_pack(pack)
    assert not built.reviewer_ready
    assert not built.release_result.reviewer_ready


# --- Pack diff -------------------------------------------------------------------------


def test_pack_diff_detects_changed_and_stable_files() -> None:
    base = build_pack(f.valid_uop_pack())

    changed_pack = f.valid_uop_pack()
    changed_pack.projects[0].objective = "different objective text"
    changed = build_pack(changed_pack)

    diff = pack_diff(base.hashes, changed.hashes)
    assert "project-register.json" in diff["changed"]
    # Files unrelated to the project change should not appear as changed.
    assert "responsibility-matrix.json" not in diff["changed"]
    assert diff["added"] == [] and diff["removed"] == []


def test_pack_diff_detects_added_and_removed_by_route() -> None:
    uop = build_pack(f.valid_uop_pack())
    sll = build_pack(f.valid_sll_pack())
    diff = pack_diff(uop.hashes, sll.hashes)
    assert "kpi-register.json" in diff["added"]
    assert "project-register.json" in diff["removed"]


# --- Constant-hazard / recalculation bridge in the bundle ------------------------------


def test_recalculation_bridge_recorded_in_change_log() -> None:
    pack = f.valid_sll_pack()
    pack.recalculation_bridges = [
        RecalculationBridge(
            from_methodology_version="resilience-v1",
            to_methodology_version="resilience-v2",
            reason="cadastre dataset upgrade",
            original_value=42.0,
            restated_value=43.5,
            original_result_reproducible=True,
            original_run_id="run-1",
        )
    ]
    built = build_pack(pack)
    change_log = json.loads(built.files["audit/change-log.json"])
    assert len(change_log) == 1
    assert change_log[0]["to_methodology_version"] == "resilience-v2"


def test_invalid_recalculation_bridge_blocks_seal() -> None:
    pack = f.valid_sll_pack()
    pack.recalculation_bridges = [
        RecalculationBridge(
            from_methodology_version="v1",
            to_methodology_version="v2",
            reason="upgrade",
            original_value=1.0,
            restated_value=2.0,
            original_result_reproducible=False,  # silent overwrite -> blocks
            original_run_id="run-1",
        )
    ]
    with pytest.raises(PackSealError) as exc:
        build_pack(pack)
    assert any("recalculation bridge invalid" in r for r in exc.value.reasons)


# --- Claim scan wired into the build ---------------------------------------------------


def test_build_claim_scan_is_clean_for_valid_pack() -> None:
    built = build_pack(f.valid_uop_pack())
    assert built.claim_scan.ok, built.claim_scan.summary()


def test_prohibited_claim_in_json_field_blocks_seal() -> None:
    pack = f.valid_uop_pack()
    pack.projects[0].objective = "CMB compliant"  # prohibited wording in a JSON value
    with pytest.raises(PackSealError):
        build_pack(pack)


# --- Post-review lifecycle states require documentary evidence (spec §12) ---------------


def test_verification_received_requires_verification_document() -> None:
    pack = f.valid_sll_pack(status=PackStatus.verification_received)
    with pytest.raises(PackSealError) as exc:
        build_pack(pack)
    assert any("verification external-review" in r for r in exc.value.reasons)


def test_verification_received_seals_with_verification_document() -> None:
    pack = f.valid_sll_pack(status=PackStatus.verification_received)
    pack.external_reviews = [
        ExternalReviewRef(
            review_type=ExternalReviewType.verification,
            provider_name="Audit Firm Ltd",
            document_ref="VER-2026-1",
        )
    ]
    built = build_pack(pack)
    assert built.reviewer_ready


def test_second_party_opinion_received_requires_spo_document() -> None:
    pack = f.valid_sll_pack(status=PackStatus.second_party_opinion_received)
    with pytest.raises(PackSealError) as exc:
        build_pack(pack)
    assert any("second_party_opinion external-review" in r for r in exc.value.reasons)


def test_issuer_approved_requires_approval_reference() -> None:
    pack = f.valid_sll_pack(status=PackStatus.issuer_approved)
    pack.manifest.authorised_body_decision_ref = None
    with pytest.raises(PackSealError) as exc:
        build_pack(pack)
    assert any("issuer_approved requires" in r for r in exc.value.reasons)

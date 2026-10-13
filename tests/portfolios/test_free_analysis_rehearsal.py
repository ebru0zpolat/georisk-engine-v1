"""Send-gate rehearsal for the free 20–50 asset analysis (TSKB / Anadolu Sigorta packet §0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.rehearse_free_analysis_pack import (
    OFFER_MAX_ASSETS,
    ROOT,
    RehearsalError,
    rehearse,
    resolve_trail_path,
)


def test_trail_path_is_required() -> None:
    with pytest.raises(RehearsalError, match="required"):
        resolve_trail_path(None)
    with pytest.raises(RehearsalError, match="required"):
        resolve_trail_path("   ")


def test_trail_path_inside_repo_is_refused() -> None:
    with pytest.raises(RehearsalError, match="inside the repository"):
        resolve_trail_path(str(ROOT / "data" / "audit_trail" / "x.jsonl"))


def test_trail_path_outside_repo_is_accepted(tmp_path: Path) -> None:
    assert resolve_trail_path(str(tmp_path / "trail.jsonl")) == (tmp_path / "trail.jsonl").resolve()


def test_max_assets_outside_offer_band_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RehearsalError, match="offer band"):
        rehearse(trail_path=tmp_path / "trail.jsonl", max_assets=OFFER_MAX_ASSETS + 1)
    with pytest.raises(RehearsalError, match="offer band"):
        rehearse(trail_path=tmp_path / "trail.jsonl", max_assets=19)


def test_rehearsal_verifies_every_asset_and_satisfies_send_gate(tmp_path: Path) -> None:
    trail = tmp_path / "outside" / "audit_trail.jsonl"
    record = rehearse(trail_path=trail, max_assets=20)

    assert record["trail_outside_repo"] is True
    assert record["portfolio_source"] == "golden-antalya"
    assert record["coverage"]["analyzed_count"] == 20
    iv = record["independent_verification"]
    assert iv["assets_verified"] == 20
    assert iv["failures"] == 0
    assert {row["agreement"] for row in iv["assets"]} == {"PASS"}
    assert record["featured_verification"]["agreement"] == "PASS"
    assert record["release_manifest"]["decision"] == "demo_only"
    assert record["release_manifest"]["production_eligible"] is False
    assert record["send_gate_satisfied"] is True

    # Artefacts landed next to the out-of-repo trail, never in the checkout.
    out = record["artefacts_outside_repo"]
    assert Path(out["trail_path"]).is_file()
    assert Path(out["pack_path"]).is_file()
    assert Path(out["release_manifest_path"]).is_file()
    assert not Path(out["trail_path"]).resolve().is_relative_to(ROOT.resolve())

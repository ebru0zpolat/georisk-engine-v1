"""Validation evidence trail: divergence classification, Erdemir trail, exports."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.reports.validation_summary import build_validation_summary_markdown
from app.schemas.validation import DivergenceFlag, EvidenceTrail
from app.services.validation_service import (
    ValidationService,
    classify,
    signed_divergence_pct,
)

_FIXED_TS = datetime(2025, 5, 3, tzinfo=timezone.utc)


def test_signed_divergence_pct() -> None:
    assert signed_divergence_pct(110.0, 100.0) == 10.0
    assert signed_divergence_pct(90.0, 100.0) == -10.0
    # Missing side or zero signal → no meaningful ratio.
    assert signed_divergence_pct(None, 100.0) is None
    assert signed_divergence_pct(100.0, None) is None
    assert signed_divergence_pct(100.0, 0.0) is None


def test_classify_threshold_bands() -> None:
    assert classify(10.0) is DivergenceFlag.GREEN
    assert classify(-15.0) is DivergenceFlag.GREEN
    assert classify(25.0) is DivergenceFlag.AMBER
    assert classify(40.0) is DivergenceFlag.AMBER
    assert classify(50.0) is DivergenceFlag.RED


def test_classify_directional_and_gaps() -> None:
    # Small magnitude but directionally inconsistent → amber, not green.
    assert classify(5.0, directionally_consistent=False) is DivergenceFlag.AMBER
    # Large + inconsistent → red.
    assert classify(30.0, directionally_consistent=False) is DivergenceFlag.RED
    # No independent signal → no_signal.
    assert classify(None, has_signal=False) is DivergenceFlag.NO_SIGNAL
    # Signal present but nothing comparable to diff → data gap → amber.
    assert classify(None, has_signal=True) is DivergenceFlag.AMBER


def test_erdemir_trail_min_eight_fields_and_versions() -> None:
    trail = ValidationService().build_erdemir_trail(generated_at=_FIXED_TS)
    assert isinstance(trail, EvidenceTrail)
    assert trail.case_id == "erdemir_2024"
    assert len(trail.records) >= 8
    # GeoRisk version + data source version present on every record.
    for rec in trail.records:
        assert rec.georisk_version
        assert rec.georisk_signal.source_version
        assert 0.0 <= rec.georisk_signal.confidence <= 1.0
    # Unique validation ids.
    ids = [r.validation_id for r in trail.records]
    assert len(ids) == len(set(ids))


def test_erdemir_known_divergences() -> None:
    by_id = {r.validation_id: r for r in ValidationService().build_erdemir_trail(generated_at=_FIXED_TS).records}
    # 2025 intensity: within ±15% but 2024→2025 basis change blocks the trend read → amber.
    intensity = by_id["ERD-2024-INT-001"]
    assert intensity.divergence_pct == 4.67
    assert intensity.flag is DivergenceFlag.AMBER
    # CBAM EBITDA ratio within Erdemir's own band → green.
    assert by_id["ERD-2024-CBAM-001"].flag is DivergenceFlag.GREEN
    # Location decomposition has no comparable reported value → amber gap.
    assert by_id["ERD-2024-WATER-003"].divergence_pct is None
    assert by_id["ERD-2024-WATER-003"].flag is DivergenceFlag.AMBER


def test_export_json_and_markdown(tmp_path) -> None:
    service = ValidationService()
    trail = service.build_erdemir_trail(generated_at=_FIXED_TS)

    json_path = service.export_trail_json(trail, path=tmp_path / "ev.json")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["case_id"] == "erdemir_2024"
    assert len(data["records"]) == len(trail.records)
    assert data["records"][0]["georisk_version"]

    md_path = service.export_summary_markdown(trail, path=tmp_path / "ev.md")
    md = md_path.read_text(encoding="utf-8")
    assert "GeoRisk Validation Evidence" in md
    assert "Flag rollup" in md
    # Tonnage renders with separators, not scientific notation.
    assert "8,089,587" in md
    assert "e+0" not in md


def test_summary_counts_cover_all_flags() -> None:
    trail = ValidationService().build_erdemir_trail(generated_at=_FIXED_TS)
    counts = trail.summary_counts()
    assert set(counts) == {f.value for f in DivergenceFlag}
    assert sum(counts.values()) == len(trail.records)


def test_build_summary_markdown_directly() -> None:
    trail = ValidationService().build_erdemir_trail(generated_at=_FIXED_TS)
    md = build_validation_summary_markdown(trail)
    assert trail.subject_tr in md
    for rec in trail.records:
        assert rec.validation_id in md

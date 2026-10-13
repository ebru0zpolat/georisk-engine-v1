"""GEO-150 cap pipeline unit tests (G-001)."""

from __future__ import annotations

from app.scoring.scenario_pipeline import apply_cap_pipeline


def test_g001_cap_pipeline_dict_four_steps() -> None:
    """G-001: hazard=90, mult=1.9 → adjusted_hazard=100, raw_scenario=95.5."""
    caps = apply_cap_pipeline(
        hazard_score=90,
        exposure_score=90,
        vulnerability_score=90,
        baseline_score=90,
        effective_multiplier=1.9,
    )
    assert caps["raw_adjusted_hazard"] == 171.0
    assert caps["adjusted_hazard_score"] == 100
    assert caps["raw_scenario_score"] == 95.5
    assert caps["scenario_score"] <= 100
    assert caps["capped_delta_points"] == 5
    assert caps["scenario_delta_cap_applied"] is True  # 5.5 raw delta truncated to 5


def test_g001_delta_cap_binds_at_25() -> None:
    caps = apply_cap_pipeline(
        hazard_score=60,
        exposure_score=60,
        vulnerability_score=60,
        baseline_score=60,
        effective_multiplier=1.3667,
    )
    assert caps["scenario_score"] == 72
    assert caps["capped_delta_points"] == 12
    assert abs(float(caps["raw_delta_points"]) - 12.1) < 0.01

"""GEO-150 deterministic cap pipeline — hazard-only SSP uplift (4 steps)."""

from __future__ import annotations

WEIGHT_HAZARD = 0.55
WEIGHT_EXPOSURE = 0.25
WEIGHT_VULNERABILITY = 0.20

SCENARIO_DELTA_CAP_POINTS = 25
MAX_SCORE = 100


def apply_cap_pipeline(
    hazard_score: int | float,
    exposure_score: int | float,
    vulnerability_score: int | float,
    baseline_score: int | float,
    effective_multiplier: float,
) -> dict[str, int | float | bool]:
    """Four-step scenario cap pipeline (GEO-150).

    Step 1: hazard saturation at 100
    Step 2: weighted H-E-V composite (hazard uses adjusted value)
    Step 3: delta cap (+25 points max vs baseline)
    Step 4: final score ceiling at 100
    """
    # Step 1
    raw_adjusted_hazard = float(hazard_score) * effective_multiplier
    adjusted_hazard_score = min(round(raw_adjusted_hazard), MAX_SCORE)

    # Step 2
    raw_scenario_score = (
        WEIGHT_HAZARD * adjusted_hazard_score
        + WEIGHT_EXPOSURE * float(exposure_score)
        + WEIGHT_VULNERABILITY * float(vulnerability_score)
    )

    # Step 3
    raw_delta_points = raw_scenario_score - float(baseline_score)
    capped_delta_points = int(
        max(0.0, min(float(SCENARIO_DELTA_CAP_POINTS), raw_delta_points))
    )
    scenario_delta_cap_applied = (
        capped_delta_points != raw_delta_points and raw_delta_points > 0
    )

    # Step 4
    scenario_score = min(MAX_SCORE, int(baseline_score) + capped_delta_points)
    final_score_cap_applied = scenario_score < int(baseline_score) + capped_delta_points

    return {
        "raw_adjusted_hazard": raw_adjusted_hazard,
        "adjusted_hazard_score": adjusted_hazard_score,
        "raw_scenario_score": raw_scenario_score,
        "raw_delta_points": raw_delta_points,
        "capped_delta_points": capped_delta_points,
        "scenario_score": scenario_score,
        "scenario_delta_cap_applied": scenario_delta_cap_applied,
        "final_score_cap_applied": final_score_cap_applied,
    }

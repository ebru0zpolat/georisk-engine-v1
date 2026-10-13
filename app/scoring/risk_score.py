import hashlib
import statistics

from app.core.sector_registry import (
    AGRICULTURE_SECTOR_ID,
    DEFAULT_SECTOR_ID,
    IRON_STEEL_SECTOR_ID,
)
from app.scoring.flood_heat import compute_flood_score, compute_heat_score
from app.schemas.risk import ComponentScores, RiskScoreRequest

# Order: industrial, pollution, land, ocean, agriculture, sensitivity.
# ``agriculture`` sector: up-weight land / agriculture / sensitivity; down-weight
# industrial / ocean to reflect NDVI– and soil-moisture–centric narratives (stub until
# real vegetation / soil layers feed these components).
# ``iron_steel``: up-weight industrial / pollution / sensitivity (CBAM / thermal proxies);
# down-weight agriculture / ocean.
_SECTOR_COMPONENT_MULTIPLIERS: dict[str, tuple[float, float, float, float, float, float]] = {
    DEFAULT_SECTOR_ID: (1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
    AGRICULTURE_SECTOR_ID: (0.72, 0.82, 1.18, 0.52, 1.22, 1.12),
    IRON_STEEL_SECTOR_ID: (1.25, 1.20, 0.95, 0.70, 0.55, 1.15),
}


def _raw_component_values(request: RiskScoreRequest) -> list[int]:
    payload = "|".join(
        (
            request.asset_name,
            f"{request.latitude:.6f}",
            f"{request.longitude:.6f}",
            f"{request.radius_km:.3f}",
            request.sector,
            request.start_date.isoformat() if request.start_date else "",
            request.end_date.isoformat() if request.end_date else "",
            request.baseline_start_date.isoformat() if request.baseline_start_date else "",
            request.baseline_end_date.isoformat() if request.baseline_end_date else "",
        )
    )
    digest = hashlib.sha256(payload.encode()).digest()
    return [digest[i] % 101 for i in range(6)]


def calibrate_component_vector(base: list[int], sector: str) -> list[int]:
    """Apply registered sector multipliers while preserving the mean of ``base`` (0–100 ints).

    Unknown ``sector`` strings are left **unchanged** (forward compatibility).
    """
    if len(base) != 6:
        raise ValueError("base must have length 6")
    mult = _SECTOR_COMPONENT_MULTIPLIERS.get(sector)
    if mult is None:
        return list(base)
    scaled = [base[i] * mult[i] for i in range(6)]
    mean_b = sum(base) / 6.0
    mean_s = sum(scaled) / 6.0
    if mean_s <= 1e-12:
        return list(base)
    adjust = mean_b / mean_s
    return [min(100, max(0, int(round(scaled[i] * adjust)))) for i in range(6)]


def compute_component_scores(request: RiskScoreRequest) -> ComponentScores:
    """Deterministic component scores from request fields (MVP stub + sector calibration)."""
    base = _raw_component_values(request)
    vals = calibrate_component_vector(base, request.sector)
    return ComponentScores(
        industrial=vals[0],
        pollution=vals[1],
        land=vals[2],
        ocean=vals[3],
        agriculture=vals[4],
        sensitivity=vals[5],
        flood=compute_flood_score(request),
        heat=compute_heat_score(request),
    )


def compute_overall_score(components: ComponentScores) -> int:
    """Legacy six-component mean (0–100). Kept for dual-publish with compound ``risk_score``."""
    parts = (
        components.industrial,
        components.pollution,
        components.land,
        components.ocean,
        components.agriculture,
        components.sensitivity,
    )
    return round(sum(parts) / len(parts))


def compound_driver_triple_from_components(components: ComponentScores) -> tuple[float, float, float]:
    """Map six MVP components to three comparable [0, 1] drivers (deterministic partition)."""
    heat = min(1.0, max(0.0, (components.industrial + components.pollution) / 200.0))
    water_stress = min(1.0, max(0.0, (components.land + components.ocean + components.agriculture) / 300.0))
    climate = min(1.0, max(0.0, components.sensitivity / 100.0))
    return heat, water_stress, climate


def compound_weights_for_preset(preset_id: str) -> tuple[float, float, float]:
    """Weights (heat, water_stress, climate) summing to 1.0."""
    if preset_id == "agriculture_v1":
        return (0.20, 0.50, 0.30)
    if preset_id == "transformer_v1":
        return (0.40, 0.30, 0.30)
    if preset_id == "iron_steel_v1":
        return (0.45, 0.25, 0.30)
    return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)


def confidence_from_drivers(heat: float, water_stress: float, climate: float) -> float:
    """Single 0–1 confidence: high when drivers agree, lower when spread is large."""
    vals = [heat, water_stress, climate]
    st = statistics.pstdev(vals)
    return max(0.0, min(1.0, 1.0 - st * 1.25))


def weighted_risk_from_components(
    components: ComponentScores, preset_id: str
) -> tuple[float, float, float, float]:
    """Return ``(risk_score, heat, water_stress, climate)`` with exact weighted identity."""
    heat, water_stress, climate = compound_driver_triple_from_components(components)
    wh, ww, wc = compound_weights_for_preset(preset_id)
    risk_score = min(1.0, max(0.0, wh * heat + ww * water_stress + wc * climate))
    return risk_score, heat, water_stress, climate


def risk_band(overall_score: int) -> str:
    if overall_score < 35:
        return "low"
    if overall_score < 65:
        return "medium"
    return "high"


def derive_flags(components: ComponentScores) -> list[str]:
    flags: list[str] = []
    if components.industrial >= 70:
        flags.append("elevated_industrial")
    if components.pollution >= 70:
        flags.append("elevated_pollution")
    if components.land >= 70:
        flags.append("elevated_land")
    if components.ocean >= 70:
        flags.append("elevated_ocean")
    if components.agriculture >= 70:
        flags.append("elevated_agriculture")
    if components.sensitivity >= 70:
        flags.append("elevated_sensitivity")
    if components.flood is not None and components.flood >= 70:
        flags.append("elevated_flood")
    if components.heat is not None and components.heat >= 70:
        flags.append("elevated_heat")
    return flags


def interpretation_text(
    overall_score: int, band: str, flags: list[str]
) -> str:
    parts = [
        f"Composite risk score {overall_score}/100 ({band} band).",
    ]
    if flags:
        parts.append(f"Notable drivers: {', '.join(flags)}.")
    else:
        parts.append("No component exceeded elevated thresholds in this assessment.")
    return " ".join(parts)

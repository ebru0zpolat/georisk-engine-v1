"""Hemelwater Engineering Decision — Article 4.116 Capacity Model.

Pure mathematical functions and decision model for Article 4.116
rainwater storage requirements.  Separates:

  required capacity (what the law demands)
  ≠
  actual capacity (what the building has)

Pure functions are mathematics only.  Calling them in a unit test
does NOT establish a verified engineering result for a real asset.

Core invariants:
  - required_storage_liters ≠ actual_storage_capacity_liters
  - geometry_verified ≠ engineering_capacity_verified
  - paragraph_applicable is separate from obligation_applicable
  - No numeric claim without explicit verified gates

Classification: engineering model — NOT production decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Pure mathematical functions
# ---------------------------------------------------------------------------

def calculate_standard_article_4_116(
    legal_built_area_m2: float,
) -> dict:
    """Calculate standard Article 4.116 requirements from a legal denominator.

    This is pure mathematics.  It does NOT establish that any specific
    building has these requirements — the caller must verify:
      - legal_bebouwd_oppervlak_verified
      - obligation_applicable
      - requirement_variant_verified

    Parameters
    ----------
    legal_built_area_m2 : float
        Verified legal bebouwd oppervlak in m² (NOT VBO floor area).

    Returns
    -------
    dict with required_storage_liters, max_discharge, required_emptying_hours.
    """
    return {
        "required_storage_liters": legal_built_area_m2 * 60.0,
        "max_discharge_liters_per_hour": legal_built_area_m2 * 1.0,
        "required_emptying_hours": 60.0,
    }


# ---------------------------------------------------------------------------
# Engineering decision model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HemelwaterEngineeringDecision:
    """Engineering capacity decision for Article 4.116 hemelwater.

    Distinguishes:
      - pand_footprint_area_m2: verified geometric fact
      - legal_bebouwd_oppervlak_m2: legal denominator (may differ)
      - required_storage_liters: what the law requires
      - actual_storage_capacity_liters: what the building has

    All verification fields are field(init=False), not caller-settable.
    """

    # --- Geometry (from geometry.py) --- INPUT fields (caller-settable)
    pand_footprint_area_m2: Optional[float] = None
    building_geometry_verified: bool = False

    # --- Legal denominator --- INPUT fields
    legal_bebouwd_oppervlak_m2: Optional[float] = None
    legal_denominator_basis: str = "NOT_DETERMINED"

    # --- Obligation applicability --- INPUT fields
    obligation_applicable: Optional[bool] = None

    # --- Requirement variant --- INPUT fields
    requirement_variant: Optional[str] = None

    # --- Required capacity (from law) --- INPUT fields
    required_storage_liters: Optional[float] = None
    max_discharge_liters_per_hour: Optional[float] = None
    required_emptying_hours: Optional[float] = None

    # --- Actual capacity (from building) --- INPUT fields
    actual_storage_capacity_liters: Optional[float] = None

    reason_code: str = "ENGINEERING_NOT_DETERMINED"

    # --- Verification flags --- factory-only, NOT caller-settable
    # These must only be set via the full verification gate chain.
    legal_bebouwd_oppervlak_verified: bool = field(init=False, default=False)
    obligation_applicability_verified: bool = field(init=False, default=False)
    requirement_variant_verified: bool = field(init=False, default=False)
    engineering_requirement_verified: bool = field(init=False, default=False)
    actual_storage_capacity_verified: bool = field(init=False, default=False)
    engineering_capacity_verified: bool = field(init=False, default=False)

    def to_dict(self) -> dict:
        """Serialize for evidence pack."""
        return {
            "pand_footprint_area_m2": self.pand_footprint_area_m2,
            "building_geometry_verified": self.building_geometry_verified,
            "legal_bebouwd_oppervlak_m2": self.legal_bebouwd_oppervlak_m2,
            "legal_bebouwd_oppervlak_verified": self.legal_bebouwd_oppervlak_verified,
            "legal_denominator_basis": self.legal_denominator_basis,
            "obligation_applicable": self.obligation_applicable,
            "obligation_applicability_verified": self.obligation_applicability_verified,
            "requirement_variant": self.requirement_variant,
            "requirement_variant_verified": self.requirement_variant_verified,
            "required_storage_liters": self.required_storage_liters,
            "max_discharge_liters_per_hour": self.max_discharge_liters_per_hour,
            "required_emptying_hours": self.required_emptying_hours,
            "engineering_requirement_verified": self.engineering_requirement_verified,
            "actual_storage_capacity_liters": self.actual_storage_capacity_liters,
            "actual_storage_capacity_verified": self.actual_storage_capacity_verified,
            "engineering_capacity_verified": self.engineering_capacity_verified,
            "reason_code": self.reason_code,
        }

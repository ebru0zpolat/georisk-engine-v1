"""Pluggable hazard modules for the five-layer Hazard layer (§2.1 / §2.4).

Active modules: flood, extreme heat, wildfire (climate) and earthquake (geophysical).
"""

from app.hazards.base import HazardModule, HazardModuleResult
from app.hazards.earthquake import EarthquakeHazardModule, SyntheticSeismicSource
from app.hazards.extreme_heat import ExtremeHeatHazardModule
from app.hazards.flood import FloodHazardModule
from app.hazards.wildfire import WildfireHazardModule

__all__ = [
    "EarthquakeHazardModule",
    "ExtremeHeatHazardModule",
    "FloodHazardModule",
    "HazardModule",
    "HazardModuleResult",
    "SyntheticSeismicSource",
    "WildfireHazardModule",
]

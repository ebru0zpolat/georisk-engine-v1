"""Flood inundation depth — the bridge from real elevation to JRC curves.

JRC depth-damage curves (``depth_damage_curves``) are keyed on inundation depth
in metres. The hazard layer holds a ground **elevation**; the flood-hazard map
holds a **water-surface elevation** by return period. Depth is their difference:

    inundation_depth = max(0, water_surface_elevation − ground_surface_elevation)

Differencing two elevations is only valid when they are genuinely comparable, so
this is **not** a bare datum-name check. An ``ElevationProfile`` carries the full
metadata of the ground-elevation source (vertical datum, units, horizontal CRS,
value semantics, source/version, datum transformation, resolution, synthetic
flag) and is checked for *differenceability* against the flood map. A NAP water
level can never be silently differenced against an EGM2008 (Copernicus DEM)
elevation, an inundation-depth raster, or a foot-unit source — each fails closed.

The scalar ``reference_level_m`` remains a single **synthetic** placeholder for the
legacy path (labelled ``synthetic_reference_flood_level``); it is isolated to one
constant and one parameter so it can never be mistaken for a real flood surface.
On the map path, provenance is **mandatory**: a caller must pass a ``data_versions``
collector, and the audit record carries the map id, checksum, source type, return
period, datum, cell id and synthetic status — no silent evidence loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.loss.depth_damage_curves import (
    DepthDamageCatalogue,
    DepthDamageCurve,
    damage_ratio_at_depth,
)
from app.loss.flood_hazard_map import FloodHazardMap

# SYNTHETIC labelled reference inundation level (metres, elevation datum).
# NOT a real flood level. Real replacement: return-period flood-hazard maps.
REFERENCE_LEVEL_BASIS = "synthetic_reference_flood_level_v0.1"
DEFAULT_REFERENCE_LEVEL_M = 1.0
# The elevation datum the scalar placeholder is expressed in (metres w.r.t. NAP).
DEFAULT_ELEVATION_DATUM = "NAP"

# Value semantics: a ground-surface elevation may be differenced from a
# water-surface elevation to yield a depth. Neither may itself already be a depth.
GROUND_SURFACE_SEMANTICS = "ground_surface_elevation"
WATER_SURFACE_SEMANTICS = "water_surface_elevation"

# A datum transformation identifier is always required. "none_required" is the
# explicit assertion that the source is natively in the target datum (never blank,
# so a missing transformation can never masquerade as "no transform needed").
NO_TRANSFORM_REQUIRED = "none_required"


@dataclass(frozen=True)
class ElevationProfile:
    """Full metadata of a ground-elevation source, so it can be checked for
    *differenceability* against a flood-map water surface — not just datum name.

    ``synthetic`` marks a labelled non-real elevation (integration demos/tests);
    a real qualification run must use a real, sealed elevation source (e.g. AHN).
    """

    vertical_datum: str  # e.g. "NAP"
    units: str  # e.g. "m"
    horizontal_crs: str  # e.g. "EPSG:4326"
    source: str  # e.g. "AHN4" or "SYNTHETIC_NAP_ELEVATION"
    version: str
    transformation: str  # a transform id, or NO_TRANSFORM_REQUIRED (never blank)
    resolution: str  # e.g. "0.5m DEM", "point"
    synthetic: bool
    value_semantics: str = GROUND_SURFACE_SEMANTICS


def assert_differenceable(profile: ElevationProfile, reference_map: FloodHazardMap) -> None:
    """Fail closed unless the elevation may be differenced from the map's water level.

    Compares the metadata that must line up before subtracting two elevations —
    vertical datum, units, horizontal CRS, value semantics (ground vs water surface,
    never an already-computed depth) and an explicit datum transformation on both
    sides. Any mismatch raises ``FLOOD_DATUM_MISMATCH`` with the specific reason(s).
    Cell/DEM resolution is deliberately *not* required to match (a 0.5 m DEM and a
    0.01° flood grid legitimately differ); it is recorded in provenance instead.
    """
    reasons: list[str] = []
    if profile.vertical_datum != reference_map.datum:
        reasons.append(
            f"vertical datum {profile.vertical_datum!r} != flood-map datum "
            f"{reference_map.datum!r} (e.g. AHN/NAP vs Copernicus DEM/EGM2008)"
        )
    if profile.units != reference_map.units:
        reasons.append(f"units {profile.units!r} != flood-map units {reference_map.units!r}")
    if profile.horizontal_crs != reference_map.horizontal_crs:
        reasons.append(
            f"horizontal CRS {profile.horizontal_crs!r} != flood-map CRS "
            f"{reference_map.horizontal_crs!r}"
        )
    if profile.value_semantics != GROUND_SURFACE_SEMANTICS:
        reasons.append(
            f"elevation value semantics {profile.value_semantics!r} is not a "
            f"{GROUND_SURFACE_SEMANTICS!r} (cannot difference a depth/other quantity)"
        )
    if reference_map.value_semantics != WATER_SURFACE_SEMANTICS:
        reasons.append(
            f"flood-map value semantics {reference_map.value_semantics!r} is not a "
            f"{WATER_SURFACE_SEMANTICS!r}"
        )
    if not profile.transformation.strip():
        reasons.append(
            f"elevation datum transformation is blank (use {NO_TRANSFORM_REQUIRED!r} "
            "if the source is natively in the target datum)"
        )
    if not reference_map.transformation.strip():
        reasons.append(
            f"flood-map datum transformation is blank (use {NO_TRANSFORM_REQUIRED!r})"
        )
    if reasons:
        raise ValueError("FLOOD_DATUM_MISMATCH: " + "; ".join(reasons))


def inundation_depth_m(ground_elevation_m: float, reference_level_m: float) -> float:
    """Water depth over ground for a given reference flood level (≥ 0)."""
    return max(0.0, float(reference_level_m) - float(ground_elevation_m))


def flood_reference_provenance(
    reference_map: FloodHazardMap,
    latitude: float,
    longitude: float,
    return_period_years: int,
    elevation_profile: ElevationProfile,
) -> dict[str, Any]:
    """Full audit identity of a flood-map reference level plus its elevation source.

    Carries the map id, checksum, source type, return period, datum, resolved cell
    id and synthetic status (from the map), and the elevation source/version/datum/
    transformation/synthetic status — everything an auditor needs to reconstruct and
    trust (or reject) the depth. Never lossy: called only on the map path, always
    written into a mandatory collector.
    """
    _level, stamp = reference_map.lookup_provenance(latitude, longitude, return_period_years)
    stamp.update(
        {
            "flood_elevation_source": elevation_profile.source,
            "flood_elevation_version": elevation_profile.version,
            "flood_elevation_datum": elevation_profile.vertical_datum,
            "flood_elevation_units": elevation_profile.units,
            "flood_elevation_transformation": elevation_profile.transformation,
            "flood_elevation_resolution": elevation_profile.resolution,
            "flood_elevation_synthetic": elevation_profile.synthetic,
        }
    )
    return stamp


def resolve_reference_level(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    return_period_years: int | None = None,
    reference_map: FloodHazardMap | None = None,
    reference_level_m: float = DEFAULT_REFERENCE_LEVEL_M,
    elevation_profile: ElevationProfile | None = None,
) -> tuple[float, str]:
    """Return ``(reference_level_m, basis)`` — a real per-asset level or the scalar.

    When a ``FloodHazardMap`` is supplied, the reference level is the map's water
    level for this location and return period (fail-closed if the cell/period is
    not covered), and the basis is the map's provenanced id. An ``ElevationProfile``
    MUST be given and MUST be *differenceable* with the map (``assert_differenceable``)
    — a missing profile or any metadata mismatch fails closed. Without a map, the
    single labelled synthetic scalar is returned (legacy path).
    """
    if reference_map is not None:
        if latitude is None or longitude is None or return_period_years is None:
            raise ValueError(
                "reference_map requires latitude, longitude and return_period_years"
            )
        if elevation_profile is None:
            raise ValueError(
                "FLOOD_DATUM_MISMATCH: a flood-map reference level requires an "
                "ElevationProfile to prove the elevation is differenceable with the "
                "map (vertical datum, units, CRS, value semantics, transformation); "
                "none supplied — refusing to difference an unqualified elevation"
            )
        assert_differenceable(elevation_profile, reference_map)
        level = reference_map.reference_level_at(latitude, longitude, return_period_years)
        basis = f"{reference_map.methodology_artifact_id}@T{return_period_years}"
        return level, basis
    return reference_level_m, REFERENCE_LEVEL_BASIS


def flood_damage_fraction(
    *,
    ground_elevation_m: float,
    building_type: str,
    catalogue: DepthDamageCatalogue,
    reference_level_m: float = DEFAULT_REFERENCE_LEVEL_M,
    continent: str = "*",
    reference_map: FloodHazardMap | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    return_period_years: int | None = None,
    elevation_profile: ElevationProfile | None = None,
    data_versions: dict[str, Any] | None = None,
) -> tuple[float, float, DepthDamageCurve]:
    """Compose elevation → depth → JRC damage fraction.

    Returns ``(depth_m, damage_ratio, selected_curve)`` (back-compatible triple).

    - **Scalar/legacy path** (no ``reference_map``): the labelled synthetic scalar
      is used; nothing is stamped, since there is no real flood-map identity.
    - **Map path** (``reference_map`` supplied): an ``ElevationProfile`` is required
      and checked for differenceability (fail-closed otherwise), and a
      ``data_versions`` collector is **mandatory** — the full provenance record
      (map id, checksum, source type, datum, cell id, return period, synthetic
      status, elevation source) is written into it. A missing collector is an error,
      not a silent omission.

    Fails closed via the catalogue guard when JRC values are not vendored, and via
    the map guard when a cell/period is uncovered.
    """
    if reference_map is not None:
        if data_versions is None:
            raise ValueError(
                "flood-map provenance is mandatory: pass a data_versions collector "
                "so the audit record carries the map id, checksum, datum, cell id, "
                "return period and synthetic status — refusing a silent map lookup"
            )
        if elevation_profile is None:
            raise ValueError(
                "FLOOD_DATUM_MISMATCH: the map path requires an ElevationProfile"
            )
        if return_period_years is None:
            raise ValueError("reference_map requires return_period_years")
    level, _basis = resolve_reference_level(
        latitude=latitude,
        longitude=longitude,
        return_period_years=return_period_years,
        reference_map=reference_map,
        reference_level_m=reference_level_m,
        elevation_profile=elevation_profile,
    )
    if reference_map is not None:
        assert latitude is not None and longitude is not None
        assert return_period_years is not None and elevation_profile is not None
        assert data_versions is not None
        data_versions.update(
            flood_reference_provenance(
                reference_map, latitude, longitude, return_period_years, elevation_profile
            )
        )
    depth = inundation_depth_m(ground_elevation_m, level)
    ratio, curve = damage_ratio_at_depth(
        building_type=building_type,
        depth_m=depth,
        continent=continent,
        catalogue=catalogue,
    )
    return depth, ratio, curve


__all__ = [
    "DEFAULT_ELEVATION_DATUM",
    "DEFAULT_REFERENCE_LEVEL_M",
    "GROUND_SURFACE_SEMANTICS",
    "NO_TRANSFORM_REQUIRED",
    "REFERENCE_LEVEL_BASIS",
    "WATER_SURFACE_SEMANTICS",
    "ElevationProfile",
    "assert_differenceable",
    "flood_damage_fraction",
    "flood_reference_provenance",
    "inundation_depth_m",
    "resolve_reference_level",
]

"""Pand Footprint Geometry — CRS Transform and Metric Area Calculation.

Derives metric building footprint area from sealed BAG Pand polygon
artifacts.  Uses OGC:CRS84 → EPSG:28992 (Amersfoort / RD New)
transformation for accurate m² computation.

Core invariants:
  - BAG Pand geometry verified ≠ Article 4.116 bebouwd oppervlak
  - VBO oppervlakte_m2 is never used for footprint calculation
  - Polygon area in degrees² is never used as m²
  - Invalid source geometry → fail closed (raises ValueError)
  - geometry_verified is set inside the validated factory
  - Calculation uses full floating precision; rounding only at
    serialization boundaries

Architecture:
  Sealed Pand artifact → hash verified → polygon extracted →
  CRS84→RDNew transform → metric area → PandFootprintEvidence
  (with geometry_verified=True inside the factory)

Classification: geometric evidence — NOT legal denominator
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterator

from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import transform as shapely_transform
from pyproj import CRS, Transformer
import pyproj as _pyproj


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_CRS = "OGC:CRS84"
AREA_CRS = "EPSG:28992"

GEOMETRY_ALGORITHM = "sealed_bag_pand_polygon_crs84_to_rdnew_area"
GEOMETRY_ALGORITHM_VERSION = "2.0"

# Allowed geometry types
ALLOWED_GEOMETRY_TYPES = {"Polygon", "MultiPolygon"}

# Broad RD-New sanity bounds (Netherlands approximate)
# X (easting): ~7000 to ~300000
# Y (northing): ~289000 to ~629000
RDNEW_X_MIN = 0.0
RDNEW_X_MAX = 400000.0
RDNEW_Y_MIN = 280000.0
RDNEW_Y_MAX = 650000.0


# ---------------------------------------------------------------------------
# Coordinate iteration (Polygon + MultiPolygon)
# ---------------------------------------------------------------------------

def _iterate_ring_coords(geom: Polygon) -> Iterator[tuple]:
    """Yield every coordinate from a Polygon's exterior and interior rings."""
    yield from geom.exterior.coords
    for interior in geom.interiors:
        yield from interior.coords


def _iterate_all_coords(geom) -> Iterator[tuple]:
    """Yield every coordinate from a Polygon or MultiPolygon."""
    if isinstance(geom, Polygon):
        yield from _iterate_ring_coords(geom)
    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            yield from _iterate_ring_coords(poly)
    else:
        raise ValueError(
            f"Unsupported geometry type: {type(geom).__name__}"
        )


# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PandFootprintEvidence:
    """Verified BAG Pand footprint geometry evidence.

    geometry_verified is set inside compute_pand_footprint_area()
    only after ALL gates pass.  A caller cannot construct a verified
    evidence object directly (field(init=False)).
    """

    bag_pand_id: str
    pand_feature_id: str

    source_geometry_type: str
    source_crs: str

    area_crs: str
    # Full floating-point precision — round only at serialization
    footprint_area_m2: float

    pand_status: str
    definitive_geometry: bool

    source_artifact_sha256: str
    source_normalized_sha256: str

    geometry_algorithm: str
    geometry_algorithm_version: str

    pand_source_id: str

    shapely_version: str
    pyproj_version: str
    proj_version: str

    # Factory-only — not caller-settable
    geometry_verified: bool = field(init=False, default=False)


# ---------------------------------------------------------------------------
# CRS transform + area calculation
# ---------------------------------------------------------------------------

def _make_transformer() -> Transformer:
    """Create CRS84 → RDNew transformer."""
    source_crs = CRS.from_user_input(SOURCE_CRS)
    area_crs = CRS.from_epsg(28992)
    return Transformer.from_crs(
        source_crs,
        area_crs,
        always_xy=True,
        allow_ballpark=False,
        only_best=True,
    )


def compute_pand_footprint_area(
    pand_geometry: dict,
    *,
    pand_status: str,
    bag_pand_id: str,
    pand_feature_id: str,
    source_artifact_sha256: str,
    source_normalized_sha256: str,
) -> PandFootprintEvidence:
    """Compute metric footprint area from a sealed BAG Pand polygon.

    On success, returns PandFootprintEvidence with geometry_verified=True.
    On failure, raises ValueError (fail closed — never returns unverified).

    Parameters
    ----------
    pand_geometry : dict
        GeoJSON geometry dict (type + coordinates).
    pand_status : str
        BAG Pand status (must be "Pand in gebruik").
    bag_pand_id : str
        BAG Pand identificatie.
    pand_feature_id : str
        Pand feature UUID.
    source_artifact_sha256 : str
        Artifact hash of the source file.
    source_normalized_sha256 : str
        Normalized content hash of the source file.

    Returns
    -------
    PandFootprintEvidence
        With geometry_verified=True (set inside the factory).

    Raises
    ------
    ValueError
        If geometry is invalid, empty, transformation fails,
        or any gate fails.
    """
    import shapely as _shapely

    # Gate 1: geometry exists
    if not pand_geometry:
        raise ValueError(
            "GEOMETRY_MISSING_FAIL_CLOSED: Pand geometry is empty"
        )

    # Gate 2: geometry type
    geom_type = pand_geometry.get("type", "")
    if geom_type not in ALLOWED_GEOMETRY_TYPES:
        raise ValueError(
            f"GEOMETRY_TYPE_INVALID_FAIL_CLOSED: {geom_type} "
            f"not in {ALLOWED_GEOMETRY_TYPES}"
        )

    # Gate 3: definitive geometry
    definitive = pand_status == "Pand in gebruik"
    if not definitive:
        raise ValueError(
            f"BAG_GEOMETRY_NOT_DEFINITIVE_FAIL_CLOSED: "
            f"status={pand_status}"
        )

    # Gate 4: parse shape and validate
    try:
        geom = shape(pand_geometry)
    except Exception as e:
        raise ValueError(
            f"GEOMETRY_PARSE_FAIL_CLOSED: {e}"
        ) from e

    # Gate 5: non-empty
    if geom.is_empty:
        raise ValueError(
            "GEOMETRY_EMPTY_FAIL_CLOSED: parsed geometry is empty"
        )

    # Gate 6: valid geometry (no self-intersections, etc.)
    if not geom.is_valid:
        raise ValueError(
            "GEOMETRY_INVALID_FAIL_CLOSED: geometry is not valid"
        )

    # Gate 7: all ring coordinates finite
    for coord in _iterate_all_coords(geom):
        if not all(math.isfinite(c) for c in coord):
            raise ValueError(
                f"COORDINATES_NON_FINITE_FAIL_CLOSED: {coord}"
            )

    # Derive source_id from pand_feature_id (matches manifest keys)
    pand_source_id_key = f"amsterdam-pand-{pand_feature_id[:8]}"

    # Gate 8: transform to metric CRS
    try:
        transformer = _make_transformer()
        geom_rd = shapely_transform(transformer.transform, geom)
    except Exception as e:
        raise ValueError(
            f"CRS_TRANSFORM_FAIL_CLOSED: {e}"
        ) from e

    # Gate 9: transformed geometry sanity
    if geom_rd.is_empty:
        raise ValueError(
            "TRANSFORMED_GEOMETRY_EMPTY_FAIL_CLOSED"
        )

    if not geom_rd.is_valid:
        raise ValueError(
            "TRANSFORMED_GEOMETRY_INVALID_FAIL_CLOSED"
        )

    area = geom_rd.area
    if not math.isfinite(area) or area <= 0:
        raise ValueError(
            f"AREA_INVALID_FAIL_CLOSED: {area}"
        )

    # Gate 10: centroid finite and within broad RD-New bounds
    centroid = geom_rd.centroid
    cx, cy = centroid.x, centroid.y
    if not math.isfinite(cx) or not math.isfinite(cy):
        raise ValueError(
            f"CENTROID_NON_FINITE_FAIL_CLOSED: ({cx}, {cy})"
        )
    if not (RDNEW_X_MIN <= cx <= RDNEW_X_MAX):
        raise ValueError(
            f"CENTROID_X_OUT_OF_RDNEW_RANGE_FAIL_CLOSED: {cx} "
            f"not in [{RDNEW_X_MIN}, {RDNEW_X_MAX}]"
        )
    if not (RDNEW_Y_MIN <= cy <= RDNEW_Y_MAX):
        raise ValueError(
            f"CENTROID_Y_OUT_OF_RDNEW_RANGE_FAIL_CLOSED: {cy} "
            f"not in [{RDNEW_Y_MIN}, {RDNEW_Y_MAX}]"
        )

    # All gates passed — build verified evidence with full precision
    evidence = PandFootprintEvidence(
        bag_pand_id=bag_pand_id,
        pand_feature_id=pand_feature_id,
        source_geometry_type=geom_type,
        source_crs=SOURCE_CRS,
        area_crs=AREA_CRS,
        footprint_area_m2=area,  # full floating-point precision
        pand_status=pand_status,
        definitive_geometry=definitive,
        source_artifact_sha256=source_artifact_sha256,
        source_normalized_sha256=source_normalized_sha256,
        pand_source_id=pand_source_id_key,
        geometry_algorithm=GEOMETRY_ALGORITHM,
        geometry_algorithm_version=GEOMETRY_ALGORITHM_VERSION,
        shapely_version=str(_shapely.__version__),
        pyproj_version=str(_pyproj.__version__),
        proj_version=str(_pyproj.proj_version_str),
    )

    # Set geometry_verified inside the factory after ALL gates pass
    # This is the ONLY code path that can produce verified evidence
    object.__setattr__(evidence, "geometry_verified", True)

    return evidence

#!/usr/bin/env python3
"""Generate a deterministic SYNTHETIC reference portfolio of Dutch commercial properties.

This fixture is a **synthetic reference dataset** for schema-conformance testing,
deterministic dry-runs, demos and development. It is NOT a scientific gold-standard,
NOT ground-truth, NOT survey data, and contains no real customer assets.

  PYTHONPATH=. python scripts/generate_synthetic_reference_portfolio.py \
      --output data/portfolios/synthetic/synthetic_reference_portfolio_v1.json \
      [--count 120] [--seed 20260825]

Fail-closed guarantees:
- validates every record against the canonical portfolio contract
  (``app.schemas.portfolio.PortfolioUploadRequest`` / ``UniversalAsset``);
- enforces the 50–500 asset size range;
- validates EPSG:28992 coordinates against the documented NL RD domain bounds;
- writes atomically (temp file + ``os.replace``) so partial output never exists;
- raises on any schema, bound, checksum or parameter failure.

Determinism: output depends only on (seed, count). All randomness is derived from
SHA-256 over stable strings; no wall-clock time enters the content. See
``CHECKSUM_CONTRACT`` below for the byte-exact checksum definition.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from app.schemas import portfolio as portfolio_schema_module  # noqa: E402
from app.schemas.portfolio import (  # noqa: E402
    PORTFOLIO_MAX_ASSETS,
    PORTFOLIO_MIN_ASSETS,
    PortfolioUploadRequest,
    UniversalAsset,
)

GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20260825
DEFAULT_COUNT = 120
MIN_ASSETS = 50
MAX_ASSETS = PORTFOLIO_MAX_ASSETS  # 500 — canonical upper bound
assert MIN_ASSETS == 50, "repository guidance expects a 50-floor"

FIXTURE_ID = "synthetic-reference-portfolio-v1"
PORTFOLIO_ID = "pf_synref_v1"
VALUATION_DATE = "2021-07-01"  # fixed constant; no wall-clock time in content

# Canonical schema binding (fail-closed against silent schema drift).
SCHEMA_BINDING = {
    "kind": "pydantic_models",
    "module": "app.schemas.portfolio",
    "models": ["PortfolioUploadRequest", "UniversalAsset"],
}

DATASET_CLASSIFICATION = "synthetic_reference_portfolio"
GENERATION_METHOD = "sha256_derived_deterministic_v1"
COORDINATE_SOURCE = "synthetically_generated"

# Exact EPSG identifiers only — informal CRS names are rejected.
EPSG_RD = 28992
EPSG_WGS84 = 4326

# Netherlands RD (EPSG:28992) domain envelope. Documented synthetic-plausibility
# bounds for this fixture; NOT an official survey extent. Values in metres.
RD_X_MIN, RD_X_MAX = 10_000.0, 278_000.0
RD_Y_MIN, RD_Y_MAX = 300_000.0, 625_000.0

# WGS84 Netherlands envelope used to sanity-check generated lat/lon.
NL_LAT_MIN, NL_LAT_MAX = 50.75, 53.70
NL_LON_MIN, NL_LON_MAX = 3.35, 7.25

# Synthetic commercial-property valuation window (EUR).
VALUE_MIN_EUR = 1_500_000.0
VALUE_MAX_EUR = 45_000_000.0

# City centroids (real cities, synthetic parcels): name -> (lat, lon, count@120).
CITY_CENTROIDS: dict[str, tuple[float, float]] = {
    "Amsterdam": (52.3720, 4.8950),
    "Rotterdam": (51.9240, 4.4780),
    "The Hague": (52.0780, 4.3130),
    "Utrecht": (52.0920, 5.1100),
    "Eindhoven": (51.4420, 5.4780),
}
SAMPLE_CITY_COUNTS = {
    "Amsterdam": 25,
    "Rotterdam": 31,
    "The Hague": 22,
    "Utrecht": 14,
    "Eindhoven": 28,
}
assert sum(SAMPLE_CITY_COUNTS.values()) == DEFAULT_COUNT

BUILDING_TYPES = ["office", "retail", "hotel", "logistics", "mixed_use"]
USE_CLASSES = {
    "office": "commercial",
    "retail": "retail",
    "hotel": "hospitality",
    "logistics": "logistics",
    "mixed_use": "commercial",
}

# Truth-state block — every value below is a hard assertion target in tests.
TRUTH_STATES = {
    "dataset_classification": DATASET_CLASSIFICATION,
    "customer_data_status": "not_customer_data",
    "valuation_status": "synthetic_unverified",
    "coordinate_source": COORDINATE_SOURCE,
    "survey_accuracy_verified": False,
    "ground_truth_verified": False,
    "physical_inundation_extent_verified": False,
    "empirical_accuracy_verified": False,
    "decision_use_approved": False,
    "controlled_pilot_eligible": False,
    "customer_pilot_verified": False,
    "runtime_live_verified": False,
    "production_eligible": False,
}

CHECKSUM_CONTRACT = (
    "sha256 over UTF-8 bytes of json.dumps(document['dataset'], sort_keys=True, "
    "separators=(',', ':'), ensure_ascii=False). The 'dataset' object contains the "
    "portfolio payload and all supplements/metadata except this integrity block. "
    "No timestamps are part of the checksummed content."
)


# --------------------------------------------------------------------------- #
# Deterministic primitives (pure functions of seed strings — no RNG state)
# --------------------------------------------------------------------------- #
def _unit(*parts: str) -> float:
    """Uniform float in [0, 1) derived from SHA-256 of the joined parts."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / 0xFFFFFFFFFFFFFFFF


def _int_in(*parts: str, lo: int, hi: int) -> int:
    return lo + int(_unit(*parts) * (hi - lo + 1)) % (hi - lo + 1)


def _round(value: float, digits: int) -> float:
    return round(value + 0.0, digits)


# --------------------------------------------------------------------------- #
# Coordinate synthesis
# --------------------------------------------------------------------------- #
def _jitter_wgs84(city: str, idx: int, seed: str) -> tuple[float, float]:
    """Plausible-but-synthetic point within ~2 km of a real city centroid."""
    base_lat, base_lon = CITY_CENTROIDS[city]
    dlat = (_unit(seed, "lat") * 2 - 1) * 0.018
    dlon = (_unit(seed, "lon") * 2 - 1) * 0.028
    return _round(base_lat + dlat, 6), _round(base_lon + dlon, 6)


def wgs84_to_rd_approx(lat: float, lon: float) -> tuple[float, float]:
    """Approximate WGS84 -> EPSG:28992 (RD) conversion.

    Published Schreutelkamp & Strang van Hees polynomial approximation
    (sub-metre typical accuracy). Used ONLY to synthesise plausible RD
    coordinates for synthetic points; never presented as surveyed or
    authoritative geometry.
    """
    dphi = 0.36 * (lat - 52.15517440)
    dlam = 0.36 * (lon - 5.38720621)

    # Easting (x): Spq · dphi^p · dlam^q
    x = (
        155_000.0
        + 190_094.945 * dlam
        + -11_832.228 * dphi * dlam
        + -114.221 * dphi ** 2
        + -32.391 * dphi ** 2 * dlam
        + -0.705 * dlam ** 2
        + -2.340 * dphi ** 3 * dlam
        + -0.608 * dphi * dlam ** 2
        + 0.008 * dphi ** 2 * dlam ** 2
        + 0.148 * dlam ** 3
    )
    # Northing (y): Qpq · dphi^p · dlam^q
    y = (
        463_000.0
        + 309_056.544 * dphi
        + 3_638.893 * dlam
        + 73.077 * dphi ** 2
        + -157.984 * dphi * dlam
        + 59.788 * dphi ** 3
        + 0.433 * dlam ** 2
        + -6.439 * dphi ** 2 * dlam
        + 0.032 * dphi ** 3 * dlam
        + -0.034 * dphi * dlam ** 3
    )
    return _round(x, 2), _round(y, 2)


def _validate_rd_bounds(x: float, y: float) -> None:
    if not (RD_X_MIN <= x <= RD_X_MAX and RD_Y_MIN <= y <= RD_Y_MAX):
        raise ValueError(
            f"Synthetic RD coordinate ({x}, {y}) outside Netherlands domain bounds "
            f"x=[{RD_X_MIN}, {RD_X_MAX}], y=[{RD_Y_MIN}, {RD_Y_MAX}]"
        )


def _validate_wgs84_bounds(lat: float, lon: float) -> None:
    if not (NL_LAT_MIN <= lat <= NL_LAT_MAX and NL_LON_MIN <= lon <= NL_LON_MAX):
        raise ValueError(
            f"Synthetic WGS84 coordinate ({lat}, {lon}) outside NL envelope "
            f"lat=[{NL_LAT_MIN}, {NL_LAT_MAX}], lon=[{NL_LON_MIN}, {NL_LON_MAX}]"
        )


def _postcode(seed: str) -> str:
    """Format-valid Dutch postcode (NNNN AA). Format validity != real property."""
    digits = _int_in(seed, "pc-d", lo=1000, hi=9999)
    letters = chr(ord("A") + _int_in(seed, "pc-a", lo=0, hi=25)) + chr(
        ord("A") + _int_in(seed, "pc-b", lo=0, hi=25)
    )
    return f"{digits} {letters}"


# --------------------------------------------------------------------------- #
# Asset synthesis
# --------------------------------------------------------------------------- #
def allocate_cities(count: int) -> list[str]:
    """Deterministically distribute ``count`` assets over cities.

    At the default 120 the distribution equals SAMPLE_CITY_COUNTS exactly;
    other counts get proportional allocation with largest-remainder fill.
    """
    total_sample = sum(SAMPLE_CITY_COUNTS.values())
    raw = {c: count * n / total_sample for c, n in SAMPLE_CITY_COUNTS.items()}
    alloc = {c: int(v) for c, v in raw.items()}
    remainder = count - sum(alloc.values())
    order = sorted(raw, key=lambda c: (-(raw[c] - alloc[c]), c))
    for i in range(remainder):
        alloc[order[i % len(order)]] += 1
    cities: list[str] = []
    for city in sorted(CITY_CENTROIDS):
        cities.extend([city] * alloc[city])
    return cities


def build_assets(count: int, seed: int) -> list[dict]:
    """Return ``count`` synthetic asset records (already canonically validated)."""
    if not isinstance(count, int) or not (MIN_ASSETS <= count <= MAX_ASSETS):
        raise ValueError(f"count must be an integer in [{MIN_ASSETS}, {MAX_ASSETS}], got {count!r}")

    cities = allocate_cities(count)
    records: list[dict] = []
    counters: dict[str, int] = {}
    for i, city in enumerate(cities):
        counters[city] = counters.get(city, 0) + 1
        code = "".join(w[0] for w in city.split()).upper()
        asset_id = f"SYNREF-{code}-{counters[city]:03d}"
        s = f"{seed}|{asset_id}|{i}"
        lat, lon = _jitter_wgs84(city, i, s)
        _validate_wgs84_bounds(lat, lon)
        building = BUILDING_TYPES[_int_in(s, "bt", lo=0, hi=len(BUILDING_TYPES) - 1)]
        value = _round(VALUE_MIN_EUR + _unit(s, "val") * (VALUE_MAX_EUR - VALUE_MIN_EUR), 2)
        year = _int_in(s, "yr", lo=1950, hi=2020)
        floors = _int_in(s, "fl", lo=1, hi=18)
        pc = _postcode(s)
        street_no = _int_in(s, "sn", lo=1, hi=220)

        # CRS assignment: stable interleave over record order — even index gets
        # RD supplement, odd index stays WGS84-only. 120 records -> exactly 60/60.
        epsg = EPSG_RD if i % 2 == 0 else EPSG_WGS84

        records.append(
            {
                "asset_id": asset_id,
                "address": f"Synthetisch perceel {street_no} {pc} {city}",
                "latitude": lat,
                "longitude": lon,
                "asset_value": value,
                "building_type": building,
                "use_class": USE_CLASSES[building],
                "construction_year": year,
                "floors": floors,
                "insurance_coverage": _round(value * 0.6, 2),
                "ltv": _round(0.40 + (_unit(s, "ltv") * 0.4), 2),
                "loan_id": f"SYN-LN-{i:04d}",
                "_epsg": epsg,
                "_rd": wgs84_to_rd_approx(lat, lon) if epsg == EPSG_RD else None,
                "_city": city,
            }
        )

    records.sort(key=lambda r: r["asset_id"])  # stable canonical ordering
    return records


def validate_canonical(records: list[dict], valuation_date: str) -> PortfolioUploadRequest:
    """Validate the payload against the canonical portfolio contract. Fail-closed.

    Any structural or semantic violation (missing field, wrong type, out-of-range
    value) is raised as ``ValueError`` — never silently coerced or skipped.
    """
    try:
        return PortfolioUploadRequest(
            valuation_date=valuation_date,
            portfolio_id=PORTFOLIO_ID,
            assets=[
                UniversalAsset(
                    asset_id=r["asset_id"],
                    address=r["address"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    asset_value=r["asset_value"],
                    building_type=r["building_type"],
                    use_class=r["use_class"],
                    construction_year=r["construction_year"],
                    floors=r["floors"],
                    insurance_coverage=r["insurance_coverage"],
                    ltv=r["ltv"],
                    loan_id=r["loan_id"],
                )
                for r in records
            ],
        )
    except ValidationError as exc:
        raise ValueError(f"Generated records violate canonical portfolio schema: {exc}") from exc
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Generated record is malformed (missing/invalid field): {exc}") from exc


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_checksum(document: dict) -> str:
    """SHA-256 over the canonical serialization of ``document['dataset']``."""
    return hashlib.sha256(_canonical_json(document["dataset"]).encode("utf-8")).hexdigest()


def build_document(count: int, seed: int) -> dict:
    records = build_assets(count, seed)
    validate_canonical(records, VALUATION_DATE)

    rd_supplement: dict[str, dict] = {}
    crs_assignment: dict[str, int] = {}
    for r in records:
        crs_assignment[r["asset_id"]] = r["_epsg"]
        if r["_epsg"] == EPSG_RD:
            assert r["_rd"] is not None
            _validate_rd_bounds(r["_rd"][0], r["_rd"][1])
            rd_supplement[r["asset_id"]] = {
                "epsg": EPSG_RD,
                "x": r["_rd"][0],
                "y": r["_rd"][1],
            }

    schema_source_sha = hashlib.sha256(
        inspect.getsource(portfolio_schema_module).encode("utf-8")
    ).hexdigest()

    dataset = {
        "fixture_id": FIXTURE_ID,
        "metadata": {
            **TRUTH_STATES,
            "generator_version": GENERATOR_VERSION,
            "generation_method": GENERATION_METHOD,
            "seed": seed,
            "asset_count": count,
            "currency": "EUR",
            "valuation_date": VALUATION_DATE,
            "valuation_range_eur": [VALUE_MIN_EUR, VALUE_MAX_EUR],
            "crs_distribution": {
                str(EPSG_RD): sum(1 for r in records if r["_epsg"] == EPSG_RD),
                str(EPSG_WGS84): sum(1 for r in records if r["_epsg"] == EPSG_WGS84),
            },
            "wgs84_axis_order": "(latitude, longitude) named fields per canonical schema",
            "schema_binding": {
                **SCHEMA_BINDING,
                "source_sha256": schema_source_sha,
            },
            "disclaimer": (
                "Deterministic synthetic reference fixture for testing and demonstration. "
                "Not a gold-standard or ground-truth dataset."
            ),
        },
        "portfolio": {
            "portfolio_id": PORTFOLIO_ID,
            "valuation_date": VALUATION_DATE,
            "assets": [
                {k: r[k] for k in (
                    "asset_id", "address", "latitude", "longitude", "asset_value",
                    "building_type", "use_class", "construction_year", "floors",
                    "insurance_coverage", "ltv", "loan_id",
                )}
                for r in records
            ],
        },
        "supplements": {
            "crs_assignment": crs_assignment,
            "rd_coordinates": rd_supplement,
            "note": (
                "Supplemental synthetic EPSG:28992 coordinates are NOT part of the "
                "canonical ingest payload; the canonical payload is WGS84-only."
            ),
        },
    }
    return {
        "dataset": dataset,
        "integrity": {
            "checksum_algorithm": "sha256",
            "checksum_contract": CHECKSUM_CONTRACT,
            "content_checksum": "",
        },
    }


def generate(count: int, seed: int) -> dict:
    document = build_document(count, seed)
    document["integrity"]["content_checksum"] = compute_checksum(document)

    # Fail-closed self-check: recompute and compare before returning.
    if compute_checksum(document) != document["integrity"]["content_checksum"]:
        raise ValueError("Checksum self-check failed")
    return document


def atomic_write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Output JSON path.")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    try:
        document = generate(args.count, args.seed)
    except ValueError as exc:
        print(f"FAIL-CLOSED: {exc}", file=sys.stderr)
        return 2

    if args.output is None:
        print(json.dumps({"asset_count": args.count, "seed": args.seed}))
        return 0
    atomic_write(args.output, document)
    print(f"wrote {args.output} ({args.count} assets, checksum {document['integrity']['content_checksum'][:16]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

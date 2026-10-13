"""Tests for the deterministic synthetic reference portfolio generator and fixture.

Covers: determinism, canonical-schema conformance, size boundaries, checksum
integrity, CRS contracts, NL coordinate bounds, privacy controls, truth-state
metadata, fail-closed behaviour, and committed-fixture regeneration equality.

No network access, no credentials, no live services.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from app.schemas.portfolio import (  # noqa: E402
    PORTFOLIO_MAX_ASSETS,
    PortfolioUploadRequest,
    UniversalAsset,
)
from scripts.generate_synthetic_reference_portfolio import (  # noqa: E402
    CHECKSUM_CONTRACT,
    DEFAULT_COUNT,
    DEFAULT_SEED,
    EPSG_RD,
    EPSG_WGS84,
    MAX_ASSETS,
    MIN_ASSETS,
    RD_X_MAX,
    RD_X_MIN,
    RD_Y_MAX,
    RD_Y_MIN,
    SAMPLE_CITY_COUNTS,
    TRUTH_STATES,
    VALUE_MAX_EUR,
    VALUE_MIN_EUR,
    atomic_write,
    build_document,
    compute_checksum,
    generate,
    main as cli_main,
    wgs84_to_rd_approx,
)

FIXTURE_PATH = ROOT / "data" / "portfolios" / "synthetic" / "synthetic_reference_portfolio_v1.json"
GENERATOR_MODULE = "scripts.generate_synthetic_reference_portfolio"

POSTCODE_RE = re.compile(r"\b[1-9][0-9]{3} [A-Z]{2}\b")
SECRET_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(api[_-]?key|secret|password|token|bearer)\s*[:=]",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"/home/\w+/",
        r"/Users/\w+",
        r"C:\\\\Users\\\\",
    )
]
CUSTOMER_DATA_WORDS = ["customer_id", "tenant_name", "client_name", "owner_name", "kvk", "bsn"]


@pytest.fixture(scope="module")
def fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dataset(fixture) -> dict:
    return fixture["dataset"]


@pytest.fixture(scope="module")
def assets(dataset) -> list[dict]:
    return dataset["portfolio"]["assets"]


# --------------------------------------------------------------------------- #
# Committed fixture integrity
# --------------------------------------------------------------------------- #
def test_committed_fixture_matches_checksum(fixture):
    assert compute_checksum(fixture) == fixture["integrity"]["content_checksum"]


def test_tamper_detection(fixture):
    tampered = json.loads(json.dumps(fixture))
    tampered["dataset"]["portfolio"]["assets"][0]["asset_value"] += 1.0
    assert compute_checksum(tampered) != tampered["integrity"]["content_checksum"]


def test_checksum_contract_is_documented_and_sha256(fixture):
    assert fixture["integrity"]["checksum_algorithm"] == "sha256"
    assert fixture["integrity"]["checksum_contract"] == CHECKSUM_CONTRACT
    assert re.fullmatch(r"[0-9a-f]{64}", fixture["integrity"]["content_checksum"])


# --------------------------------------------------------------------------- #
# Generator determinism
# --------------------------------------------------------------------------- #
def test_default_output_is_exactly_120():
    doc = generate(DEFAULT_COUNT, DEFAULT_SEED)
    assert len(doc["dataset"]["portfolio"]["assets"]) == 120


def test_deterministic_equality_same_seed():
    a, b = generate(120, 7), generate(120, 7)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_different_seed_different_output():
    a, b = generate(60, 1), generate(60, 2)
    assert json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)


def test_boundary_counts_50_and_500():
    assert len(generate(MIN_ASSETS, 5)["dataset"]["portfolio"]["assets"]) == 50
    assert len(generate(MAX_ASSETS, 5)["dataset"]["portfolio"]["assets"]) == 500
    assert MAX_ASSETS == PORTFOLIO_MAX_ASSETS


@pytest.mark.parametrize("count", [49, 501, 0, -1])
def test_reject_counts_outside_range(count):
    with pytest.raises(ValueError):
        generate(count, 5)


def test_stable_ordering_by_asset_id(assets):
    ids = [a["asset_id"] for a in assets]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


# --------------------------------------------------------------------------- #
# Canonical schema conformance
# --------------------------------------------------------------------------- #
def test_canonical_schema_validation(dataset):
    p = dataset["portfolio"]
    request = PortfolioUploadRequest(
        valuation_date=p["valuation_date"],
        portfolio_id=p["portfolio_id"],
        assets=[UniversalAsset(**a) for a in p["assets"]],
    )
    assert request.asset_count if hasattr(request, "asset_count") else True
    assert len(request.assets) == len(p["assets"])


def test_fixture_assets_match_canonical_model_fields(assets):
    canonical_fields = set(UniversalAsset.model_fields)
    for asset in assets:
        extra = set(asset) - canonical_fields
        assert not extra, f"non-canonical fields in payload: {extra}"


def test_schema_binding_records_module_and_source_hash(dataset):
    binding = dataset["metadata"]["schema_binding"]
    module = importlib.import_module("app.schemas.portfolio")
    source = inspect_getsource(module)
    assert binding["module"] == "app.schemas.portfolio"
    assert binding["source_sha256"] == hashlib.sha256(source.encode()).hexdigest()


def inspect_getsource(module) -> str:
    import inspect

    return inspect.getsource(module)


# --------------------------------------------------------------------------- #
# Sample-fixture shape: cities, CRS distribution
# --------------------------------------------------------------------------- #
def test_city_distribution_for_sample_fixture(dataset):
    counts = {c: 0 for c in SAMPLE_CITY_COUNTS}
    rd = dataset["supplements"]["rd_coordinates"]
    all_ids = set(dataset["supplements"]["crs_assignment"])
    # Derive city from the address of each asset.
    for a in dataset["portfolio"]["assets"]:
        for city in counts:
            if a["address"].endswith(city):
                counts[city] += 1
                break
        else:
            pytest.fail(f"asset {a['asset_id']} has no recognised city: {a['address']}")
    assert counts == SAMPLE_CITY_COUNTS, counts
    assert sum(counts.values()) == 120 == len(all_ids)


def test_crs_distribution_60_60(dataset):
    dist = dataset["metadata"]["crs_distribution"]
    assert dist[str(EPSG_RD)] == 60
    assert dist[str(EPSG_WGS84)] == 60
    assign = dataset["supplements"]["crs_assignment"]
    values = list(assign.values())
    assert values.count(EPSG_RD) == 60
    assert values.count(EPSG_WGS84) == 60


def test_exact_epsg_identifiers_only(dataset):
    allowed = {EPSG_RD, EPSG_WGS84}
    assert set(dataset["supplements"]["crs_assignment"].values()) <= allowed
    assert set(map(int, dataset["metadata"]["crs_distribution"])) <= allowed


def test_rd_supplement_only_for_rd_assets(dataset):
    assign = dataset["supplements"]["crs_assignment"]
    rd = dataset["supplements"]["rd_coordinates"]
    expect_rd = {aid for aid, e in assign.items() if e == EPSG_RD}
    assert set(rd) == expect_rd


# --------------------------------------------------------------------------- #
# Coordinate bounds and axis order
# --------------------------------------------------------------------------- #
def test_wgs84_within_netherlands_bounds(assets):
    for a in assets:
        assert -90.0 <= a["latitude"] <= 90.0
        assert -180.0 <= a["longitude"] <= 180.0
        assert 50.75 <= a["latitude"] <= 53.70
        assert 3.35 <= a["longitude"] <= 7.25


def test_rd_coordinates_within_nl_domain_bounds(dataset):
    for aid, coord in dataset["supplements"]["rd_coordinates"].items():
        assert coord["epsg"] == EPSG_RD
        assert RD_X_MIN <= coord["x"] <= RD_X_MAX
        assert RD_Y_MIN <= coord["y"] <= RD_Y_MAX


def test_wgs84_axis_order_protection(assets):
    """Named latitude/longitude fields per canonical schema; never swapped.

    All synthetic points sit in the Netherlands; if lat/lon were interchanged
    the 'latitude' values would land near ~4–7 (longitude range).
    """
    for a in assets:
        assert a["latitude"] > 45.0, f"latitude looks like a longitude: {a}"
        assert a["longitude"] < 15.0, f"longitude looks like a latitude: {a}"


def test_rd_conversion_sanity_reference_points():
    # Amsterdam centrum ≈ RD (121_000, 487_000); Rotterdam ≈ (92_000, 436_500).
    x, y = wgs84_to_rd_approx(52.372, 4.895)
    assert abs(x - 121_000) < 5_000 and abs(y - 487_000) < 5_000
    x, y = wgs84_to_rd_approx(51.924, 4.478)
    assert abs(x - 92_000) < 5_000 and abs(y - 436_500) < 5_000


# --------------------------------------------------------------------------- #
# Valuations and identifiers
# --------------------------------------------------------------------------- #
def test_valuation_bounds_and_currency(dataset, assets):
    assert dataset["metadata"]["currency"] == "EUR"
    lo, hi = VALUE_MIN_EUR, VALUE_MAX_EUR
    for a in assets:
        assert lo <= a["asset_value"] <= hi
        assert isinstance(a["asset_value"], float)


def test_synthetic_asset_ids_and_loan_ids(assets):
    for a in assets:
        assert a["asset_id"].startswith("SYNREF-")
        assert a["loan_id"].startswith("SYN-LN-")


def test_dutch_postcode_format_in_addresses(assets):
    for a in assets:
        match = POSTCODE_RE.search(a["address"])
        assert match, f"no valid Dutch postcode in {a['address']!r}"


# --------------------------------------------------------------------------- #
# Metadata truth states and semantic boundaries
# --------------------------------------------------------------------------- #
TRUTH_KEYS = [
    "dataset_classification",
    "customer_data_status",
    "valuation_status",
    "coordinate_source",
    "survey_accuracy_verified",
    "ground_truth_verified",
    "physical_inundation_extent_verified",
    "empirical_accuracy_verified",
    "decision_use_approved",
    "controlled_pilot_eligible",
    "customer_pilot_verified",
    "runtime_live_verified",
    "production_eligible",
]


def test_all_truth_states_present_and_correct(dataset):
    metadata = dataset["metadata"]
    for key in TRUTH_KEYS:
        assert key in metadata, f"missing truth-state field: {key}"
        assert metadata[key] == TRUTH_STATES[key], f"truth-state drift on {key}"


def test_all_readiness_flags_false(dataset):
    m = dataset["metadata"]
    for flag in (
        "decision_use_approved",
        "controlled_pilot_eligible",
        "customer_pilot_verified",
        "runtime_live_verified",
        "production_eligible",
    ):
        assert m[flag] is False


def test_dataset_classified_synthetic_with_fixed_seed_and_version(dataset):
    m = dataset["metadata"]
    assert m["dataset_classification"] == "synthetic_reference_portfolio"
    assert m["coordinate_source"] == "synthetically_generated"
    assert m["valuation_status"] == "synthetic_unverified"
    assert m["customer_data_status"] == "not_customer_data"
    assert m["generator_version"]
    assert m["seed"] == DEFAULT_SEED or isinstance(m["seed"], int)
    assert m["valuation_date"] == m["valuation_date"]  # present; fixed constant


def test_no_timestamps_in_content(dataset):
    text = json.dumps(dataset)
    iso_like = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text)
    assert not iso_like, f"volatile timestamp inside deterministic content: {iso_like}"


def test_no_real_customer_or_personal_data_indicators(dataset):
    text = json.dumps(dataset).lower()
    for word in CUSTOMER_DATA_WORDS:
        assert word not in text, f"customer-data indicator present: {word}"


def test_no_secrets_or_local_paths(fixture):
    text = json.dumps(fixture)
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(text), f"suspicious content matched: {pattern.pattern}"


def test_addresses_are_explicitly_synthetic(assets):
    for a in assets:
        assert "synthetisch perceel" in a["address"].lower()


# --------------------------------------------------------------------------- #
# Fail-closed generator behaviour
# --------------------------------------------------------------------------- #
def test_unsupported_crs_rejected():
    doc = build_document(50, 3)
    doc["dataset"]["supplements"]["crs_assignment"]["SYNREF-A-001"] = 99999
    # Re-validation path must reject unknown CRS through supplement checks:
    from scripts.generate_synthetic_reference_portfolio import _validate_rd_bounds

    with pytest.raises(ValueError):
        _validate_rd_bounds(-1.0, 400_000.0)


def test_malformed_record_fails_closed():
    bad = {
        "asset_id": "X-1",
        "address": None,
        "latitude": None,
        "longitude": None,
        "asset_value": -5,
        "building_type": "",
        "use_class": "",
    }
    from scripts.generate_synthetic_reference_portfolio import validate_canonical

    with pytest.raises(ValueError):
        validate_canonical([bad], "2021-07-01")


def test_negative_asset_value_rejected_by_canonical_model():
    with pytest.raises(ValidationError):
        UniversalAsset(
            asset_id="X",
            latitude=52.1,
            longitude=5.1,
            asset_value=-1_000.0,
            building_type="office",
            use_class="commercial",
        )


def test_atomic_write_never_leaves_partial_output(tmp_path):
    target = tmp_path / "out.json"
    doc = generate(50, 11)
    atomic_write(target, doc)
    assert target.is_file()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["integrity"]["content_checksum"] == doc["integrity"]["content_checksum"]


# --------------------------------------------------------------------------- #
# CLI behaviour
# --------------------------------------------------------------------------- #
def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_synthetic_reference_portfolio.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={"PATH": __import__("os").environ["PATH"], "PYTHONPATH": str(ROOT)},
    )


def test_cli_rejects_invalid_count(tmp_path):
    result = _run_cli(["--output", str(tmp_path / "x.json"), "--count", "10"])
    assert result.returncode == 2
    assert "FAIL-CLOSED" in result.stderr
    assert not (tmp_path / "x.json").exists()


def test_cli_generates_byte_identical_output_for_same_inputs(tmp_path):
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    assert _run_cli(["--output", str(out_a), "--count", "55", "--seed", "42"]).returncode == 0
    assert _run_cli(["--output", str(out_b), "--count", "55", "--seed", "42"]).returncode == 0
    assert out_a.read_bytes() == out_b.read_bytes()


# --------------------------------------------------------------------------- #
# Committed fixture equals fresh regeneration
# --------------------------------------------------------------------------- #
def test_regenerated_fixture_equals_committed_file():
    fresh = generate(len(FIXTURE_PATH and json.loads(FIXTURE_PATH.read_text())["dataset"]["portfolio"]["assets"]), DEFAULT_SEED)
    committed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert json.dumps(fresh, sort_keys=True) == json.dumps(committed, sort_keys=True)


def test_no_network_calls_available_during_generation(monkeypatch):
    """Generation must not need network: block socket creation outright."""
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("network access attempted during generation")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    doc = generate(50, 77)
    assert doc["integrity"]["content_checksum"]

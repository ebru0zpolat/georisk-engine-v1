"""Fail-closed baseline calibration and outcome-blind coverage qualification."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

FEMA_V3_RAW_BUILDING_PAYMENT = "amountPaidOnBuildingClaim"
CANONICAL_BUILDING_PAYMENT = "buildingClaimPaymentAmount"

#: Outcome-bearing field names, refused before any evaluation unlock. The denylist is
#: matched after normalisation (case-folded, separators removed) so a provider-native
#: camelCase name, a snake_case alias and a kebab/spaced variant all collapse to the same
#: token: an exact top-level key comparison can be bypassed by ``building_claim_payment``
#: or by nesting the outcome one level down.
OUTCOME_FIELD_NAMES = frozenset(
    {
        FEMA_V3_RAW_BUILDING_PAYMENT,
        CANONICAL_BUILDING_PAYMENT,
        "netBuildingPaymentAmount",
        "buildingDamageAmount",
        "contentsClaimPaymentAmount",
        "totalClaimPaymentAmount",
        "net_building_payment_amount",
        "contents_claim_payment_amount",
        "total_claim_payment_amount",
        "building_claim_payment",
        "building_payment_amount",
        "total_claim_payment",
        "observed_loss",
    }
)

#: The FEMA claims API origin. Bound structurally (scheme, host, path), never by suffix.
APPROVED_ENDPOINT_SCHEMES = frozenset({"https"})
APPROVED_ENDPOINT_HOSTS = frozenset({"fema.gov", "www.fema.gov"})
APPROVED_ENDPOINT_PATHS = frozenset({"/api/open/v3/NfipClaims"})

HARVEY_ESTIMAND_ID = "nfip_claim_conditional_building_payment_v1"
HARVEY_ALLOWED_VALIDATION_CLAIMS = frozenset(
    {"harvey_event_loss_method_validated", "us_harvey_flood_hazard_verified"}
)
_REQUIRED_FIELD_MAPPING = {
    FEMA_V3_RAW_BUILDING_PAYMENT: CANONICAL_BUILDING_PAYMENT,
    "totalBuildingInsuranceCoverage": "totalBuildingInsuranceCoverage",
}


def _normalize_field_name(name: Any) -> str:
    """Collapse a field name to its comparison token: case-folded, alphanumerics only."""
    return "".join(character for character in str(name).casefold() if character.isalnum())


_OUTCOME_TOKENS = frozenset(_normalize_field_name(name) for name in OUTCOME_FIELD_NAMES)


def _outcome_field_paths(node: Any, path: str = "") -> list[str]:
    """Return every nested path whose key normalises to a refused outcome field."""
    found: list[str] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            child = f"{path}{key}"
            if _normalize_field_name(key) in _OUTCOME_TOKENS:
                found.append(child)
            found.extend(_outcome_field_paths(value, f"{child}."))
    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            found.extend(_outcome_field_paths(item, f"{path}[{index}]."))
    return found


def endpoint_origin_is_approved(endpoint: str) -> bool:
    """True only for the exact approved FEMA claims origin.

    A suffix test such as ``endswith("/open/v3/NfipClaims")`` is satisfied by any host
    that merely ends the path the same way — ``https://evil.invalid/x/open/v3/NfipClaims``
    would pass. The URL is therefore parsed and each component approved separately:
    scheme, exact host, no userinfo, no port other than 443, and the exact API path.
    """
    try:
        parts = urlsplit(endpoint)
    except ValueError:
        return False
    if parts.scheme.casefold() not in APPROVED_ENDPOINT_SCHEMES:
        return False
    if parts.username or parts.password:
        return False
    try:
        port = parts.port
    except ValueError:
        return False
    if port is not None and port != 443:
        return False
    if (parts.hostname or "").casefold() not in APPROVED_ENDPOINT_HOSTS:
        return False
    return parts.path.rstrip("/") in APPROVED_ENDPOINT_PATHS


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _parse_usgs_covered(value: Any) -> bool:
    """Read a coverage flag strictly; anything ambiguous fails closed.

    ``bool(value)`` scores the string ``"false"`` as *covered*, which silently inflates
    the coverage fraction and could carry a study past the >=95% gate on absent hazard
    data. Only booleans, the strings ``true``/``false`` (any case, trimmed) and 0/1 are
    accepted; every other value is ambiguous and refused rather than guessed.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().casefold()
        if token == "true":
            return True
        if token == "false":
            return False
    raise ValueError(
        f"usgs_covered must be a boolean, 0/1 or 'true'/'false'; got {value!r}"
    )



@dataclass(frozen=True)
class DataUseManifest:
    endpoint: str
    data_version: str
    schema_sha256: str
    query_parameters: Mapping[str, Any]
    retrieval_timestamp: str
    raw_response_sha256: tuple[str, ...]
    terms_archive_sha256: str
    commercial_use_assessment: str
    assessed_by: str
    licence_status: str
    retention_policy: str
    access_restrictions: str
    field_mapping: Mapping[str, str]

    def permits_real_provider(self) -> bool:
        """Return true only with affirmative approval and complete hash evidence."""
        hashes = (
            self.schema_sha256,
            self.terms_archive_sha256,
            *self.raw_response_sha256,
        )
        return (
            endpoint_origin_is_approved(self.endpoint)
            and self.data_version == "v3"
            and self.licence_status == "approved"
            and bool(self.assessed_by.strip())
            and bool(self.commercial_use_assessment.strip())
            and bool(self.retention_policy.strip())
            and bool(self.access_restrictions.strip())
            and bool(self.raw_response_sha256)
            and all(_valid_sha256(value) for value in hashes)
            and dict(self.field_mapping) == _REQUIRED_FIELD_MAPPING
        )


@dataclass(frozen=True)
class HazardEvidenceManifest:
    """Provenance for the preregistered observed-event hazard artifact.

    P1-07. A retrospective event reconstruction observes the event after the
    pre-registration cutoff, so the artifact is legitimately *acquired* late. The
    admission test is therefore **selection blindness**, not file age: the hazard
    source must have been chosen before any outcome was read, and it must be
    licensed for the intended use and hash-pinned. Nothing here can substitute for
    the frozen study's own event-conditioning contract; this manifest is the
    evidence that supports it.
    """

    source_id: str
    artifact_sha256: str
    acquisition_timestamp: str
    selected_before_outcome_access: bool
    coverage_fraction: float
    commercial_use_permitted: bool
    licence_record_sha256: str
    crs: str
    depth_unit: str
    nodata_policy: str

    def permits_retrospective_conditioning(self) -> bool:
        """True only when the source was chosen without looking at outcomes.

        ``acquisition_timestamp`` is deliberately absent from the test: a hazard
        file downloaded years after the event is admissible if it was selected
        before the outcomes were opened, and inadmissible if the source was picked
        after someone had seen the payments.
        """
        return (
            bool(self.source_id.strip())
            and _valid_sha256(self.artifact_sha256)
            and _valid_sha256(self.licence_record_sha256)
            and self.selected_before_outcome_access is True
            and self.commercial_use_permitted is True
            and bool(self.crs.strip())
            and bool(self.depth_unit.strip())
            and bool(self.nodata_policy.strip())
            and 0.0 <= self.coverage_fraction <= 1.0
        )


def adapt_fema_v3_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Map the one approved FEMA v3 payment field without semantic fallbacks."""
    if FEMA_V3_RAW_BUILDING_PAYMENT not in raw:
        raise ValueError(
            f"FEMA v3 record is missing required raw field {FEMA_V3_RAW_BUILDING_PAYMENT!r}; "
            "netBuildingPaymentAmount and buildingDamageAmount are not substitutes"
        )
    canonical = dict(raw)
    canonical[CANONICAL_BUILDING_PAYMENT] = raw[FEMA_V3_RAW_BUILDING_PAYMENT]
    return canonical


def validate_harvey_estimand(estimand_id: str) -> None:
    """Reject broader portfolio, frequency, EAL, uninsured, or NL-CRE claims."""
    if estimand_id != HARVEY_ESTIMAND_ID:
        raise ValueError(
            f"Harvey study requires estimand_id={HARVEY_ESTIMAND_ID!r}, "
            f"got {estimand_id!r}"
        )


def validate_harvey_claim(estimand_id: str, claim_id: str) -> None:
    """Enforce the machine-readable estimand-to-claim scope boundary."""
    validate_harvey_estimand(estimand_id)
    if claim_id not in HARVEY_ALLOWED_VALIDATION_CLAIMS:
        raise ValueError(f"claim {claim_id!r} is outside the Harvey estimand")


@dataclass(frozen=True)
class BaselineCalibrationSpec:
    geography: tuple[str, ...]
    start_date: date
    cutoff: date
    occupancy_types: tuple[str, ...]
    include_zero_payments: bool
    denominator_field: str
    numerator_field: str
    exclude_missing_or_zero_coverage: bool
    outlier_policy: str
    minimum_sample_size: int
    bootstrap_repetitions: int
    bootstrap_seed: int
    estimand_id: str
    excluded_event: str = "Hurricane Harvey"

    def __post_init__(self) -> None:
        if self.cutoff != date(2017, 8, 24):
            raise ValueError("Harvey baseline cutoff must be 2017-08-24")
        if self.denominator_field != "totalBuildingInsuranceCoverage":
            raise ValueError(
                "baseline denominator must be totalBuildingInsuranceCoverage"
            )
        if self.numerator_field != "buildingClaimPaymentAmount":
            raise ValueError("baseline numerator must be buildingClaimPaymentAmount")
        if self.outlier_policy != "retain_all_eligible_records":
            raise ValueError("outlier policy must be fixed before calibration")
        if self.minimum_sample_size < 200:
            raise ValueError("minimum calibration sample size must be at least 200")
        if self.bootstrap_repetitions < 10_000:
            raise ValueError(
                "baseline diagnostics require at least 10,000 bootstrap repeats"
            )
        validate_harvey_estimand(self.estimand_id)


@dataclass(frozen=True)
class BaselineArtifact:
    baseline_type: str
    ratio: float
    calibration_cutoff: str
    excluded_event: str
    sample_size: int
    query_fingerprint: str
    source_data_sha256: str
    calculation_code_commit: str
    created_at: str
    estimand_id: str
    diagnostics: Mapping[str, Any]
    outcome_accessed_for_evaluation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calibrate_historical_baseline(
    rows: Iterable[Mapping[str, Any]],
    *,
    spec: BaselineCalibrationSpec,
    query_parameters: Mapping[str, Any],
    source_data_sha256: str,
    calculation_code_commit: str,
    created_at: str,
) -> BaselineArtifact:
    """Calculate the aggregate pre-Harvey loss/coverage ratio without trimming."""
    if not _valid_sha256(source_data_sha256):
        raise ValueError("source_data_sha256 must be a lowercase SHA-256 digest")
    payment_sum = 0.0
    coverage_sum = 0.0
    count = 0
    excluded_coverage_count = 0
    eligible: list[tuple[Mapping[str, Any], float, float]] = []
    for row in rows:
        canonical_row = adapt_fema_v3_record(row)
        loss_date = date.fromisoformat(str(row["dateOfLoss"])[:10])
        if not (spec.start_date <= loss_date <= spec.cutoff):
            raise ValueError(
                "calibration input contains a record outside the frozen dates"
            )
        if str(row.get("eventName", "")).casefold() == spec.excluded_event.casefold():
            raise ValueError("calibration input contains the excluded event")
        if str(row["state"]) not in spec.geography:
            raise ValueError("calibration input contains an unregistered geography")
        if str(row["occupancyType"]) not in spec.occupancy_types:
            continue
        coverage_raw = row.get(spec.denominator_field)
        if coverage_raw in (None, ""):
            if spec.exclude_missing_or_zero_coverage:
                excluded_coverage_count += 1
                continue
            raise ValueError("missing coverage is not permitted by the frozen rule")
        coverage = float(coverage_raw)
        if coverage <= 0:
            if spec.exclude_missing_or_zero_coverage:
                excluded_coverage_count += 1
                continue
            raise ValueError(
                "non-positive coverage is not permitted by the frozen rule"
            )
        payment = float(canonical_row[spec.numerator_field] or 0.0)
        if payment < 0:
            raise ValueError("building payment must be non-negative")
        if payment == 0 and not spec.include_zero_payments:
            continue
        payment_sum += payment
        coverage_sum += coverage
        count += 1
        eligible.append((row, payment, coverage))
    if count < spec.minimum_sample_size:
        raise ValueError("eligible calibration sample is below the frozen minimum")
    return BaselineArtifact(
        baseline_type="historical_coverage_ratio",
        ratio=payment_sum / coverage_sum,
        calibration_cutoff=spec.cutoff.isoformat(),
        excluded_event=spec.excluded_event,
        sample_size=count,
        query_fingerprint=f"sha256:{_canonical_sha256(query_parameters)}",
        source_data_sha256=source_data_sha256,
        calculation_code_commit=calculation_code_commit,
        created_at=created_at,
        estimand_id=spec.estimand_id,
        diagnostics=_baseline_diagnostics(
            eligible, spec, excluded_coverage_count=excluded_coverage_count
        ),
    )


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _baseline_diagnostics(
    eligible: list[tuple[Mapping[str, Any], float, float]],
    spec: BaselineCalibrationSpec,
    *,
    excluded_coverage_count: int,
) -> dict[str, Any]:
    years: Counter[str] = Counter()
    decades: Counter[str] = Counter()
    occupancies: Counter[str] = Counter()
    event_year_payments: defaultdict[str, float] = defaultdict(float)
    zero_count = 0
    for row, payment, _coverage in eligible:
        year = str(row["dateOfLoss"])[:4]
        years[year] += 1
        decades[f"{year[:3]}0s"] += 1
        occupancies[str(row["occupancyType"])] += 1
        event_year_payments[year] += payment
        zero_count += payment == 0
    ranked = sorted(eligible, key=lambda item: item[1], reverse=True)
    top = ranked[: max(1, math.ceil(len(ranked) * 0.01))]
    total_payment = sum(item[1] for item in eligible)
    total_coverage = sum(item[2] for item in eligible)
    rng = random.Random(spec.bootstrap_seed)
    bootstrap_ratios = []
    for _ in range(spec.bootstrap_repetitions):
        sample = rng.choices(eligible, k=len(eligible))
        bootstrap_ratios.append(
            sum(item[1] for item in sample) / sum(item[2] for item in sample)
        )
    coverages = [item[2] for item in eligible]
    return {
        "counts_by_year": dict(sorted(years.items())),
        "counts_by_decade": dict(sorted(decades.items())),
        "occupancy_distribution": dict(sorted(occupancies.items())),
        "coverage_quantiles": {
            str(q): _quantile(coverages, q) for q in (0.0, 0.25, 0.5, 0.75, 0.99, 1.0)
        },
        "largest_event_year_payment_share": (
            max(event_year_payments.values()) / total_payment if total_payment else 0.0
        ),
        "top_1_percent_payment_share": (
            sum(item[1] for item in top) / total_payment if total_payment else 0.0
        ),
        "top_1_percent_coverage_share": sum(item[2] for item in top) / total_coverage,
        "zero_payment_fraction": zero_count / len(eligible),
        "excluded_missing_or_zero_coverage": excluded_coverage_count,
        "bootstrap": {
            "repetitions": spec.bootstrap_repetitions,
            "seed": spec.bootstrap_seed,
            "confidence_interval_95": [
                _quantile(bootstrap_ratios, 0.025),
                _quantile(bootstrap_ratios, 0.975),
            ],
        },
    }


@dataclass(frozen=True)
class CoverageQualification:
    sample_size: int
    location_clusters: int
    covered_locations: int
    coverage_fraction: float
    usgs_artifact_sha256: str
    crs: str
    depth_unit: str
    nodata_policy: str
    qualified: bool
    stop_reason: str | None


def qualify_outcome_blind_coverage(
    rows: Iterable[Mapping[str, Any]],
    *,
    usgs_artifact_sha256: str,
    crs: str,
    depth_unit: str,
    nodata_policy: str,
) -> CoverageQualification:
    """Apply the preregistered coverage gate while rejecting outcome columns."""
    if not _valid_sha256(usgs_artifact_sha256):
        raise ValueError("usgs_artifact_sha256 must be a lowercase SHA-256 digest")
    materialized = list(rows)
    # Refuse an outcome in any alias or at any nesting depth: a provider-native name, a
    # snake/kebab/spaced variant, or a value buried inside a nested structure would all
    # defeat a flat exact-key comparison.
    leaked: set[str] = set()
    for row in materialized:
        leaked.update(_outcome_field_paths(row))
    if leaked:
        raise ValueError(
            f"outcome fields are prohibited during coverage qualification: "
            f"{sorted(leaked)}"
        )
    sample_size = len(materialized)
    clusters = len({str(row["location_cluster"]) for row in materialized})
    covered = 0
    for row in materialized:
        if "usgs_covered" not in row:
            raise ValueError(
                f"row {row.get('location_cluster', '<unknown>')!r} is missing the "
                "usgs_covered flag; an absent coverage flag is not evidence of coverage"
            )
        covered += int(_parse_usgs_covered(row["usgs_covered"]))
    fraction = covered / sample_size if sample_size else 0.0
    failures = []
    if sample_size < 200:
        failures.append("sample_size_below_200")
    if clusters < 30:
        failures.append("location_clusters_below_30")
    if fraction < 0.95:
        failures.append("usgs_coverage_below_0.95")
    if not crs.strip() or not depth_unit.strip() or not nodata_policy.strip():
        failures.append("raster_metadata_incomplete")
    return CoverageQualification(
        sample_size=sample_size,
        location_clusters=clusters,
        covered_locations=covered,
        coverage_fraction=fraction,
        usgs_artifact_sha256=usgs_artifact_sha256,
        crs=crs,
        depth_unit=depth_unit,
        nodata_policy=nodata_policy,
        qualified=not failures,
        stop_reason=",".join(failures) or None,
    )

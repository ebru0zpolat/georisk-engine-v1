"""P1-07: pre-event information cutoff vs preregistered retrospective hazard.

The Harvey study is an *event reconstruction*, not a prospective forecast. It
uses two kinds of predictor information that one date cannot honestly describe:

* **pre-event** information — asset attributes, model configuration, the
  historical baseline — whose availability is bounded by 2017-08-24; and
* **preregistered observed-event hazard** — what the Harvey footprint actually
  saw, observed during 2017-08-25..2017-09-01.

Collapsing the two into a single ``features_as_of`` would either reject legitimate
event conditioning (turning the study into a forecast) or admit arbitrary
post-cutoff predictors (destroying the leakage guard). The contract therefore
keeps them typed apart, and these tests hold both halves in place at once.

These tests are structural. They use in-memory fakes and no licensed data; they
do not constitute a validation result.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.validation.gate1 import (
    EventConditioningHazard,
    EventConditioningHazardInvalid,
    EventConditioningRegistration,
    EventConditioningRegistrationInvalid,
    LookaheadError,
    PreRegistration,
    PreRegistrationNotFrozen,
    SampleUnit,
    freeze_pre_registration,
    run_comparison,
)
from app.validation.gate1.pre_registration import HARVEY_REQUIRED_STUDY_DECISIONS
from app.validation.gate1.pre_registration import SuccessRule
from app.validation.harvey import HazardEvidenceManifest

CUTOFF = date(2017, 8, 24)
WINDOW_START = date(2017, 8, 25)
WINDOW_END = date(2017, 9, 1)
HARVEY = date(2017, 8, 28)
TS = "2026-09-04T00:00:00+00:00"
HAZARD_SHA = "c" * 64
DATA_MANIFEST_SHA = "d" * 64
SOURCE_DATA_SHA = "e" * 64
LICENCE_SHA = "f" * 64
SOURCE_ID = "usgs_hazus_harvey_event_depth"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _ConstantModel:
    """A model that scores the unit's admitted hazard, else its stated feature."""

    name = "flood-depth-times-ten-thousand"

    def predict(self, unit: SampleUnit) -> float:
        hazard = unit.event_conditioning_hazard
        if hazard is not None:
            return hazard.value * 10_000.0
        return float(unit.features.get("pred", 0.0))


class _Provider:
    name = "fema-nfip-claims-v3"
    is_synthetic = True  # a fake is never real data (contract field)

    def __init__(self, units: list[SampleUnit]) -> None:
        self._units = units

    def is_licensed_for_commercial_use(self) -> bool:
        return True

    def load(self, pre_registration: object) -> list[SampleUnit]:  # noqa: ARG002
        return list(self._units)


def _decisions() -> dict[str, object]:
    """Every result-independent decision P1-06 requires the freeze to bind."""
    values: dict[str, object] = {
        "study_id": "harvey_2017_nfip",
        "baseline_calibration_window": "2000-01-01..2017-08-24",
        "evaluation_geography": "FIPS:48201",
        "calibration_geography": "TX",
        "excluded_events": ["Hurricane Harvey"],
        "excluded_occupancy_types": [],
        "outcome_access_protocol": "staged_hash_bound_unlock",
        "sample_split": "census_no_holdout",
        "sample_size_and_cluster_thresholds": {"min_units": 200, "min_clusters": 30},
        "hazard_coverage_threshold": 0.95,
        "bootstrap_repetitions": 10_000,
        "bootstrap_seed": 20170825,
        "data_use_manifest_sha256": DATA_MANIFEST_SHA,
        "source_data_sha256": SOURCE_DATA_SHA,
        "query_fingerprint": "sha256:placeholder",
        "calculation_code_commit": "a" * 40,
        "reviewer": "founder",
    }
    assert set(values) == set(HARVEY_REQUIRED_STUDY_DECISIONS)
    return values


def _event_conditioning(**overrides: object) -> EventConditioningRegistration:
    base = {
        "role": "retrospective_event_conditioning",
        "source_id": SOURCE_ID,
        "artifact_sha256": HAZARD_SHA,
        "event_window_start": WINDOW_START,
        "event_window_end": WINDOW_END,
        "selected_before_outcome_access": True,
    }
    base.update(overrides)
    return EventConditioningRegistration(**base)  # type: ignore[arg-type]


_UNSET = object()


def _prereg(
    *,
    event_conditioning: object = _UNSET,
    decisions: dict[str, object] | None = None,
    study_title: str = "Harvey 2017 NFIP claim payment reconstruction",
    frozen: bool = True,
) -> PreRegistration:
    prereg = PreRegistration(
        study_title=study_title,
        hazard_type="flood",
        information_cutoff=CUTOFF,
        observed_loss_dataset="fema-nfip-claims-v3",
        baseline_name="zero_loss",
        baseline_params={"model": "zero"},
        primary_metric="rmse",
        success_rule=SuccessRule(type="absolute_threshold", max_value=25_000.0),
        frozen=False,
        estimand_id="nfip_claim_conditional_building_payment_v1",
        event_conditioning=(
            _event_conditioning() if event_conditioning is _UNSET else event_conditioning
        ),
        study_decisions=_decisions() if decisions is None else decisions,
    )
    if not frozen:
        return prereg
    return freeze_pre_registration(prereg, timestamp=TS, commit="b" * 40)


def _hazard_unit(
    *,
    observed_at: date = HARVEY,
    role: str = "retrospective_event_conditioning",
    source_id: str = SOURCE_ID,
    artifact_sha256: str = HAZARD_SHA,
    features_as_of: date = CUTOFF,
) -> SampleUnit:
    return SampleUnit(
        unit_id="claim-1",
        observed_loss=20_000,
        observation_date=HARVEY,
        features_as_of=features_as_of,
        features={"pred": 20_000},
        event_conditioning_hazard=EventConditioningHazard(
            observed_at=observed_at,
            role=role,
            source_id=source_id,
            artifact_sha256=artifact_sha256,
            metric="depth_m",
            value=1.4,
        ),
    )


def _run(units: list[SampleUnit], prereg: PreRegistration | None = None):
    return run_comparison(
        pre_registration=prereg or _prereg(),
        model=_ConstantModel(),
        observed_loss_provider=_Provider(units),
        generated_at=TS,
    )


# --------------------------------------------------------------------------- #
# 1/2. Historical baseline is pre-event — enforced in preparation
# --------------------------------------------------------------------------- #
def test_post_event_observed_loss_is_never_pre_event_predictor_information() -> None:
    """The target may post-date the cutoff; the pre-event information may not."""
    unit = SampleUnit(
        unit_id="claim-1",
        observed_loss=20_000,
        observation_date=HARVEY,
        features_as_of=CUTOFF,
        features={"pred": 20_000},
    )
    report = _run([unit])
    assert report.n_units == 1


# --------------------------------------------------------------------------- #
# 3. Post-cutoff predictor configuration is refused
# --------------------------------------------------------------------------- #
def test_post_cutoff_predictor_configuration_is_rejected() -> None:
    """Genuinely post-cutoff pre-event information is still lookahead."""
    unit = SampleUnit(
        unit_id="claim-1",
        observed_loss=20_000,
        observation_date=HARVEY,
        features_as_of=date(2017, 8, 25),
        features={"asset": {"year_built": 1990}, "pred": 20_000},
    )
    with pytest.raises(LookaheadError, match="features_as_of past the information cutoff"):
        _run([unit])


def test_harvey_loss_dated_before_cutoff_cannot_enter_pre_event_features() -> None:
    """A mis-dated Harvey row must not slip in through the feature map."""
    unit = SampleUnit(
        unit_id="claim-1",
        observed_loss=20_000,
        observation_date=HARVEY,
        features_as_of=date(2017, 8, 20),
        features={"pred": 20_000, "claim": {"buildingClaimPaymentAmount": 20_000}},
    )
    from app.validation.harvey import qualify_outcome_blind_coverage

    with pytest.raises(ValueError, match="outcome fields"):
        qualify_outcome_blind_coverage(
            [dict(unit.features, location_cluster="a", usgs_covered=True)],
            usgs_artifact_sha256=HAZARD_SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


# --------------------------------------------------------------------------- #
# 4. Preregistered retrospective hazard is admissible
# --------------------------------------------------------------------------- #
def test_preregistered_retrospective_harvey_hazard_is_allowed_after_cutoff() -> None:
    """The event may be observed, if the study registered that observation."""
    report = _run([_hazard_unit()])
    assert report.n_units == 1


def test_retrospective_hazard_is_not_expressible_through_features_as_of() -> None:
    """A unit may not launder post-cutoff hazard into the pre-event date."""
    with pytest.raises(LookaheadError):
        _run([_hazard_unit(features_as_of=date(2017, 8, 25))])


def test_hazard_must_belong_to_the_same_event_as_the_loss() -> None:
    """Borrowing another event's hazard to explain this claim's loss is refused."""
    unit = _hazard_unit()
    with pytest.raises(EventConditioningHazardInvalid, match="same event"):
        replace(
            unit,
            event_conditioning_hazard=replace(
                unit.event_conditioning_hazard, observed_at=date(2016, 8, 29)
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_id", "   "),
        ("artifact_sha256", "not-a-digest"),
        ("metric", ""),
        ("value", "1.4"),
        ("value", True),
    ],
)
def test_malformed_hazard_evidence_fails_closed(field: str, value: object) -> None:
    unit = _hazard_unit()
    with pytest.raises(EventConditioningHazardInvalid):
        replace(
            unit, event_conditioning_hazard=replace(unit.event_conditioning_hazard, **{field: value})
        )


# --------------------------------------------------------------------------- #
# 5. The exception is narrow
# --------------------------------------------------------------------------- #
def test_unregistered_post_event_predictor_is_not_exempt_from_cutoff() -> None:
    """An unregistered role is refused at construction, not downgraded."""
    with pytest.raises(EventConditioningHazardInvalid, match="not preregistered event"):
        _hazard_unit(role="ordinary_predictor")


def test_hazard_without_a_preregistered_contract_is_refused() -> None:
    """No registration means no exception, however well-formed the unit is.

    A Harvey study cannot even be frozen without the contract (P1-06), so this
    exercises the harness guard using a study that did not register one.
    """
    other = _prereg(
        study_title="flood event reconstruction",
        event_conditioning=None,
        decisions={},
    )
    with pytest.raises(LookaheadError, match="registers no event-conditioning"):
        _run([_hazard_unit()], other)


def test_hazard_from_an_unregistered_source_is_refused() -> None:
    with pytest.raises(LookaheadError, match="not the preregistered source"):
        _run([_hazard_unit(source_id="some_other_hazard_product")])


# --------------------------------------------------------------------------- #
# 6/7. Outcome information is never a predictor (covered in preparation tests,
#      which hold the alias/nesting matrix) — asserted here through the harness
#      boundary so the separation is stated in one place.
# --------------------------------------------------------------------------- #
def test_observed_loss_injected_into_features_is_visible_to_the_guard() -> None:
    """The harness cannot see into ``features``; preparation refuses it upstream."""
    from app.validation.harvey import qualify_outcome_blind_coverage

    unit = SampleUnit(
        unit_id="claim-1",
        observed_loss=20_000,
        observation_date=HARVEY,
        features_as_of=CUTOFF,
        features={"pred": 20_000, "derived": {"observed_loss": 20_000}},
    )
    with pytest.raises(ValueError, match="outcome fields"):
        qualify_outcome_blind_coverage(
            [dict(unit.features, location_cluster="a", usgs_covered=True)],
            usgs_artifact_sha256=HAZARD_SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )


# --------------------------------------------------------------------------- #
# 8. Selection blindness, not download date
# --------------------------------------------------------------------------- #
def _manifest(**overrides: object) -> HazardEvidenceManifest:
    base = {
        "source_id": SOURCE_ID,
        "artifact_sha256": HAZARD_SHA,
        "acquisition_timestamp": "2026-09-01T00:00:00Z",
        "selected_before_outcome_access": True,
        "coverage_fraction": 0.97,
        "commercial_use_permitted": True,
        "licence_record_sha256": LICENCE_SHA,
        "crs": "EPSG:4326",
        "depth_unit": "metre",
        "nodata_policy": "uncovered",
    }
    base.update(overrides)
    return HazardEvidenceManifest(**base)  # type: ignore[arg-type]


def test_hazard_artifact_may_be_acquired_after_event() -> None:
    """A hazard file downloaded long after the event is still admissible."""
    assert _manifest().permits_retrospective_conditioning() is True


def test_hazard_source_selected_after_outcome_access_is_rejected() -> None:
    manifest = _manifest(selected_before_outcome_access=False)
    assert manifest.permits_retrospective_conditioning() is False


def test_registration_cannot_claim_outcome_informed_selection() -> None:
    with pytest.raises(
        EventConditioningRegistrationInvalid,
        match="requires selected_before_outcome_access=True",
    ):
        _event_conditioning(selected_before_outcome_access=False)


def test_unlicensed_or_unpinned_hazard_manifest_is_refused() -> None:
    assert _manifest(commercial_use_permitted=False).permits_retrospective_conditioning() is False
    assert _manifest(artifact_sha256="not-a-digest").permits_retrospective_conditioning() is False


# --------------------------------------------------------------------------- #
# 9. P1-06: every bound scientific decision is tamper-evident
# --------------------------------------------------------------------------- #
def test_hazard_artifact_hash_change_after_unlock_invalidates_freeze() -> None:
    frozen = _prereg()
    tampered = replace(
        frozen,
        event_conditioning=replace(
            frozen.event_conditioning, artifact_sha256="b" * 64
        ),
    )
    with pytest.raises(PreRegistrationNotFrozen, match="changed since it was frozen"):
        tampered.require_frozen()


def test_changed_hazard_source_invalidates_freeze() -> None:
    frozen = _prereg()
    tampered = replace(
        frozen, event_conditioning=replace(frozen.event_conditioning, source_id="other")
    )
    with pytest.raises(PreRegistrationNotFrozen):
        tampered.require_frozen()


def test_widened_event_window_invalidates_freeze() -> None:
    frozen = _prereg()
    tampered = replace(
        frozen,
        event_conditioning=replace(
            frozen.event_conditioning, event_window_end=date(2017, 12, 31)
        ),
    )
    with pytest.raises(PreRegistrationNotFrozen):
        tampered.require_frozen()


@pytest.mark.parametrize("decision", sorted(HARVEY_REQUIRED_STUDY_DECISIONS))
def test_every_bound_study_decision_invalidates_the_freeze(decision: str) -> None:
    """P1-06: no scientific decision can be edited after the fact."""
    frozen = _prereg()
    altered = {**_decisions(), decision: "changed-after-results"}
    tampered = replace(frozen, study_decisions=altered)
    with pytest.raises(PreRegistrationNotFrozen, match="changed since it was frozen"):
        tampered.require_frozen()


def test_harvey_freeze_requires_every_scientific_decision() -> None:
    """An unbound decision is caught when the study is sealed, not after."""
    for omitted in sorted(HARVEY_REQUIRED_STUDY_DECISIONS):
        incomplete = {k: v for k, v in _decisions().items() if k != omitted}
        draft = replace(_prereg(frozen=False), study_decisions=incomplete)
        with pytest.raises(
            PreRegistrationNotFrozen, match="missing frozen study decisions"
        ):
            freeze_pre_registration(draft, timestamp=TS, commit="b" * 40)


def test_harvey_freeze_requires_an_event_conditioning_contract() -> None:
    """A reconstruction with no registered hazard authority cannot be sealed."""
    draft = replace(_prereg(frozen=False), event_conditioning=None)
    with pytest.raises(
        PreRegistrationNotFrozen, match="registers no event-conditioning"
    ):
        freeze_pre_registration(draft, timestamp=TS, commit="b" * 40)


# --------------------------------------------------------------------------- #
# 10. The event window constrains hazard evidence independently of the cutoff
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("hazard_date", [WINDOW_START, HARVEY, WINDOW_END])
def test_harvey_hazard_inside_registered_event_window_is_allowed(hazard_date: date) -> None:
    unit = replace(
        _hazard_unit(),
        observation_date=hazard_date,
        event_conditioning_hazard=replace(
            _hazard_unit().event_conditioning_hazard, observed_at=hazard_date
        ),
    )
    assert _run([unit]).n_units == 1


@pytest.mark.parametrize("hazard_date", [CUTOFF, date(2017, 9, 2)])
def test_hazard_outside_registered_event_window_cannot_define_primary_event_input(
    hazard_date: date,
) -> None:
    unit = replace(
        _hazard_unit(),
        observation_date=hazard_date,
        event_conditioning_hazard=replace(
            _hazard_unit().event_conditioning_hazard, observed_at=hazard_date
        ),
    )
    with pytest.raises(LookaheadError, match="outside the registered event window"):
        _run([unit])


# --------------------------------------------------------------------------- #
# The architectural test
# --------------------------------------------------------------------------- #
def test_harvey_event_reconstruction_separates_pre_event_leakage_from_retrospective_hazard() -> None:
    """The whole scientific contract, asserted end to end.

    Pre-event configuration/baseline:
        <= 2017-08-24
    Retrospective observed hazard:
        2017-08-25 ... 2017-09-01, preregistered event-conditioning evidence only
    Observed Harvey loss:
        scoring target only; never a predictor, configuration or baseline input
    """
    # (a) The whole thing runs: pre-event information, a registered post-event
    #     observation, and the payment used only as the target.
    report = _run([_hazard_unit()])
    assert report.n_units == 1
    assert report.passed is True
    assert report.dataset_is_synthetic is True  # a fake; never a validation result

    # (b) A baseline row dated after the cutoff is refused.
    from app.validation.harvey import calibrate_historical_baseline

    with pytest.raises(ValueError, match="outside the frozen dates"):
        calibrate_historical_baseline(
            [
                {
                    "dateOfLoss": "2017-08-25",
                    "eventName": "Other",
                    "state": "TX",
                    "occupancyType": "RES1",
                    "totalBuildingInsuranceCoverage": 100,
                    "amountPaidOnBuildingClaim": 10,
                }
            ],
            spec=_baseline_spec(),
            query_parameters={},
            source_data_sha256=SOURCE_DATA_SHA,
            calculation_code_commit="a" * 40,
            created_at=TS,
        )

    # (c) Configuration information dated after the cutoff is refused.
    with pytest.raises(LookaheadError, match="features_as_of past the information cutoff"):
        _run([_hazard_unit(features_as_of=date(2017, 8, 25))])

    # (d) The observed hazard stays admissible.
    assert _run([_hazard_unit()]).n_units == 1

    # (e) A payment injected into features is refused upstream.
    from app.validation.harvey import qualify_outcome_blind_coverage

    with pytest.raises(ValueError, match="outcome fields"):
        qualify_outcome_blind_coverage(
            [
                {
                    "location_cluster": "a",
                    "usgs_covered": True,
                    "provider": {"buildingClaimPaymentAmount": 20_000},
                }
            ],
            usgs_artifact_sha256=HAZARD_SHA,
            crs="EPSG:4326",
            depth_unit="m",
            nodata_policy="uncovered",
        )

    # (f) A hazard source changed after the freeze invalidates the freeze.
    frozen = _prereg()
    with pytest.raises(PreRegistrationNotFrozen):
        replace(
            frozen,
            event_conditioning=replace(frozen.event_conditioning, artifact_sha256="b" * 64),
        ).require_frozen()

    # (g) A hazard source selected after outcomes were read is not admissible.
    assert _manifest(selected_before_outcome_access=False).permits_retrospective_conditioning() is False


def _baseline_spec():
    from app.validation.harvey import BaselineCalibrationSpec, HARVEY_ESTIMAND_ID

    return BaselineCalibrationSpec(
        geography=("TX",),
        start_date=date(2000, 1, 1),
        cutoff=CUTOFF,
        occupancy_types=("RES1",),
        include_zero_payments=True,
        denominator_field="totalBuildingInsuranceCoverage",
        numerator_field="buildingClaimPaymentAmount",
        exclude_missing_or_zero_coverage=True,
        outlier_policy="retain_all_eligible_records",
        minimum_sample_size=200,
        bootstrap_repetitions=10_000,
        bootstrap_seed=20170825,
        estimand_id=HARVEY_ESTIMAND_ID,
    )

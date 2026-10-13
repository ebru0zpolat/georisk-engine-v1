"""Observed-loss sample units and the fail-closed provider seam.

A :class:`SampleUnit` is one unit of analysis (an asset, grid cell, parcel …)
carrying the *features* a predictor may use and the *observed loss* it is scored
against. Providers load a study's sample from a licensed dataset.

Two kinds of predictor information exist and they are typed apart, because one
date cannot honestly describe both:

``features_as_of``
    The information cutoff of the unit's **pre-event** inputs — asset attributes,
    model configuration, exposure, baseline. Must be on or before the study's
    pre-registered cutoff; the harness refuses otherwise (:class:`LookaheadError`).

``event_conditioning_hazard``
    Preregistered *observed event* hazard evidence (e.g. the depth a claim's
    footprint saw during a named historical event). Physical availability of
    that observation follows the event, so it is **not** a pre-event input and
    must not be encoded in ``features_as_of``. It is admitted only as a typed,
    registered role bounded by the study's event window, an artifact hash, and
    outcome-blind source selection. See
    :class:`EventConditioningHazard`.

The default :class:`UnlicensedObservedLossProvider` raises on ``load`` — the
harness therefore cannot run until a real, licensed provider is supplied
(criterion 1.3). This is intentional: a silent fallback to synthetic data would
void Gate 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol, runtime_checkable

#: The only hazard role that may carry post-cutoff information. Any other role is
#: ordinary pre-event predictor input and stays bound by ``features_as_of``.
RETROSPECTIVE_EVENT_CONDITIONING = "retrospective_event_conditioning"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class EventConditioningHazardInvalid(ValueError):
    """Raised when event-conditioning hazard evidence is malformed or unregistered.

    Fail-closed: a unit that *declares* retrospective hazard but cannot prove the
    preregistration (role, window, source identity, artifact hash) is refused,
    never downgraded to an ordinary predictor.
    """


@dataclass(frozen=True)
class EventConditioningHazard:
    """Preregistered observed-event hazard evidence for one unit.

    This is the only route by which information that post-dates the
    pre-registration cutoff may reach a predictor, and it is deliberately
    expensive to construct: every field is required, and the harness
    cross-checks it against the frozen study before the unit is scored.

    Attributes:
        observed_at: Date the hazard was physically observed (the event date),
            which may post-date the information cutoff.
        role: Must be :data:`RETROSPECTIVE_EVENT_CONDITIONING`. A unit claiming a
            different role is refused rather than reclassified.
        source_id: Stable identifier of the hazard product, e.g.
            ``"usgs_hazus_harvey_event_depth"``. Bound by the study's freeze.
        artifact_sha256: Lowercase SHA-256 of the frozen hazard artifact.
        metric: Hazard quantity, e.g. ``"depth_m"``.
        value: The observed value in the declared metric's unit.
    """

    observed_at: date
    role: str
    source_id: str
    artifact_sha256: str
    metric: str
    value: float

    def __post_init__(self) -> None:
        if self.role != RETROSPECTIVE_EVENT_CONDITIONING:
            raise EventConditioningHazardInvalid(
                f"hazard role {self.role!r} is not preregistered event "
                f"conditioning; the only admissible role is "
                f"{RETROSPECTIVE_EVENT_CONDITIONING!r}"
            )
        if not self.source_id.strip():
            raise EventConditioningHazardInvalid(
                "event-conditioning hazard requires a non-empty source_id"
            )
        if not _SHA256_RE.match(self.artifact_sha256):
            raise EventConditioningHazardInvalid(
                "event-conditioning hazard artifact_sha256 must be a lowercase "
                f"SHA-256 digest, got {self.artifact_sha256!r}"
            )
        if not self.metric.strip():
            raise EventConditioningHazardInvalid(
                "event-conditioning hazard requires a non-empty metric"
            )
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise EventConditioningHazardInvalid(
                f"event-conditioning hazard value must be numeric, got {self.value!r}"
            )


class ObservedLossDataUnavailable(RuntimeError):
    """Raised when no licensed observed-loss dataset is available for a study.

    The harness treats this as a hard stop, never a cue to substitute synthetic
    or unlicensed data.
    """


@dataclass(frozen=True)
class SampleUnit:
    """One unit of analysis in a Gate-1 study.

    Attributes:
        unit_id: Stable identifier, unique within the sample.
        observed_loss: Ground-truth realised loss (absolute, study currency).
            This is the target; predictors never receive it.
        observation_date: When the loss was realised (the event outcome date).
        features_as_of: Information cutoff of this unit's **pre-event** predictor
            inputs. Must be on or before the study's pre-registered information
            cutoff — the harness enforces this to prevent lookahead. A
            preregistered retrospective event hazard must NOT be encoded here
            (it is not pre-event information); it belongs in
            ``event_conditioning_hazard``.
        features: Opaque **pre-event** predictor inputs, interpreted by the
            model/baseline adapters (e.g. ``{"asset": {...}}``). The harness does
            not read into this map.
        event_conditioning_hazard: Optional preregistered observed-event hazard
            evidence, admitted by the harness only when the frozen study
            registers a hazard source and event window covering it.
    """

    unit_id: str
    observed_loss: float
    observation_date: date
    features_as_of: date
    features: dict[str, Any] = field(default_factory=dict)
    event_conditioning_hazard: EventConditioningHazard | None = None

    def __post_init__(self) -> None:
        if self.observed_loss < 0.0:
            raise ValueError(
                f"observed_loss for {self.unit_id!r} must be >= 0, "
                f"got {self.observed_loss!r}"
            )
        if (
            self.event_conditioning_hazard is not None
            and self.event_conditioning_hazard.observed_at
            != self.observation_date
        ):
            raise EventConditioningHazardInvalid(
                f"unit {self.unit_id!r} declares event-conditioning hazard observed "
                f"on {self.event_conditioning_hazard.observed_at.isoformat()} but its "
                f"observation_date is {self.observation_date.isoformat()}; the "
                "observed hazard and the realised loss must belong to the same event"
            )


@runtime_checkable
class ObservedLossProvider(Protocol):
    """Loads the observed-loss sample for a study.

    Real implementations must (a) hold a commercial-use licence for the dataset
    and return ``True`` from :meth:`is_licensed_for_commercial_use`, (b) return
    sample units whose ``features_as_of`` respects the study cutoff, and
    (c) declare ``is_synthetic = False`` to assert real-data provenance.

    ``is_synthetic`` is a required part of the contract: the harness stamps it
    onto the report (``ComparisonReport.dataset_is_synthetic``) and the
    validation gate refuses to validate a synthetic dataset. It is read
    fail-closed via ``getattr(provider, "is_synthetic", True)``, so a provider
    that omits it is treated as synthetic and can never validate — a real
    integration MUST set it to ``False``.
    """

    # Provenance flag: real licensed providers set this False; fixtures set True.
    is_synthetic: bool

    @property
    def name(self) -> str:
        """Human-readable dataset/provider name for the report."""

    def is_licensed_for_commercial_use(self) -> bool:
        """Whether a commercial-use licence is on file (criterion 1.3)."""

    def load(self, pre_registration: Any) -> list[SampleUnit]:
        """Return the study sample, or raise :class:`ObservedLossDataUnavailable`."""


class UnlicensedObservedLossProvider:
    """Default, fail-closed provider. Never returns data.

    Present so the harness has a safe default and so the "no licensed data yet"
    path is exercised by tests. Swap for a licensed provider to run a real study.
    """

    # A real licensed provider must set is_synthetic = False; the harness reads
    # this to stamp the report's provenance (default: synthetic / fail-closed).
    is_synthetic = True

    @property
    def name(self) -> str:
        return "unlicensed-placeholder"

    def is_licensed_for_commercial_use(self) -> bool:
        return False

    def load(self, pre_registration: Any) -> list[SampleUnit]:  # noqa: ARG002
        raise ObservedLossDataUnavailable(
            "No licensed observed-loss dataset is configured. Gate-1 criterion "
            "1.3 requires a commercial-use licence on file before any study may "
            "run. Supply a licensed ObservedLossProvider; the harness will not "
            "fall back to synthetic data."
        )

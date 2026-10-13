"""Machine-readable pre-registration and the freeze guard (criterion 1.2).

The human narrative lives in ``docs/business/gate1_pre_registration_TEMPLATE.md``.
This module is the machine-checkable companion: the key study parameters
(cutoff, named baseline, metric, success rule) transcribed into a JSON file that
the harness reads. The harness refuses to run unless the pre-registration is
``frozen`` — parameters chosen after seeing results void the gate.
"""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, Literal

from app.validation.gate1.observed_loss import RETROSPECTIVE_EVENT_CONDITIONING

HazardType = Literal["heat", "flood"]


class PreRegistrationNotFrozen(RuntimeError):
    """Raised when a study is run against an unfrozen pre-registration."""


class EventConditioningRegistrationInvalid(ValueError):
    """Raised when a preregistered event-conditioning contract is malformed."""


@dataclass(frozen=True)
class EventConditioningRegistration:
    """The preregistration's authority to admit post-cutoff observed hazard evidence.

    P1-07: the pre-event information cutoff is absolute for *pre-event*
    information, but a retrospective event reconstruction legitimately observes
    the event it is reconstructing. That exception is admissible only when the
    study declared, **before** any outcome was opened, exactly which artifact may
    supply post-cutoff hazard intensity, for which event window, and that the
    source was selected without looking at outcomes.

    Every field here is part of the frozen scientific payload, so a study cannot
    widen the exception after the fact: changing the source, the artifact hash,
    the window or the selection-blindness flag invalidates the freeze.

    Attributes:
        role: Must be ``retrospective_event_conditioning``; the one admissible role.
        source_id: Identifier of the registered hazard product.
        artifact_sha256: SHA-256 of the frozen hazard artifact.
        event_window_start: First date of the registered event window (inclusive).
        event_window_end: Last date of the registered event window (inclusive).
        selected_before_outcome_access: Whether hazard source selection happened
            before any outcome was read. Selection blindness, not the download
            date, is what makes the observation admissible.
    """

    role: str
    source_id: str
    artifact_sha256: str
    event_window_start: date
    event_window_end: date
    selected_before_outcome_access: bool

    def __post_init__(self) -> None:
        if self.role != RETROSPECTIVE_EVENT_CONDITIONING:
            raise EventConditioningRegistrationInvalid(
                f"event-conditioning role {self.role!r} is not preregistered; the "
                f"only admissible role is {RETROSPECTIVE_EVENT_CONDITIONING!r}"
            )
        if not self.source_id.strip():
            raise EventConditioningRegistrationInvalid(
                "event-conditioning registration requires a non-empty source_id"
            )
        if not _SHA256_RE.match(self.artifact_sha256):
            raise EventConditioningRegistrationInvalid(
                "event-conditioning artifact_sha256 must be a lowercase SHA-256 "
                f"digest, got {self.artifact_sha256!r}"
            )
        if self.event_window_start > self.event_window_end:
            raise EventConditioningRegistrationInvalid(
                "event window start must not be after its end"
            )
        if self.selected_before_outcome_access is not True:
            raise EventConditioningRegistrationInvalid(
                "event conditioning requires selected_before_outcome_access=True; a "
                "hazard source chosen after reading outcomes is outcome-informed and "
                "cannot be admitted as event conditioning"
            )

    def admits(self, *, source_id: str, artifact_sha256: str, observed_at: date) -> str | None:
        """Return why this registration refuses an observation, or ``None`` if it admits it."""
        if self.source_id != source_id:
            return (
                f"hazard source {source_id!r} is not the preregistered source "
                f"{self.source_id!r}"
            )
        if self.artifact_sha256 != artifact_sha256:
            return (
                f"hazard artifact {artifact_sha256!r} does not match the frozen "
                f"artifact {self.artifact_sha256!r}"
            )
        if not (self.event_window_start <= observed_at <= self.event_window_end):
            return (
                f"observed hazard dated {observed_at.isoformat()} falls outside the "
                f"registered event window "
                f"{self.event_window_start.isoformat()}..{self.event_window_end.isoformat()}"
            )
        return None


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{7,64}$")

#: P1-06: the result-independent Harvey decisions the freeze must bind. Each is a
#: scientific choice made once, before any outcome is read; leaving any of them
#: unbound would let the study be re-specified after seeing results.
HARVEY_REQUIRED_STUDY_DECISIONS: tuple[str, ...] = (
    "study_id",
    "baseline_calibration_window",
    "evaluation_geography",
    "calibration_geography",
    "excluded_events",
    "excluded_occupancy_types",
    "outcome_access_protocol",
    "sample_split",
    "sample_size_and_cluster_thresholds",
    "hazard_coverage_threshold",
    "bootstrap_repetitions",
    "bootstrap_seed",
    "data_use_manifest_sha256",
    "source_data_sha256",
    "query_fingerprint",
    "calculation_code_commit",
    "reviewer",
)


@dataclass(frozen=True)
class SuccessRule:
    """Pre-stated rule deciding whether the model beats the baseline.

    Types:
        relative_improvement: model metric <= baseline metric * (1 - min_fraction).
            ``min_fraction`` in [0, 1]; e.g. 0.15 means "reduce error >= 15%".
        absolute_threshold: model metric <= max_value.
    """

    type: Literal["relative_improvement", "absolute_threshold"]
    min_fraction: float | None = None
    max_value: float | None = None

    def __post_init__(self) -> None:
        if self.type == "relative_improvement":
            if self.min_fraction is None or not (0.0 <= self.min_fraction <= 1.0):
                raise ValueError("relative_improvement requires min_fraction in [0, 1]")
        elif self.type == "absolute_threshold":
            if self.max_value is None or self.max_value < 0.0:
                raise ValueError("absolute_threshold requires max_value >= 0")
        else:
            raise ValueError(
                f"unknown success_rule type {self.type!r}; expected "
                "'relative_improvement' or 'absolute_threshold'"
            )

    def describe(self) -> str:
        if self.type == "relative_improvement":
            pct = round((self.min_fraction or 0.0) * 100, 3)
            return f"model error <= baseline error reduced by >= {pct}%"
        return f"model error <= {self.max_value}"


@dataclass(frozen=True)
class PreRegistration:
    """Frozen study parameters. Sections 1-8 of the human template, machine form."""

    study_title: str
    hazard_type: HazardType
    information_cutoff: date
    observed_loss_dataset: str
    baseline_name: str
    baseline_params: dict[str, Any]
    primary_metric: str
    success_rule: SuccessRule
    frozen: bool
    estimand_id: str | None = None
    freeze_timestamp: str | None = None
    freeze_commit: str | None = None
    preregistration_sha256: str | None = None
    #: P1-07: authority to admit preregistered observed-event hazard evidence.
    event_conditioning: EventConditioningRegistration | None = None
    #: P1-06: the remaining result-independent study decisions (study id,
    #: geography, split, exclusions, gate thresholds, provenance digests). Held
    #: as a mapping and bound by the freeze digest so none of it can change after
    #: results exist.
    study_decisions: dict[str, Any] = field(default_factory=dict)

    def scientific_payload(self) -> dict[str, Any]:
        """Return only the result-independent decisions covered by the freeze."""
        payload = self.summary()
        for key in (
            "frozen",
            "freeze_timestamp",
            "freeze_commit",
            "preregistration_sha256",
        ):
            payload.pop(key, None)
        return payload

    def scientific_payload_sha256(self) -> str:
        encoded = json.dumps(
            self.scientific_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def require_frozen(self) -> None:
        """Raise unless the pre-registration is frozen with a timestamp + commit."""
        if not self.frozen:
            raise PreRegistrationNotFrozen(
                f"Pre-registration {self.study_title!r} is not frozen. Freeze the "
                "sampling frame, baseline, metric, cutoff and success rule "
                "(criterion 1.2) before computing any result."
            )
        if (
            not self.freeze_timestamp
            or not self.freeze_commit
            or not self.preregistration_sha256
        ):
            raise PreRegistrationNotFrozen(
                f"Pre-registration {self.study_title!r} is marked frozen but is "
                "missing freeze_timestamp, freeze_commit or preregistration_sha256; the freeze is not "
                "auditable."
            )
        if not _GIT_OBJECT_RE.fullmatch(self.freeze_commit.lower()):
            raise PreRegistrationNotFrozen("freeze_commit is not a Git object id")
        if not _SHA256_RE.fullmatch(self.preregistration_sha256.lower()):
            raise PreRegistrationNotFrozen(
                "preregistration_sha256 is not a SHA-256 digest"
            )
        if self.preregistration_sha256.lower() != self.scientific_payload_sha256():
            raise PreRegistrationNotFrozen(
                "pre-registration scientific payload has changed since it was frozen"
            )
        if "harvey" in self.study_title.casefold() and self.estimand_id != (
            "nfip_claim_conditional_building_payment_v1"
        ):
            raise PreRegistrationNotFrozen(
                "Harvey pre-registration is not bound to the approved claim-conditional estimand"
            )
        if "harvey" in self.study_title.casefold():
            # P1-06: a Harvey freeze that omits any of these leaves a scientific
            # decision mutable after the fact. Refuse rather than run.
            missing = sorted(
                key
                for key in HARVEY_REQUIRED_STUDY_DECISIONS
                if self.study_decisions.get(key) is None
            )
            if missing:
                raise PreRegistrationNotFrozen(
                    "Harvey pre-registration is missing frozen study decisions: "
                    + ", ".join(missing)
                )
            if self.event_conditioning is None:
                raise PreRegistrationNotFrozen(
                    "Harvey pre-registration registers no event-conditioning hazard "
                    "contract; a retrospective reconstruction must name the hazard "
                    "source, artifact hash, event window and outcome-blind selection"
                )

    def summary(self) -> dict[str, Any]:
        return {
            "study_title": self.study_title,
            "estimand_id": self.estimand_id,
            "hazard_type": self.hazard_type,
            "information_cutoff": self.information_cutoff.isoformat(),
            "observed_loss_dataset": self.observed_loss_dataset,
            "baseline_name": self.baseline_name,
            "baseline_params": self.baseline_params,
            "primary_metric": self.primary_metric,
            "success_rule": {
                "type": self.success_rule.type,
                "min_fraction": self.success_rule.min_fraction,
                "max_value": self.success_rule.max_value,
            },
            "event_conditioning": (
                {
                    "role": self.event_conditioning.role,
                    "source_id": self.event_conditioning.source_id,
                    "artifact_sha256": self.event_conditioning.artifact_sha256,
                    "event_window_start": (
                        self.event_conditioning.event_window_start.isoformat()
                    ),
                    "event_window_end": self.event_conditioning.event_window_end.isoformat(),
                    "selected_before_outcome_access": (
                        self.event_conditioning.selected_before_outcome_access
                    ),
                }
                if self.event_conditioning is not None
                else None
            ),
            "study_decisions": self.study_decisions,
            "frozen": self.frozen,
            "freeze_timestamp": self.freeze_timestamp,
            "freeze_commit": self.freeze_commit,
            "preregistration_sha256": self.preregistration_sha256,
        }


def pre_registration_from_dict(raw: dict[str, Any]) -> PreRegistration:
    """Build a :class:`PreRegistration` from a parsed JSON mapping."""
    try:
        rule_raw = dict(raw["success_rule"])
        rule = SuccessRule(
            type=rule_raw["type"],
            min_fraction=rule_raw.get("min_fraction"),
            max_value=rule_raw.get("max_value"),
        )
        return PreRegistration(
            study_title=str(raw["study_title"]),
            hazard_type=raw["hazard_type"],
            information_cutoff=date.fromisoformat(str(raw["information_cutoff"])),
            observed_loss_dataset=str(raw["observed_loss_dataset"]),
            baseline_name=str(raw["baseline_name"]),
            baseline_params=dict(raw.get("baseline_params", {})),
            primary_metric=str(raw["primary_metric"]),
            success_rule=rule,
            frozen=bool(raw.get("frozen", False)),
            estimand_id=(
                str(raw["estimand_id"]) if raw.get("estimand_id") is not None else None
            ),
            freeze_timestamp=(
                str(raw["freeze_timestamp"])
                if raw.get("freeze_timestamp") is not None
                else None
            ),
            freeze_commit=(
                str(raw["freeze_commit"])
                if raw.get("freeze_commit") is not None
                else None
            ),
            preregistration_sha256=(
                str(raw["preregistration_sha256"])
                if raw.get("preregistration_sha256") is not None
                else None
            ),
            event_conditioning=_event_conditioning_from_dict(
                raw.get("event_conditioning")
            ),
            study_decisions=dict(raw.get("study_decisions", {})),
        )
    except KeyError as exc:
        raise ValueError(f"pre-registration is missing required key: {exc}") from exc


def _event_conditioning_from_dict(
    raw: Any,
) -> EventConditioningRegistration | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("event_conditioning must be an object when present")
    try:
        return EventConditioningRegistration(
            role=str(raw["role"]),
            source_id=str(raw["source_id"]),
            artifact_sha256=str(raw["artifact_sha256"]),
            event_window_start=date.fromisoformat(str(raw["event_window_start"])),
            event_window_end=date.fromisoformat(str(raw["event_window_end"])),
            selected_before_outcome_access=bool(raw["selected_before_outcome_access"]),
        )
    except KeyError as exc:
        raise ValueError(f"event_conditioning is missing required key: {exc}") from exc


def load_pre_registration(path: str | Path) -> PreRegistration:
    """Load and parse a JSON pre-registration file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("pre-registration JSON must be an object")
    return pre_registration_from_dict(data)


def freeze_pre_registration(
    preregistration: PreRegistration, *, timestamp: str, commit: str
) -> PreRegistration:
    """Seal a draft while preserving a digest of its scientific decisions."""
    if preregistration.frozen:
        raise ValueError("pre-registration is already frozen")
    missing_baseline = [
        key for key, value in preregistration.baseline_params.items() if value is None
    ]
    if missing_baseline:
        raise ValueError(
            "baseline parameters must be fixed before freezing; missing: "
            + ", ".join(sorted(missing_baseline))
        )
    digest = preregistration.scientific_payload_sha256()
    frozen = replace(
        preregistration,
        frozen=True,
        freeze_timestamp=timestamp,
        freeze_commit=commit,
        preregistration_sha256=digest,
    )
    frozen.require_frozen()
    return frozen


def verify_git_freeze(path: str | Path, *, repository: str | Path = ".") -> None:
    """Prove that the frozen scientific payload existed at ``freeze_commit``.

    Freeze metadata is deliberately excluded from the digest, avoiding an
    impossible self-reference where a file must contain the hash of its own
    commit. The referenced commit must contain the same path and payload.
    """
    repo = Path(repository).resolve()
    current_path = Path(path).resolve()
    try:
        relative = current_path.relative_to(repo).as_posix()
    except ValueError as exc:
        raise PreRegistrationNotFrozen(
            "pre-registration is outside repository"
        ) from exc
    prereg = load_pre_registration(current_path)
    prereg.require_frozen()
    assert prereg.freeze_commit is not None
    try:
        committed = subprocess.run(
            ["git", "show", f"{prereg.freeze_commit}:{relative}"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise PreRegistrationNotFrozen(
            f"freeze_commit does not contain {relative!r}"
        ) from exc
    committed_prereg = pre_registration_from_dict(json.loads(committed))
    if committed_prereg.scientific_payload_sha256() != prereg.preregistration_sha256:
        raise PreRegistrationNotFrozen(
            "freeze_commit contains a different scientific payload"
        )

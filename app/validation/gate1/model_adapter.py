"""Adapter from a :class:`SampleUnit` to the production expected-loss model.

Maps a unit's opaque ``features`` into the model's typed inputs and returns the
predicted absolute loss (``eal_absolute``). Cutoff is enforced at the model
boundary via :meth:`HazardScenarioIntensities.assert_no_lookahead`, so a unit
whose hazard inputs look ahead of the study cutoff raises instead of leaking.

Each prediction runs against an *isolated* audit trail so the harness never
pollutes the global production trail.

Expected feature schema per unit::

    {
      "asset":   {"asset_id", "asset_value", "building_type", "use_class",
                  "fragility_factor"?, "adaptation_capacity_factor"?,
                  "insurance_coverage"?},
      "hazards": {"current": {<hazard>: intensity in [0,1], ...},
                  "data_versions"? : {...}}
    }
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.loss.expected_loss import (
    EXPECTED_LOSS_METHODOLOGY_V0_4,
    ExpectedLossAssetInput,
    HazardScenarioIntensities,
    compute_expected_loss,
)
from app.loss.depth_damage_curves import DepthDamageCatalogue
from app.services.audit_trail import AppendOnlyAuditTrail
from app.validation.gate1.observed_loss import SampleUnit
from app.validation.gate1.pre_registration import HazardType

# Canonical hazard id used by the loss curves for each pre-registered hazard
# type. A single-hazard Gate-1 study is scored on exactly this hazard.
_HAZARD_TYPE_TO_ID: dict[HazardType, str] = {
    "heat": "extreme_heat",
    "flood": "flood",
}


class ExpectedLossModelAdapter:
    """Wraps :func:`compute_expected_loss` as a Gate-1 predictor.

    Args:
        information_cutoff: Study cutoff; each unit's hazard ``as_of`` (its
            ``features_as_of``) is checked against this to bar lookahead.
        valuation_date: Valuation date passed to the model. Defaults to the
            information cutoff.
        name: Reported model name; defaults to the model's methodology version.
        hazard_type: The pre-registered study hazard (``"heat"`` or
            ``"flood"``). When set, each unit must carry exactly this hazard in
            ``features.hazards.current``; off-study hazards are rejected so a
            single-hazard validation cannot be inflated by, or run on, another
            hazard's loss. Pass ``pre_registration.hazard_type``.
    """

    def __init__(
        self,
        *,
        information_cutoff: date,
        valuation_date: date | None = None,
        name: str | None = None,
        hazard_type: HazardType | None = None,
        depth_catalogue: DepthDamageCatalogue | None = None,
    ) -> None:
        if depth_catalogue is not None and hazard_type != "flood":
            raise ValueError(
                "depth_catalogue is only valid for a flood study "
                "(hazard_type='flood'); the JRC depth-damage path prices flood "
                "only and must not be applied to another hazard's depth."
            )
        self._cutoff = information_cutoff
        self._valuation_date = valuation_date or information_cutoff
        self._depth_catalogue = depth_catalogue
        if name is not None:
            self._name = name
        elif depth_catalogue is not None:
            # Bind the curve artefact identity into the model name so it flows
            # into the report's config_hash — an attestation issued for one set
            # of curves cannot validate results computed with another.
            self._name = (
                "expected-loss-v0.4-depth"
                f"[{depth_catalogue.catalogue_id}-v{depth_catalogue.version}]"
            )
        else:
            self._name = "expected-loss-model"
        self._hazard_id = (
            _HAZARD_TYPE_TO_ID[hazard_type] if hazard_type is not None else None
        )

    @property
    def name(self) -> str:
        return self._name

    def predict(self, unit: SampleUnit) -> float:
        """Return predicted absolute loss for one unit (no lookahead)."""
        if unit.features_as_of > self._cutoff:
            raise ValueError(
                f"unit {unit.unit_id!r} features_as_of={unit.features_as_of} "
                f"looks ahead of information_cutoff={self._cutoff}"
            )

        asset_raw: dict[str, Any] = dict(unit.features.get("asset", {}))
        hazards_raw: dict[str, Any] = dict(unit.features.get("hazards", {}))
        if "current" not in hazards_raw:
            raise ValueError(
                f"unit {unit.unit_id!r} is missing features.hazards.current"
            )

        current = dict(hazards_raw["current"])
        if self._hazard_id is not None:
            present = {str(h).strip().lower() for h in current}
            off_study = sorted(present - {self._hazard_id})
            if off_study:
                raise ValueError(
                    f"unit {unit.unit_id!r} carries off-study hazard(s) "
                    f"{off_study} for a {self._hazard_id!r} study; a "
                    "pre-registered single-hazard study must contain only its "
                    "registered hazard, or its result would mix hazards."
                )
            if self._hazard_id not in present:
                raise ValueError(
                    f"unit {unit.unit_id!r} is missing the registered study "
                    f"hazard {self._hazard_id!r} in features.hazards.current."
                )

        asset = ExpectedLossAssetInput(**asset_raw)
        hazards = HazardScenarioIntensities(
            current=current,
            data_versions=dict(hazards_raw.get("data_versions", {})),
            as_of=unit.features_as_of,
        )
        # Belt-and-braces: the model also rejects lookahead itself.
        hazards.assert_no_lookahead(self._cutoff)

        # Isolated trail so validation runs never touch the global audit chain.
        trail = AppendOnlyAuditTrail()
        if self._depth_catalogue is not None:
            # Validate the calibrated depth path (expected-loss-v0.4): each unit
            # must carry per-hazard inundation depths for its registered hazard.
            depths_raw = unit.features.get("depths")
            if not depths_raw:
                raise ValueError(
                    f"unit {unit.unit_id!r} is missing features.depths, required "
                    "for a depth-damage (v0.4) validation study"
                )
            depths = {str(k): float(v) for k, v in dict(depths_raw).items()}
            if self._hazard_id is not None and self._hazard_id not in depths:
                # Without the registered hazard's depth, v0.4 would silently fall
                # back to the v0.3 intensity curve for it while the report still
                # names the v0.4-depth model — a different model than claimed.
                raise ValueError(
                    f"unit {unit.unit_id!r} features.depths is missing the "
                    f"registered study hazard {self._hazard_id!r}; a v0.4 depth "
                    "study must supply the depth it prices"
                )
            result = compute_expected_loss(
                asset=asset,
                hazards=hazards,
                valuation_date=self._valuation_date,
                trail=trail,
                methodology_version=EXPECTED_LOSS_METHODOLOGY_V0_4,
                depths=depths,
                depth_catalogue=self._depth_catalogue,
            )
        else:
            result = compute_expected_loss(
                asset=asset,
                hazards=hazards,
                valuation_date=self._valuation_date,
                trail=trail,
            )
        return float(result.eal_absolute)

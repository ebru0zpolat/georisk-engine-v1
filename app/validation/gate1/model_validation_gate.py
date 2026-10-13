"""The ``model_validated_for_use_case`` readiness gate (GEO-105), tiered.

``run_comparison`` answers one question — *did the model beat the pre-registered
naive baseline on licensed data?* — stamped on a :class:`ComparisonReport` as
``passed``. That is necessary but not sufficient for the production readiness
state ``model_validated_for_use_case``: a green comparison still needs an
attestation bound to the exact study, on a **non-synthetic** dataset.

**Tiers.** External independent review is not available to a pre-funding MVP, so
validation is tiered rather than all-or-nothing:

- ``self_attested`` — the study author/team signs off (same org). The MVP
  minimum: honest, auditable, and achievable without outside parties.
- ``independent`` — an external reviewer from a different org signs off. The
  higher-assurance tier, unlocked later.

``evaluate_model_validation`` returns the **tier achieved** plus a ``validated``
boolean = "meets at least ``minimum_tier``". The default minimum is
``self_attested`` (MVP). Nothing is overstated: the verdict always names the
tier, so "validated (self-attested)" never reads as independent assurance.

Fail-closed regardless of tier: no reviewer, a rejected/ mismatched attestation,
a synthetic dataset, or a failed comparison all yield ``validated=False`` with
the reason named. A signature can never rescue a synthetic dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from app.validation.gate1.report import ComparisonReport

# The org that authors the model; a reviewer from it yields the self_attested tier.
DEFAULT_MODEL_AUTHORS_ORG = "georisk-engine"

# Datasets that can never support a validation verdict (fixtures / placeholders).
SYNTHETIC_DATASET_NAMES: frozenset[str] = frozenset(
    {"unlicensed-placeholder", "synthetic-mechanics-fixture"}
)


class ValidationTier(str, Enum):
    """Assurance tiers for model validation, lowest to highest."""

    SELF_ATTESTED = "self_attested"
    INDEPENDENT = "independent"


_TIER_ORDER: dict[ValidationTier, int] = {
    ValidationTier.SELF_ATTESTED: 1,
    ValidationTier.INDEPENDENT: 2,
}


@dataclass(frozen=True)
class ReviewerAttestation:
    """A reviewer's sign-off, bound to one study's config hash.

    ``reviewer_org`` decides the tier: equal to the model authors' org →
    ``self_attested``; a different org → ``independent``.
    """

    reviewer_id: str
    reviewer_org: str
    attested_config_hash: str
    decision: Literal["approve", "reject"]
    signed_at: str  # ISO-8601
    statement: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer_id": self.reviewer_id,
            "reviewer_org": self.reviewer_org,
            "attested_config_hash": self.attested_config_hash,
            "decision": self.decision,
            "signed_at": self.signed_at,
            "statement": self.statement,
        }


@dataclass(frozen=True)
class ModelValidationVerdict:
    """Fail-closed, tiered verdict for ``model_validated_for_use_case``."""

    validated: bool
    tier: str | None  # achieved tier ("self_attested"/"independent"), or None
    minimum_tier: str
    use_case: str
    hazard_type: str
    model_name: str
    observed_loss_dataset: str
    report_config_hash: str
    reasons: list[str] = field(default_factory=list)
    reviewer_id: str | None = None
    evaluated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "validated": self.validated,
            "tier": self.tier,
            "minimum_tier": self.minimum_tier,
            "use_case": self.use_case,
            "hazard_type": self.hazard_type,
            "model_name": self.model_name,
            "observed_loss_dataset": self.observed_loss_dataset,
            "report_config_hash": self.report_config_hash,
            "reasons": list(self.reasons),
            "reviewer_id": self.reviewer_id,
            "evaluated_at": self.evaluated_at,
        }


def evaluate_model_validation(
    *,
    report: ComparisonReport,
    reviewer: ReviewerAttestation | None,
    minimum_tier: ValidationTier = ValidationTier.SELF_ATTESTED,
    model_authors_org: str = DEFAULT_MODEL_AUTHORS_ORG,
    synthetic_dataset_names: frozenset[str] = SYNTHETIC_DATASET_NAMES,
    evaluated_at: str | None = None,
) -> ModelValidationVerdict:
    """Decide ``model_validated_for_use_case`` from a report + reviewer sign-off.

    ``validated`` is ``True`` only when the comparison passed, the dataset is not
    synthetic, a valid attestation (approve + matching config hash) exists, and
    its tier meets ``minimum_tier`` (default ``self_attested`` — the MVP bar).
    Any gap appends a reason and leaves ``validated=False``.
    """
    reasons: list[str] = []

    if not report.passed:
        reasons.append(
            f"comparison did not pass the frozen success rule ({report.success_rule})"
        )

    dataset = report.observed_loss_dataset
    # Authoritative, provenance-driven check: the report must affirmatively carry
    # real-data provenance (the harness sets this from the provider). Absence of
    # a name from the denylist is NOT evidence of real data.
    if report.dataset_is_synthetic:
        reasons.append(
            "observed-loss dataset provenance is not affirmatively real "
            "(report.dataset_is_synthetic); a verdict requires a provider that "
            "asserts a licensed real dataset (is_synthetic=False)"
        )
    # Belt-and-braces denylist for known fixture/placeholder names.
    if dataset in synthetic_dataset_names:
        reasons.append(
            f"observed-loss dataset {dataset!r} is a synthetic/placeholder "
            "dataset and can never support a validation verdict"
        )

    achieved_tier: ValidationTier | None = None
    if reviewer is None:
        reasons.append(
            "no reviewer attestation on file (a self-attestation is the MVP minimum)"
        )
    else:
        attestation_ok = True
        if not reviewer.reviewer_org.strip():
            reasons.append(
                "reviewer attestation has an empty reviewer_org; an org is "
                "required to establish the tier (and independence)"
            )
            attestation_ok = False
        if reviewer.decision != "approve":
            reasons.append(f"reviewer decision is {reviewer.decision!r}, not 'approve'")
            attestation_ok = False
        if reviewer.attested_config_hash != report.config_hash:
            reasons.append(
                "reviewer attestation binds to config_hash "
                f"{reviewer.attested_config_hash[:16]}…, not this study's "
                f"{report.config_hash[:16]}…"
            )
            attestation_ok = False
        if attestation_ok:
            independent = (
                reviewer.reviewer_org.strip().lower()
                != model_authors_org.strip().lower()
            )
            achieved_tier = (
                ValidationTier.INDEPENDENT if independent else ValidationTier.SELF_ATTESTED
            )
            if _TIER_ORDER[achieved_tier] < _TIER_ORDER[minimum_tier]:
                reasons.append(
                    f"attestation tier {achieved_tier.value!r} is below the "
                    f"required minimum {minimum_tier.value!r} (needs an "
                    "independent reviewer from a different org)"
                )

    prereg = report.pre_registration or {}
    return ModelValidationVerdict(
        validated=not reasons,
        tier=achieved_tier.value if achieved_tier else None,
        minimum_tier=minimum_tier.value,
        use_case=str(prereg.get("study_title", report.study_title)),
        hazard_type=str(prereg.get("hazard_type", "")),
        model_name=report.model_name,
        observed_loss_dataset=dataset,
        report_config_hash=report.config_hash,
        reasons=reasons,
        reviewer_id=reviewer.reviewer_id if reviewer else None,
        evaluated_at=evaluated_at,
    )


__all__ = [
    "DEFAULT_MODEL_AUTHORS_ORG",
    "SYNTHETIC_DATASET_NAMES",
    "ModelValidationVerdict",
    "ReviewerAttestation",
    "ValidationTier",
    "evaluate_model_validation",
]

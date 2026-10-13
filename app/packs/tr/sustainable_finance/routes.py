"""Regulatory routes, pack lifecycle states and engagement roles (spec §3, §4, §12)."""

from __future__ import annotations

from enum import Enum


class RegulatoryRoute(str, Enum):
    """Exactly one primary route must be selected per engagement (spec §4)."""

    use_of_proceeds = "use_of_proceeds"
    sustainability_linked = "sustainability_linked"


class PackStatus(str, Enum):
    """Pack lifecycle states (spec §12).

    GeoRisk may assign only the first three; later states require documentary evidence
    supplied by the responsible issuer or external-review provider. Recording an external
    document does NOT mean GeoRisk endorses its conclusion.
    """

    draft = "draft"
    technical_evidence_complete = "technical_evidence_complete"
    reviewer_ready = "reviewer_ready"
    issuer_approved = "issuer_approved"
    second_party_opinion_received = "second_party_opinion_received"
    verification_received = "verification_received"
    superseded = "superseded"


#: States GeoRisk itself is permitted to assign (spec §12).
GEORISK_ASSIGNABLE_STATES: frozenset[PackStatus] = frozenset(
    {
        PackStatus.draft,
        PackStatus.technical_evidence_complete,
        PackStatus.reviewer_ready,
    }
)


def is_georisk_assignable(state: PackStatus) -> bool:
    return state in GEORISK_ASSIGNABLE_STATES


class EligibilityStatus(str, Enum):
    """Permitted GeoRisk project-eligibility values (spec §6.2).

    ``project_eligible = true`` is NOT a permitted value — legal eligibility is never
    determined by GeoRisk.
    """

    technical_evidence_complete = "technical_evidence_complete"
    technical_evidence_incomplete = "technical_evidence_incomplete"
    outside_georisk_scope = "outside_georisk_scope"
    requires_issuer_determination = "requires_issuer_determination"
    requires_external_review = "requires_external_review"


class EngagementRole(str, Enum):
    """Parties in the responsibility map (spec §3.3)."""

    issuer = "issuer"
    capital_markets_legal_adviser = "capital_markets_legal_adviser"
    framework_adviser = "framework_adviser"
    georisk_engine = "georisk_engine"
    second_party_opinion_provider = "second_party_opinion_provider"
    verifier = "verifier"


class ExternalReviewType(str, Enum):
    """The only two guideline external-review service types (spec §D.9 / §E.9)."""

    second_party_opinion = "second_party_opinion"
    verification = "verification"


#: What GeoRisk may provide (spec §3.1) — descriptive, for the boundary export.
GEORISK_MAY_PROVIDE: tuple[str, ...] = (
    "versioned hazard, exposure and vulnerability evidence for active and validated modules",
    "scenario / time-horizon evidence when a real, licensed, versioned climate intensity map is available",
    "before/after physical-risk evidence for an adaptation project",
    "candidate qualitative or quantitative impact measures",
    "candidate KPI definitions and SPT design inputs",
    "data lineage, licences, retrieval dates, hashes and calculation records",
    "uncertainty, exclusions, assumptions and known limitations",
    "a structured evidence index for the issuer, adviser, second-party opinion provider and verifier",
    "draft disclosure fields for issuer review",
)

#: What GeoRisk must NOT provide under the current product contract (spec §3.2).
GEORISK_MUST_NOT_PROVIDE: tuple[str, ...] = (
    "a legal conclusion that an instrument or project is green, sustainable, social or sustainability-linked",
    "a CMB eligibility, approval or compliance certificate",
    "a second-party opinion under either guideline",
    "independent verification or assurance under the guidelines",
    "a credit rating, green rating, certification or investment recommendation",
    "an engineering certificate that an asset or adaptation measure meets a design standard",
    "an emissions, transition-plan or CBAM KPI unless a separate transition-risk capability is validated",
    "a social-impact determination without a separate social-impact methodology and evidence source",
    "a coupon-trigger recommendation based on synthetic, fallback, unvalidated or non-reproducible data",
    "a prediction of actual loss, downtime or credit loss from the current preliminary loss proxy",
)


def role_separation_ok(
    *,
    framework_adviser: str | None,
    second_party_opinion_provider: str | None,
    verifier: str | None,
) -> tuple[bool, list[str]]:
    """Check the independence rules (spec §3.3, §D.9, §E.9).

    - The framework-preparation adviser may not provide external review for that framework.
    - For the same framework, one provider may perform only one external-review type
      (an SPO provider must not also be the verifier).

    Returns ``(ok, violations)``. Unappointed roles (``None``) do not create violations.
    """
    violations: list[str] = []

    def _norm(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().casefold()
        return cleaned or None

    adviser = _norm(framework_adviser)
    spo = _norm(second_party_opinion_provider)
    ver = _norm(verifier)

    if adviser is not None and spo is not None and adviser == spo:
        violations.append(
            "framework adviser also named as second-party opinion provider for the same framework"
        )
    if adviser is not None and ver is not None and adviser == ver:
        violations.append("framework adviser also named as verifier for the same framework")
    if spo is not None and ver is not None and spo == ver:
        violations.append(
            "same provider named as both second-party opinion provider and verifier for the same framework"
        )
    return (not violations, violations)


__all__ = [
    "EligibilityStatus",
    "EngagementRole",
    "ExternalReviewType",
    "GEORISK_ASSIGNABLE_STATES",
    "GEORISK_MAY_PROVIDE",
    "GEORISK_MUST_NOT_PROVIDE",
    "PackStatus",
    "RegulatoryRoute",
    "is_georisk_assignable",
    "role_separation_ok",
]

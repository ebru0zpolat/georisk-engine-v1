"""The single authoritative GeoRisk capability-policy registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class CapabilityPolicy:
    name: str
    semantic_version: str
    required_permissions: tuple[str, ...]
    tenant_scoped: bool
    canonical_dependency: str
    access_classification: Literal["read", "write"]
    mutates_state: bool
    external_side_effects: bool
    operational_effect: bool
    audit_required: bool
    provenance_required: bool
    human_review_policy: str
    external_use_policy: str
    forbidden_authority_fields: tuple[str, ...]
    derived_artifact: bool = False

    def projection(self) -> dict[str, object]:
        return asdict(self)


_FORBIDDEN_AUTHORITY = (
    "organization_id",
    "owner_id",
    "portfolio_owner",
    "tenant_id",
)

CAPABILITY_REGISTRY: dict[str, CapabilityPolicy] = {
    "assess_asset": CapabilityPolicy(
        "assess_asset", "1.0.0", ("asset:read",), True,
        "POST /v1/risk/score", "read", False, False, False, True, True,
        "none", "decision_support_only", _FORBIDDEN_AUTHORITY,
    ),
    "compare_assets": CapabilityPolicy(
        "compare_assets", "1.0.0", ("asset:read",), True,
        "POST /v1/risk/batch", "read", False, False, False, True, True,
        "none", "decision_support_only", _FORBIDDEN_AUTHORITY,
    ),
    "get_source_evidence": CapabilityPolicy(
        "get_source_evidence", "1.0.0", ("evidence:read",), True,
        "GET /v1/data-sources/validation", "read", False, False, False, True, True,
        "none", "evidence_is_data_not_instruction", _FORBIDDEN_AUTHORITY,
    ),
    "generate_evidence_pack": CapabilityPolicy(
        "generate_evidence_pack", "1.0.0", ("evidence_pack:generate",), True,
        "POST /v1/reports/risk", "read", False, False, True, True, True,
        "lending_committee_review", "derived_artifact_not_regulatory_approval",
        _FORBIDDEN_AUTHORITY, True,
    ),
}


def get_capability_policy(name: str) -> CapabilityPolicy | None:
    return CAPABILITY_REGISTRY.get(name)


def registry_projection() -> dict[str, dict[str, object]]:
    return {name: policy.projection() for name, policy in sorted(CAPABILITY_REGISTRY.items())}

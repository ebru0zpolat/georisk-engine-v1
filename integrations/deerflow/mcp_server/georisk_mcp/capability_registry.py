"""Read-only adapter over the generated projection of the app registry.

Do not edit policy data here. Regenerate ``capability_registry.generated.json`` from
``app.capabilities.registry`` and verify equivalence in CI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class CapabilityPolicyView:
    name: str
    semantic_version: str
    required_permissions: frozenset[str]
    tenant_scoped: bool
    canonical_dependency: str
    access_classification: str
    mutates_state: bool
    external_side_effects: bool
    operational_effect: bool
    audit_required: bool
    provenance_required: bool
    human_review_policy: str
    external_use_policy: str
    forbidden_authority_fields: frozenset[str]
    derived_artifact: bool


def _load_projection() -> dict[str, CapabilityPolicyView]:
    path = files("georisk_mcp").joinpath("capability_registry.generated.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        name: CapabilityPolicyView(
            **{
                **policy,
                "required_permissions": frozenset(policy["required_permissions"]),
                "forbidden_authority_fields": frozenset(policy["forbidden_authority_fields"]),
            }
        )
        for name, policy in raw.items()
    }


CAPABILITY_REGISTRY = _load_projection()


def get_capability_policy(name: str) -> CapabilityPolicyView | None:
    return CAPABILITY_REGISTRY.get(name)

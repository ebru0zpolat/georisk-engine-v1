"""WP-A: Fail-closed deployment configuration contract (GEO-62).

Identifies required deployment settings without exposing their values.
Separates required / optional / disabled / present / verified states.
Rejects placeholder secrets and fails closed when a connector is
enabled but its required configuration is absent.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


_PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "changeme",
        "placeholder",
        "test",
        "example",
        "todo",
        "unknown",
        "",
    }
)


class ConfigState(StrEnum):
    """Lifecycle state of a single configuration entry."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    DISABLED = "disabled"
    PRESENT = "present"
    VERIFIED = "verified"


class ConnectorConfig(BaseModel, frozen=True):
    """One connector's configuration status.

    ``secret_value`` is never stored, serialised, logged or included
    in evidence.  Only the identifier (environment-variable name) is
    retained.
    """

    name: str
    enabled: bool
    required_env_vars: list[str] = Field(default_factory=list)
    optional_env_vars: list[str] = Field(default_factory=list)
    state: ConfigState = ConfigState.REQUIRED
    placeholder_rejected: bool = False
    missing_required: list[str] = Field(default_factory=list)
    present_required: list[str] = Field(default_factory=list)
    present_optional: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    @model_validator(mode="after")
    def _check_placeholder_and_absent(self) -> ConnectorConfig:
        """Detect placeholder values and missing required vars.

        This validator mutates computed fields only; it never reads
        or stores actual secret values.
        """
        if not self.enabled:
            return self

        missing: list[str] = []
        present_req: list[str] = []
        present_opt: list[str] = []
        placeholder = False

        for var in self.required_env_vars:
            raw = os.environ.get(var, "")
            stripped = raw.strip()
            if not stripped or stripped.lower() in _PLACEHOLDER_VALUES:
                missing.append(var)
                if stripped.lower() in _PLACEHOLDER_VALUES:
                    placeholder = True
            else:
                present_req.append(var)

        for var in self.optional_env_vars:
            raw = os.environ.get(var, "")
            stripped = raw.strip()
            if stripped and stripped.lower() not in _PLACEHOLDER_VALUES:
                present_opt.append(var)

        object.__setattr__(self, "missing_required", missing)
        object.__setattr__(self, "present_required", present_req)
        object.__setattr__(self, "present_optional", present_opt)
        object.__setattr__(self, "placeholder_rejected", placeholder)
        return self


class DeployConfiguration(BaseModel, frozen=True):
    """Top-level deployment configuration status.

    ``secrets`` is a flat list of environment-variable *names only*.
    Actual values are never stored, serialised or compared.
    """

    environment_name: str = "unknown"
    connectors: list[ConnectorConfig] = Field(default_factory=list)
    complete: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    @model_validator(mode="after")
    def _evaluate_completeness(self) -> DeployConfiguration:
        """Fail-closed: any missing required or placeholder rejects.

        An empty or absent connector list also fails closed — a deployment
        with no configured data sources cannot satisfy any operational gate.
        """
        reasons: list[str] = []
        all_secrets: list[str] = []

        if not self.connectors:
            reasons.append("No connectors configured")

        for conn in self.connectors:
            all_secrets.extend(conn.required_env_vars)
            if not conn.enabled:
                continue
            if conn.missing_required:
                reasons.append(
                    f"{conn.name}: missing required {conn.missing_required}"
                )
            if conn.placeholder_rejected:
                reasons.append(f"{conn.name}: placeholder secret rejected")

        object.__setattr__(self, "complete", len(reasons) == 0)
        object.__setattr__(self, "blocking_reasons", reasons)
        object.__setattr__(self, "secrets", all_secrets)
        return self


def evaluate_deploy_config(
    *,
    environment_name: str = "unknown",
    connectors: list[ConnectorConfig] | None = None,
) -> DeployConfiguration:
    """Evaluate deployment configuration without exposing values."""
    return DeployConfiguration(
        environment_name=environment_name,
        connectors=connectors or [],
    )

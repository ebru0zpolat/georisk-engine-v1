"""Trusted, complete circuit-breaker state evaluation."""

from enum import StrEnum

from app.automation.issues import IssueInventory, MARKER_RE, marker, trusted_issue

CIRCUIT_MARKER = marker("circuit-breaker", "global")
ACTIVATION_CONDITIONS = {
    "classification_or_evidence_schema_failure", "required_check_provenance_mismatch",
    "repeated_privileged_workflow_failure", "unintended_publication",
    "post_deployment_verification_failure", "suspected_credential_exposure",
    "security_policy_failure",
}


class CircuitState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


def circuit_state(
    inventory: IssueInventory | None, *, trusted_creators: set[str], trusted_label: str,
) -> CircuitState:
    if inventory is None or not inventory.complete:
        return CircuitState.UNKNOWN
    matches = [item for item in inventory.issues if CIRCUIT_MARKER in item.body]
    # Any ambiguous/untrusted circuit marker blocks, even though it cannot establish canonical state.
    if any(not trusted_issue(item, repository=inventory.repository, creators=trusted_creators, label=trusted_label) for item in matches):
        return CircuitState.UNKNOWN
    if len(matches) > 1:
        return CircuitState.UNKNOWN
    if not matches:
        return CircuitState.CLOSED
    return CircuitState.OPEN if matches[0].state == "open" else CircuitState.CLOSED


def has_marker_contamination(inventory: IssueInventory) -> bool:
    return any(MARKER_RE.search(item.body) for item in inventory.issues)

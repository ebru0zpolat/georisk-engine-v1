"""Records source for the data_source_operational gate.

The gate (``data_source_operational_gate``) decides operational status from four
controls; this module is where three of them come from as data:

- **licence** + **retention** records: declared in a config file (JSON). They
  are legal/operational facts, never inferred — a missing file means no records
  and the gate fails closed.
- **live-runtime evidence**: appended to a JSONL log when a real live connector
  fetch is captured (``capture_live_evidence`` — fingerprints the connector's
  live output). ``scripts/capture_live_evidence.py`` drives the real connectors
  and writes these.

``OperationalRecordsStore`` bundles the three and, given each source's delivery
mode (from ``data_source_validation.delivery_mode_for``), produces the per-source
operational verdicts via the gate. Nothing here fabricates a control: absent
records fail closed.

Populating records safely (roadmap P2, "as keys become available"):

- ``validate_operational_config`` cross-checks the licence/retention config
  against the known registry ids so a typo'd ``source_id`` fails **loud** rather
  than fabricating a permanent silent fail-closed (indistinguishable from "no
  licence").
- ``provisioning_status`` composes the gate verdict into a per-control checklist
  with the exact next action for each missing control — the operator's guide to
  flipping one credentialed source operational.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.core.data_source_operational_gate import (
    DataSourceOperationalVerdict,
    LicenceRecord,
    LiveRuntimeEvidence,
    RetentionPolicy,
    evaluate_data_source_operational,
    evaluate_sources_operational,
)

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = _ROOT / "config" / "data_source_operational.json"
DEFAULT_EVIDENCE_LOG = _ROOT / "data" / "operational" / "live_evidence.jsonl"

#: How a source in each delivery plane earns ``delivery_mode == "live"``. Used to
#: tell an operator exactly which credential is missing (never guessed).
CREDENTIAL_HINT: dict[str, str] = {
    "cds_zarr": "set ORAS5_ZARR_URL or COPERNICUS_CDS_API_KEY (CDSAPI_KEY)",
    "gee": "set GEE_PROJECT and GEE_ENABLED=true",
    "gee_audit": "set GEE_PROJECT (or AUDIT_USE_MOCK=true for non-live audit runs)",
    "stub": "roadmap-tier stub source — no live credential path exists yet",
}

#: Delivery planes whose wired connector genuinely fetches *that source's own*
#: dataset, so a fingerprinted payload is valid live evidence for it. The
#: ``capture_live_evidence`` script drives these. ``gee_audit`` is deliberately
#: excluded: those sources (Landsat thermal, S5P CO, VIIRS DNB monthly) are NOT
#: fetched by the production ``GeeConnector`` — routing them through it would
#: fingerprint the wrong dataset and fabricate provenance. They must be captured
#: via their dedicated audit pipeline, not this seam.
CAPTURABLE_PLANES: frozenset[str] = frozenset({"cds_zarr", "gee"})


def sample_sha256(payload: Any) -> str:
    """Deterministic SHA-256 fingerprint of a connector's live output."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_live_evidence(
    *,
    source_id: str,
    payload: Any,
    request_ref: str,
    delivery_mode: str,
    captured_at: date | None = None,
) -> LiveRuntimeEvidence:
    """Fingerprint a real live connector fetch into a ``LiveRuntimeEvidence``.

    Only a ``live`` delivery counts — recording evidence from a fallback/stub
    fetch would be a false operational signal, so it is refused.
    """
    if delivery_mode != "live":
        raise ValueError(
            f"refusing to record live evidence for delivery_mode={delivery_mode!r}; "
            "only a real live fetch is evidence"
        )
    return LiveRuntimeEvidence(
        source_id=source_id,
        captured_at=captured_at or date.today(),
        request_ref=request_ref,
        sample_sha256=sample_sha256(payload),
        delivery_mode="live",
    )


def append_evidence(evidence: LiveRuntimeEvidence, *, path: Path = DEFAULT_EVIDENCE_LOG) -> None:
    """Append one evidence record to the JSONL log (append-only history)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "source_id": evidence.source_id,
        "captured_at": evidence.captured_at.isoformat(),
        "request_ref": evidence.request_ref,
        "sample_sha256": evidence.sample_sha256,
        "delivery_mode": evidence.delivery_mode,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def load_evidence(path: Path = DEFAULT_EVIDENCE_LOG) -> dict[str, list[LiveRuntimeEvidence]]:
    """Load the evidence log grouped by source_id (empty when absent)."""
    out: dict[str, list[LiveRuntimeEvidence]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        ev = LiveRuntimeEvidence(
            source_id=str(row["source_id"]),
            captured_at=date.fromisoformat(str(row["captured_at"])),
            request_ref=str(row.get("request_ref", "")),
            sample_sha256=str(row.get("sample_sha256", "")),
            delivery_mode=str(row.get("delivery_mode", "")),
        )
        out.setdefault(ev.source_id, []).append(ev)
    return out


def load_licences_and_retentions(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> tuple[dict[str, LicenceRecord], dict[str, RetentionPolicy]]:
    """Load licence + retention records from config (empty when file absent)."""
    licences: dict[str, LicenceRecord] = {}
    retentions: dict[str, RetentionPolicy] = {}
    if not config_path.exists():
        return licences, retentions
    data = json.loads(config_path.read_text(encoding="utf-8"))
    for i, raw in enumerate(data.get("licences", [])):
        try:
            licences[str(raw["source_id"])] = LicenceRecord(
                source_id=str(raw["source_id"]),
                licence_id=str(raw["licence_id"]),
                licensor=str(raw["licensor"]),
                commercial_use=bool(raw["commercial_use"]),
                valid_from=date.fromisoformat(str(raw["valid_from"])),
                valid_until=(
                    date.fromisoformat(str(raw["valid_until"]))
                    if raw.get("valid_until")
                    else None
                ),
                document_ref=str(raw.get("document_ref", "")),
            )
        except (KeyError, ValueError) as exc:
            # Fail loud with the row index so a malformed licence is fixed, not
            # silently dropped into a fail-closed the operator can't diagnose.
            raise ValueError(f"licences[{i}] in {config_path.name} is malformed: {exc}") from exc
    for i, raw in enumerate(data.get("retentions", [])):
        try:
            retentions[str(raw["source_id"])] = RetentionPolicy(
                source_id=str(raw["source_id"]),
                retention_days=int(raw["retention_days"]),
                storage_location=str(raw["storage_location"]),
                policy_ref=str(raw.get("policy_ref", "")),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"retentions[{i}] in {config_path.name} is malformed: {exc}") from exc
    return licences, retentions


@dataclass(frozen=True)
class ConfigIssue:
    """One problem found while validating the licence/retention config."""

    section: str  # "licences" or "retentions"
    index: int
    source_id: str
    message: str

    def __str__(self) -> str:
        return f"{self.section}[{self.index}] ({self.source_id or '?'}): {self.message}"


def validate_operational_config(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    known_source_ids: set[str] | None = None,
) -> list[ConfigIssue]:
    """Return structured issues with the licence/retention config (empty = clean).

    Catches the mistakes that would otherwise become an undiagnosable silent
    fail-closed: an unknown/typo'd ``source_id``, a duplicate source in one
    section, an unparseable date, a non-commercial licence, a non-positive
    retention horizon. An absent file is valid (no records → fail-closed by
    design). Legal facts are never invented here — only checked for shape.
    """
    if not config_path.exists():
        return []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [ConfigIssue("file", 0, "", f"not valid JSON: {exc}")]

    issues: list[ConfigIssue] = []

    def _check_id(section: str, i: int, sid: str) -> None:
        if known_source_ids is not None and sid not in known_source_ids:
            issues.append(ConfigIssue(
                section, i, sid,
                "source_id is not in the data-source registry — it will never "
                "match a source and stays silently fail-closed",
            ))

    seen_lic: set[str] = set()
    for i, raw in enumerate(data.get("licences", [])):
        sid = str(raw.get("source_id", ""))
        if not sid:
            issues.append(ConfigIssue("licences", i, sid, "missing source_id"))
            continue
        _check_id("licences", i, sid)
        if sid in seen_lic:
            issues.append(ConfigIssue("licences", i, sid, "duplicate licence for this source_id"))
        seen_lic.add(sid)
        for key in ("licence_id", "licensor", "valid_from"):
            if not str(raw.get(key, "")).strip():
                issues.append(ConfigIssue("licences", i, sid, f"missing {key}"))
        if not isinstance(raw.get("commercial_use"), bool):
            issues.append(ConfigIssue("licences", i, sid, "commercial_use must be true/false"))
        elif raw.get("commercial_use") is False:
            issues.append(ConfigIssue("licences", i, sid, "commercial_use is false — gate will reject"))
        for key in ("valid_from", "valid_until"):
            val = raw.get(key)
            if val:
                try:
                    date.fromisoformat(str(val))
                except ValueError:
                    issues.append(ConfigIssue("licences", i, sid, f"{key} is not an ISO date"))

    seen_ret: set[str] = set()
    for i, raw in enumerate(data.get("retentions", [])):
        sid = str(raw.get("source_id", ""))
        if not sid:
            issues.append(ConfigIssue("retentions", i, sid, "missing source_id"))
            continue
        _check_id("retentions", i, sid)
        if sid in seen_ret:
            issues.append(ConfigIssue("retentions", i, sid, "duplicate retention for this source_id"))
        seen_ret.add(sid)
        try:
            if int(raw.get("retention_days", 0)) <= 0:
                issues.append(ConfigIssue("retentions", i, sid, "retention_days must be positive"))
        except (TypeError, ValueError):
            issues.append(ConfigIssue("retentions", i, sid, "retention_days must be an integer"))
        if not str(raw.get("storage_location", "")).strip():
            issues.append(ConfigIssue("retentions", i, sid, "missing storage_location"))

    return issues


@dataclass(frozen=True)
class ProvisioningControl:
    """One of the four controls, with its state and the next action if unmet."""

    name: str
    ok: bool
    next_action: str = ""


@dataclass(frozen=True)
class ProvisioningStatus:
    """A per-source checklist for flipping ``data_source_operational`` on."""

    source_id: str
    delivery_plane: str
    delivery_mode: str
    operational: bool
    controls: list[ProvisioningControl] = field(default_factory=list)

    @property
    def remaining(self) -> list[ProvisioningControl]:
        return [c for c in self.controls if not c.ok]


def _evidence_next_action(source_id: str, delivery_plane: str, live: bool) -> str:
    """Next action to obtain live evidence for a source (honest per plane)."""
    if delivery_plane not in CAPTURABLE_PLANES:
        # e.g. gee_audit: the production connector does not fetch this dataset, so
        # never point the operator at a capture that would fingerprint wrong data.
        return (
            "live evidence for this delivery plane needs its dedicated audit "
            "connector/pipeline — the generic capture seam does not fetch this dataset"
        )
    if live:
        return (
            f"capture a live fetch: PYTHONPATH=. python "
            f"scripts/capture_live_evidence.py --source {source_id}"
        )
    return "capture live evidence once delivery is live (needs credentials first)"


def provisioning_status(
    *,
    source_id: str,
    delivery_plane: str,
    delivery_mode: str,
    licence: LicenceRecord | None,
    evidence: list[LiveRuntimeEvidence] | None,
    retention: RetentionPolicy | None,
    as_of: date,
) -> ProvisioningStatus:
    """Compose the gate verdict into a next-action checklist (no logic duplicated).

    Reuses ``evaluate_data_source_operational`` for the per-control booleans, then
    annotates each unmet control with the exact next step. Honest: it reports what
    is missing and how to supply it — it never marks a control met without a record.
    """
    verdict = evaluate_data_source_operational(
        source_id=source_id,
        delivery_mode=delivery_mode,
        licence=licence,
        live_evidence=evidence,
        retention=retention,
        as_of=as_of,
    )
    live = delivery_mode == "live"
    controls = [
        ProvisioningControl(
            "delivery_live", live,
            "" if live
            else f"configure live credentials — {CREDENTIAL_HINT.get(delivery_plane, 'see connector docs')}",
        ),
        ProvisioningControl(
            "licence", verdict.licence_ok,
            "" if verdict.licence_ok
            else f"add a commercial-use LicenceRecord for {source_id!r} to "
                 "config/data_source_operational.json (shape in …example.json)",
        ),
        ProvisioningControl(
            "live_evidence", verdict.live_evidence_ok,
            "" if verdict.live_evidence_ok
            else _evidence_next_action(source_id, delivery_plane, live),
        ),
        ProvisioningControl(
            "retention", verdict.retention_ok,
            "" if verdict.retention_ok
            else f"declare a RetentionPolicy for {source_id!r} in "
                 "config/data_source_operational.json",
        ),
    ]
    return ProvisioningStatus(
        source_id=source_id,
        delivery_plane=delivery_plane,
        delivery_mode=delivery_mode,
        operational=verdict.operational,
        controls=controls,
    )


class OperationalRecordsStore:
    """Bundles licence/retention config + the evidence log for the gate."""

    def __init__(
        self,
        *,
        config_path: Path = DEFAULT_CONFIG_PATH,
        evidence_log: Path = DEFAULT_EVIDENCE_LOG,
    ) -> None:
        self.licences, self.retentions = load_licences_and_retentions(config_path)
        self.evidence = load_evidence(evidence_log)

    def verdicts(
        self, delivery_mode_by_source: dict[str, str], *, as_of: date | None = None
    ) -> dict[str, DataSourceOperationalVerdict]:
        return evaluate_sources_operational(
            delivery_mode_by_source=delivery_mode_by_source,
            licences=self.licences,
            evidence=self.evidence,
            retentions=self.retentions,
            as_of=as_of or date.today(),
        )

    def provisioning(
        self,
        delivery_by_source: dict[str, tuple[str, str]],
        *,
        as_of: date | None = None,
    ) -> dict[str, ProvisioningStatus]:
        """Per-source next-action checklists.

        ``delivery_by_source`` maps each source_id to ``(delivery_plane,
        delivery_mode)`` — the plane (e.g. ``"cds_zarr"``) drives the credential
        hint, the mode (``"live"``/``"fallback"``/…) drives whether evidence can
        be captured yet.
        """
        when = as_of or date.today()
        return {
            sid: provisioning_status(
                source_id=sid,
                delivery_plane=plane,
                delivery_mode=mode,
                licence=self.licences.get(sid),
                evidence=self.evidence.get(sid),
                retention=self.retentions.get(sid),
                as_of=when,
            )
            for sid, (plane, mode) in delivery_by_source.items()
        }


__all__ = [
    "CAPTURABLE_PLANES",
    "CREDENTIAL_HINT",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_EVIDENCE_LOG",
    "ConfigIssue",
    "OperationalRecordsStore",
    "ProvisioningControl",
    "ProvisioningStatus",
    "append_evidence",
    "capture_live_evidence",
    "load_evidence",
    "load_licences_and_retentions",
    "provisioning_status",
    "sample_sha256",
    "validate_operational_config",
]

"""Amsterdam Omgevingsplan Source Artifact.

Three-source sealed legal evidence:
  1. Legal text: /CVDR696291/15 (pinned version HTML)
  2. WTI metadata: /CVDR696291/15?show-wti=true (version/effectivity)
  3. Amendment publication: gmb-2026-243575 (official Gemeenteblad)

source_verified is derived from all three sources after hash verification
and content parsing. All verification flags are field(init=False) —
the constructor cannot set them to True.

Fail-closed:
  - Missing/tampered artifact → raise
  - Hash mismatch → raise
  - Parse failure → raise
  - Gate mismatch → raise
  - Current-law claim on/after a recorded successor's effective date →
    SOURCE_VERSION_SUPERSEDED (see assess_source_currency)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path


# Amsterdam Omgevingsplan — Paragraaf 4.4.2 / Artikel 4.116
AMSTERDAM_OMGEVINGSPLAN_URL = (
    "https://lokaleregelgeving.overheid.nl/CVDR696291"
)
AMSTERDAM_OMGEVINGSPLAN_VERSION_URL = (
    "https://lokaleregelgeving.overheid.nl/CVDR696291/15"
)
AMSTERDAM_OMGEVINGSPLAN_CVDR_ID = "CVDR696291"
AMSTERDAM_OMGEVINGSPLAN_VERSION_NUMBER = 15
AMSTERDAM_OMGEVINGSPLAN_RESOLVED_REF = "CVDR696291/15"
AMSTERDAM_OMGEVINGSPLAN_ID = "amsterdam-omgevingsplan-442"
AMSTERDAM_OMGEVINGSPLAN_TITLE = (
    "Omgevingsplan gemeente Amsterdam — "
    "Paragraaf 4.4.2 Hemelwaterafvoer bij bouwwerken"
)
AMSTERDAM_OMGEVINGSPLAN_LEGACY_URL = (
    "https://lokaleregelgeving.overheid.nl/DR000417648"
)

# Official version metadata from Overheid.nl WTI
AMSTERDAM_EFFECTIVE_FROM = "2026-06-19"
AMSTERDAM_EFFECTIVE_UNTIL = None
AMSTERDAM_LATEST_AMENDMENT_PUBLICATION = "gmb-2026-243575"
AMSTERDAM_OFFICIAL_VERSION_IDENTIFIER = "CVDR696291_15"
AMSTERDAM_DECISION_DATE = "2026-05-07"
AMSTERDAM_PUBLICATION_DATE = "2026-05-22"

# ---------------------------------------------------------------------------
# Source-version currency (scheduled supersession of the pinned version)
# ---------------------------------------------------------------------------
#
# The sealed WTI snapshot (retrieved 2026-08-27) records CVDR696291/15 as
# "Geldend van 19-06-2026 t/m heden". It predates the next amendment, so it
# cannot tell us when /15 stops being current law. The registry below carries
# that fact. It can only take a current-law claim away (fail closed on or
# after the successor's effective date); it never makes a claim stronger.
#
# Evidence status: the Gemeenteblad publication is NOT yet sealed in the
# provenance manifest (overheid.nl was unreachable from the acquisition
# environment). Until it is, the record is an unsealed official notice and
# is labelled as such in every pack that carries it.

SOURCE_VERSION_SUPERSEDED = "NL_AMS_SOURCE_VERSION_SUPERSEDED"
SOURCE_CURRENCY_AS_OF_INVALID = "NL_AMS_SOURCE_CURRENCY_AS_OF_INVALID"
SOURCE_VERSION_UNRECOGNIZED = "NL_AMS_SOURCE_VERSION_UNRECOGNIZED"
SOURCE_VERSION_NOT_YET_IN_FORCE = "NL_AMS_SOURCE_VERSION_NOT_YET_IN_FORCE"

CURRENCY_CURRENT = "current"
CURRENCY_CURRENT_PENDING_SUPERSESSION = "current_pending_supersession"
CURRENCY_SUPERSEDED = "superseded"
CURRENCY_UNDETERMINED = "undetermined"
CURRENCY_NOT_YET_IN_FORCE = "not_yet_in_force"

# Versions whose effective-from date comes from sealed WTI evidence. A
# reference not listed here has no currency evidence and is refused.
AMSTERDAM_SEALED_VERSION_EFFECTIVE_FROM: dict[str, str] = {
    AMSTERDAM_OMGEVINGSPLAN_RESOLVED_REF: AMSTERDAM_EFFECTIVE_FROM,
}

# Hemelwater articles whose mapping must be re-verified against the successor
# consolidated version before a current-law claim can resume.
AMSTERDAM_HEMELWATER_ARTICLES = ("Artikel 4.113", "Artikel 4.115", "Artikel 4.116")


@dataclass(frozen=True)
class SourceVersionSupersession:
    """A published amendment that ends a pinned version's current-law status."""
    superseded_ref: str
    superseding_publication: str
    superseding_publication_url: str
    superseding_title: str
    decision_date: str
    publication_date: str
    effective_from: str
    evidence_status: str
    successor_consolidated_ref: str | None
    reported_unamended_articles: tuple[str, ...]
    reported_unamended_verified: bool = field(init=False, default=False)

    @property
    def last_current_date(self) -> str:
        return (
            date.fromisoformat(self.effective_from) - timedelta(days=1)
        ).isoformat()

    def to_dict(self) -> dict:
        return {
            "superseded_ref": self.superseded_ref,
            "superseding_publication": self.superseding_publication,
            "superseding_publication_url": self.superseding_publication_url,
            "superseding_title": self.superseding_title,
            "decision_date": self.decision_date,
            "publication_date": self.publication_date,
            "effective_from": self.effective_from,
            "last_current_date": self.last_current_date,
            "evidence_status": self.evidence_status,
            "successor_consolidated_ref": self.successor_consolidated_ref,
            "reported_unamended_articles": list(self.reported_unamended_articles),
            "reported_unamended_verified": self.reported_unamended_verified,
        }


AMSTERDAM_SOURCE_SUPERSESSIONS: tuple[SourceVersionSupersession, ...] = (
    SourceVersionSupersession(
        superseded_ref="CVDR696291/15",
        superseding_publication="gmb-2026-430670",
        superseding_publication_url=(
            "https://zoek.officielebekendmakingen.nl/gmb-2026-430670"
        ),
        superseding_title=(
            "Wijzigingsbesluit Omgevingsplan gemeente Amsterdam: Toevoeging "
            "van regels over horeca, darkstores en evenementenlocaties"
        ),
        decision_date="2026-09-02",
        publication_date="2026-09-15",
        effective_from="2026-10-14",
        evidence_status="unsealed_official_notice",
        successor_consolidated_ref=None,
        # Reported by the change notice; not checked against a sealed
        # successor text, so reported_unamended_verified stays False.
        reported_unamended_articles=AMSTERDAM_HEMELWATER_ARTICLES,
    ),
)


@dataclass(frozen=True)
class SourceCurrencyAssessment:
    """Whether a pinned version may be asserted as current law on a date."""
    resolved_version_ref: str
    as_of: str
    currency_state: str
    current_law_claim_permitted: bool
    blocker_code: str | None
    supersession: SourceVersionSupersession | None
    required_actions: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "resolved_version_ref": self.resolved_version_ref,
            "as_of": self.as_of,
            "currency_state": self.currency_state,
            "current_law_claim_permitted": self.current_law_claim_permitted,
            "blocker_code": self.blocker_code,
            "supersession": (
                self.supersession.to_dict() if self.supersession else None
            ),
            "required_actions": list(self.required_actions),
        }


class SourceVersionNotCurrentError(ValueError):
    """Raised when a pack asserts a superseded version as current law."""

    def __init__(self, assessment: SourceCurrencyAssessment, message: str):
        super().__init__(f"{assessment.blocker_code}: {message}")
        self.assessment = assessment
        self.blocker_code = assessment.blocker_code


def _successor_required_actions(s: SourceVersionSupersession) -> tuple[str, ...]:
    return (
        "acquire the consolidated CVDR696291 version in force from "
        f"{s.effective_from} (incorporating {s.superseding_publication})",
        "hash and seal it, with its WTI metadata and the "
        f"{s.superseding_publication} publication, in the provenance manifest",
        "re-verify the "
        + "/".join(a.removeprefix("Artikel ") for a in s.reported_unamended_articles)
        + " rule mappings against the sealed successor text",
        "re-pin resolved_version_ref and rebuild the evidence pack",
    )


def _parse_as_of(as_of: date | datetime | str) -> date:
    if isinstance(as_of, datetime):
        return as_of.date()
    if isinstance(as_of, date):
        return as_of
    if isinstance(as_of, str) and as_of:
        # Accept a date or an ISO-8601 timestamp; the whole value must parse,
        # then its date part governs.
        if len(as_of) == 10:
            return date.fromisoformat(as_of)
        return datetime.fromisoformat(as_of).date()
    raise ValueError(f"unparseable as_of: {as_of!r}")


def assess_source_currency(
    resolved_version_ref: str,
    as_of: date | datetime | str,
) -> SourceCurrencyAssessment:
    """Decide whether ``resolved_version_ref`` may be claimed as current law.

    Fail-closed, in order:
      - unparseable ``as_of``                → SOURCE_CURRENCY_AS_OF_INVALID
      - reference without sealed effectivity → SOURCE_VERSION_UNRECOGNIZED
      - ``as_of`` before the version's sealed effective-from date
                                             → SOURCE_VERSION_NOT_YET_IN_FORCE
      - ``as_of`` on or after a recorded successor's effective date
                                             → SOURCE_VERSION_SUPERSEDED
    Otherwise the claim stands; flagged as pending supersession when a
    successor is recorded.
    """
    try:
        as_of_date = _parse_as_of(as_of)
    except (TypeError, ValueError):
        return SourceCurrencyAssessment(
            resolved_version_ref=resolved_version_ref,
            as_of=str(as_of),
            currency_state=CURRENCY_UNDETERMINED,
            current_law_claim_permitted=False,
            blocker_code=SOURCE_CURRENCY_AS_OF_INVALID,
            supersession=None,
            required_actions=("supply an ISO-8601 as_of date",),
        )

    effective_from = AMSTERDAM_SEALED_VERSION_EFFECTIVE_FROM.get(resolved_version_ref)
    if effective_from is None:
        return SourceCurrencyAssessment(
            resolved_version_ref=resolved_version_ref,
            as_of=as_of_date.isoformat(),
            currency_state=CURRENCY_UNDETERMINED,
            current_law_claim_permitted=False,
            blocker_code=SOURCE_VERSION_UNRECOGNIZED,
            supersession=None,
            required_actions=(
                f"seal WTI effectivity evidence for {resolved_version_ref!r} "
                "and register it before asserting it as current law",
            ),
        )
    if as_of_date < date.fromisoformat(effective_from):
        return SourceCurrencyAssessment(
            resolved_version_ref=resolved_version_ref,
            as_of=as_of_date.isoformat(),
            currency_state=CURRENCY_NOT_YET_IN_FORCE,
            current_law_claim_permitted=False,
            blocker_code=SOURCE_VERSION_NOT_YET_IN_FORCE,
            supersession=None,
            required_actions=(
                f"{resolved_version_ref} is in force from {effective_from}; "
                "use the version in force on the as_of date",
            ),
        )

    matches = [
        s for s in AMSTERDAM_SOURCE_SUPERSESSIONS
        if s.superseded_ref == resolved_version_ref
    ]
    if not matches:
        return SourceCurrencyAssessment(
            resolved_version_ref=resolved_version_ref,
            as_of=as_of_date.isoformat(),
            currency_state=CURRENCY_CURRENT,
            current_law_claim_permitted=True,
            blocker_code=None,
            supersession=None,
            required_actions=(),
        )

    # Earliest successor governs.
    s = min(matches, key=lambda m: m.effective_from)
    if as_of_date >= date.fromisoformat(s.effective_from):
        return SourceCurrencyAssessment(
            resolved_version_ref=resolved_version_ref,
            as_of=as_of_date.isoformat(),
            currency_state=CURRENCY_SUPERSEDED,
            current_law_claim_permitted=False,
            blocker_code=SOURCE_VERSION_SUPERSEDED,
            supersession=s,
            required_actions=_successor_required_actions(s),
        )
    return SourceCurrencyAssessment(
        resolved_version_ref=resolved_version_ref,
        as_of=as_of_date.isoformat(),
        currency_state=CURRENCY_CURRENT_PENDING_SUPERSESSION,
        current_law_claim_permitted=True,
        blocker_code=None,
        supersession=s,
        required_actions=_successor_required_actions(s),
    )


def require_current_law_claim(
    resolved_version_ref: str,
    as_of: date | datetime | str,
) -> SourceCurrencyAssessment:
    """Raise SourceVersionNotCurrentError unless the claim is permitted."""
    a = assess_source_currency(resolved_version_ref, as_of)
    if not a.current_law_claim_permitted:
        if a.supersession is not None:
            msg = (
                f"{resolved_version_ref} is not current law on {a.as_of}: "
                f"superseded from {a.supersession.effective_from} by "
                f"{a.supersession.superseding_publication}"
            )
        else:
            msg = (
                f"cannot assert {resolved_version_ref!r} as current law at "
                f"{a.as_of} ({a.currency_state})"
            )
        raise SourceVersionNotCurrentError(a, msg)
    return a


AMSTERDAM_THRESHOLDS = {
    "storage_requirement": {
        "threshold_id": "NL-AM-HW-STORAGE-001",
        "parameter": "storage_capacity_l_per_m2",
        "value": 60.0,
        "unit": "L/m²",
        "comparison": "gte",
        "article": "Artikel 4.116",
        "lid": "lid 1(a)",
        "description": "Minimum bergingscapaciteit",
    },
    "discharge_limit": {
        "threshold_id": "NL-AM-HW-DISCHARGE-001",
        "parameter": "max_discharge_l_per_m2_per_hour",
        "value": 1.0,
        "unit": "L/m²/h",
        "comparison": "lte",
        "article": "Artikel 4.116",
        "lid": "lid 1(b)",
        "description": "Lozingsnormering hemelwater",
    },
    "emptying_requirement": {
        "threshold_id": "NL-AM-HW-EMPTYING-001",
        "parameter": "max_emptying_time_hours",
        "value": 60.0,
        "unit": "h",
        "comparison": "lte",
        "article": "Artikel 4.116",
        "lid": "lid 1(c)",
        "description": "Ledigingstermijn",
    },
}


@dataclass(frozen=True)
class AmsterdamSourceArtifact:
    """Sealed Amsterdam regulatory source artifact.

    All verification flags are field(init=False) — the constructor
    cannot assert verified state. The loader sets them via
    object.__setattr__ only after evidence validation.
    """
    source_id: str
    title: str
    source_url: str
    cvdr_id: str
    version_number: int
    resolved_version_ref: str
    resolved_version_url: str
    retrieved_at: str
    effective_from: str
    effective_until: str | None
    artifact_sha256: str
    normalized_content_sha256: str
    regulatory_state: str
    latest_amendment_publication: str
    official_version_identifier: str
    rule_mapping_version: str
    # All verification flags: field(init=False), default False
    source_verified: bool = field(init=False, default=False)
    version_verified: bool = field(init=False, default=False)
    effective_status_verified: bool = field(init=False, default=False)
    amendment_chain_verified: bool = field(init=False, default=False)
    rule_mapping_verified: bool = field(init=False, default=False)
    publication_type: str = "gemeenteblad"
    authority: str = "Gemeente Amsterdam"
    license_id: str = "Public Domain Mark 1.0"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "source_url": self.source_url,
            "cvdr_id": self.cvdr_id,
            "version_number": self.version_number,
            "resolved_version_ref": self.resolved_version_ref,
            "resolved_version_url": self.resolved_version_url,
            "retrieved_at": self.retrieved_at,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "artifact_sha256": self.artifact_sha256,
            "normalized_content_sha256": self.normalized_content_sha256,
            "source_verified": self.source_verified,
            "regulatory_state": self.regulatory_state,
            "version_verified": self.version_verified,
            "effective_status_verified": self.effective_status_verified,
            "latest_amendment_publication": self.latest_amendment_publication,
            "official_version_identifier": self.official_version_identifier,
            "amendment_chain_verified": self.amendment_chain_verified,
            "rule_mapping_verified": self.rule_mapping_verified,
            "rule_mapping_version": self.rule_mapping_version,
        }


def compute_artifact_hash(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()


def compute_normalized_hash_html(content_bytes: bytes) -> str:
    """SHA-256 of normalized HTML: strip tags + normalize whitespace."""
    text = content_bytes.decode("utf-8", errors="replace")
    text_clean = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE
    )
    text_clean = re.sub(
        r"<style[^>]*>.*?</style>", "", text_clean, flags=re.DOTALL | re.IGNORECASE
    )
    text_clean = re.sub(r"<[^>]+>", " ", text_clean)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()
    return hashlib.sha256(text_clean.encode("utf-8")).hexdigest()


def _require_source_entry(manifest: dict, source_id: str) -> dict:
    """Load and validate a source entry from the manifest."""
    sources = manifest.get("sources", {})
    if source_id not in sources:
        raise ValueError(
            f"Source entry '{source_id}' missing from manifest. "
            f"Available: {list(sources.keys())}"
        )
    src = sources[source_id]
    required = [
        "snapshot_path", "artifact_sha256", "normalized_content_sha256",
    ]
    for field_name in required:
        if field_name not in src:
            raise ValueError(
                f"Source '{source_id}' missing required field: {field_name}"
            )
    return src


def _verify_and_load_artifact(
    src: dict,
    label: str,
) -> tuple[bytes, str, str]:
    """Verify hash integrity and load raw bytes from a sealed artifact."""
    path = Path(src["snapshot_path"])
    if not path.exists():
        raise FileNotFoundError(f"{label} snapshot not found: {path}")
    raw = path.read_bytes()
    if len(raw) == 0:
        raise ValueError(f"{label} snapshot is empty: {path}")

    actual_sha = compute_artifact_hash(raw)
    if actual_sha != src["artifact_sha256"]:
        raise ValueError(
            f"{label} artifact hash mismatch: "
            f"computed {actual_sha} != manifest {src['artifact_sha256']}. "
            f"Artifact may have been tampered with."
        )

    actual_norm = compute_normalized_hash_html(raw)
    if actual_norm != src["normalized_content_sha256"]:
        raise ValueError(
            f"{label} normalized hash mismatch: "
            f"computed {actual_norm} != manifest {src['normalized_content_sha256']}."
        )

    return raw, actual_sha, actual_norm


def _parse_wti_evidence(raw_bytes: bytes) -> dict:
    """Parse WTI metadata from sealed HTML artifact.

    Returns derived version/effectivity facts.
    Raises ValueError if required facts cannot be parsed.
    """
    text = raw_bytes.decode("utf-8", errors="replace")
    text_clean = re.sub(r"<[^>]+>", " ", text)
    text_clean = re.sub(r"\s+", " ", text_clean)

    result = {}

    # Parse effective date: "Geldend van 19-06-2026 t/m heden"
    m = re.search(r"Geldend\s+van\s+(\d{2}-\d{2}-\d{4})", text_clean)
    if m:
        parts = m.group(1).split("-")
        result["effective_from"] = f"{parts[2]}-{parts[1]}-{parts[0]}"
    else:
        raise ValueError("WTI: cannot parse effective_from (Geldend van)")

    if re.search(r"t/m\s+heden", text_clean):
        result["effective_until"] = None
    else:
        raise ValueError("WTI: cannot confirm current status (t/m heden)")

    # Parse amendment reference linked to the current version's effective date.
    # The WTI page has many Gemeenteblad refs; we need the one associated
    # with the 19-06-2026 effective date (wijziging 07-05-2026).
    # Pattern: "wijziging 07-05-2026 Gemeenteblad 2026,243575"
    m = re.search(
        r"wijziging\s+\d{2}-\d{2}-\d{4}\s+Gemeenteblad\s+(\d{4}),(\d+)",
        text_clean,
    )
    if m:
        result["amendment_publication"] = f"gmb-{m.group(1)}-{m.group(2)}"
    else:
        # Fallback: find Gemeenteblad ref near the effective date
        eff_section = re.search(
            r"19-06-2026.*?Gemeenteblad\s+(\d{4}),(\d+)", text_clean, re.DOTALL
        )
        if eff_section:
            result["amendment_publication"] = (
                f"gmb-{eff_section.group(1)}-{eff_section.group(2)}"
            )
        else:
            raise ValueError("WTI: cannot parse amendment publication")

    # Parse version: "CVDR696291/15" or "CVDR696291_15"
    m = re.search(r"CVDR696291[/_](\d+)", text_clean)
    if m:
        result["version_number"] = int(m.group(1))
    else:
        raise ValueError("WTI: cannot parse version number")

    result["regulatory_state"] = "current_in_force"
    return result


def _parse_amendment_evidence(raw_bytes: bytes) -> dict:
    """Parse amendment publication metadata from sealed HTML artifact.

    Uses structured HTML data-before attributes for reliable date extraction.
    Official source contract:
      Datum ondertekening = 2026-05-07
      Publicatiedatum      = 2026-05-22
      Regeling             = CVDR696291_15
      Identifier           = gmb-2026-243575

    Returns derived amendment facts.
    Raises ValueError if required facts cannot be parsed.
    """
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    text_clean = re.sub(r"<[^>]+>", " ", raw_text)
    text_clean = re.sub(r"\s+", " ", text_clean)

    result = {}

    # Parse publication ID: "gmb-2026-243575"
    m = re.search(r"gmb-\d{4}-\d+", text_clean)
    if m:
        result["publication_id"] = m.group(0)
    else:
        raise ValueError("Amendment: cannot parse publication_id")

    # Parse decision date from data-before="Datum ondertekening" structure
    # <td data-before="Datum ondertekening"><time datetime="2026-05-07">07-05-2026</time></td>
    m = re.search(
        r'data-before="Datum\s+ondertekening"[^>]*>.*?'
        r'datetime="(\d{4}-\d{2}-\d{2})',
        raw_text, re.DOTALL,
    )
    if m:
        result["decision_date"] = m.group(1)
    else:
        # Fallback: look for the date near "Datum ondertekening" in stripped text
        m = re.search(
            r"Datum\s+ondertekening.*?(\d{4}-\d{2}-\d{2})", text_clean
        )
        if m:
            result["decision_date"] = m.group(1)
        else:
            raise ValueError("Amendment: cannot parse decision_date")

    # Parse publication date from data-before="Datum publicatie" structure
    m = re.search(
        r'data-before="Datum\s+publicatie"[^>]*>.*?'
        r'datetime="(\d{4}-\d{2}-\d{2})',
        raw_text, re.DOTALL,
    )
    if m:
        result["publication_date"] = m.group(1)
    else:
        m = re.search(r"Publicatiedatum\s+(\d{4}-\d{2}-\d{2})", text_clean)
        if m:
            result["publication_date"] = m.group(1)
        else:
            raise ValueError("Amendment: cannot parse publication_date")

    # Parse version identifier: "CVDR696291_15"
    m = re.search(r"Regeling\s+CVDR696291_(\d+)", text_clean)
    if m:
        result["official_version_identifier"] = f"CVDR696291_{m.group(1)}"
    else:
        raise ValueError("Amendment: cannot parse official_version_identifier")

    return result


def _derive_rule_mapping(raw_bytes: bytes) -> bool:
    """Parse pinned legal text and verify Artikel 4.113/4.116 thresholds."""
    text = raw_bytes.decode("utf-8", errors="replace")
    text_clean = re.sub(r"<[^>]+>", " ", text)
    text_clean = re.sub(r"\s+", " ", text_clean)

    checks = [
        "Artikel 4.113" in text_clean,
        "Artikel 4.116" in text_clean,
        bool(re.search(r"60\s*liter\s*per\s*m\s*2", text_clean, re.IGNORECASE)),
        bool(re.search(r"1\s*liter\s*per\s*m\s*2.*per\s*uur", text_clean, re.IGNORECASE)),
        bool(re.search(r"60\s*uur", text_clean, re.IGNORECASE)),
    ]
    return all(checks)


def load_sealed_snapshot(
    snapshot_path: Path,
    manifest_path: Path | None = None,
) -> AmsterdamSourceArtifact:
    """Load and verify a sealed Amsterdam Omgevingsplan from three sources.

    Three-source gate:
      1. Legal text: hash verification + rule mapping derivation
      2. WTI metadata: hash verification + version/effectivity parsing
      3. Amendment publication: hash verification + publication/version parsing

    The supplied snapshot_path is the authoritative legal artifact path.
    It is verified against manifest hashes — not silently replaced.

    source_verified is derived from all gates. All verification flags
    are set via object.__setattr__ after construction.

    The loader NEVER returns source_verified=False. It raises instead.

    Raises FileNotFoundError if any artifact is missing.
    Raises ValueError if any gate fails.
    """
    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"Sealed snapshot not found: {snapshot_path}"
        )

    # Resolve manifest
    if manifest_path is None:
        manifest_path = (
            snapshot_path.parent.parent.parent
            / "provenance-manifest-amsterdam-v1.json"
        )
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())

    # --- Source 1: Legal text artifact ---
    # Verify the SUPPLIED snapshot_path matches manifest expectation
    legal_src = _require_source_entry(
        manifest, "amsterdam-omgevingsplan-cvdr696291"
    )
    expected_path = Path(legal_src["snapshot_path"])
    if snapshot_path.resolve() != expected_path.resolve():
        raise ValueError(
            f"Supplied snapshot path {snapshot_path} does not match "
            f"manifest legal source path {expected_path}"
        )

    # Verify the actual bytes of the supplied file
    legal_raw = snapshot_path.read_bytes()
    if len(legal_raw) == 0:
        raise ValueError(f"Legal snapshot is empty: {snapshot_path}")
    actual_sha = compute_artifact_hash(legal_raw)
    if actual_sha != legal_src["artifact_sha256"]:
        raise ValueError(
            f"Legal artifact hash mismatch: supplied={actual_sha} "
            f"!= manifest={legal_src['artifact_sha256']}"
        )
    actual_norm = compute_normalized_hash_html(legal_raw)
    if actual_norm != legal_src["normalized_content_sha256"]:
        raise ValueError(
            f"Legal normalized hash mismatch: computed={actual_norm} "
            f"!= manifest={legal_src['normalized_content_sha256']}"
        )

    # Derive rule mapping from actual content
    derived_rule_mapping = _derive_rule_mapping(legal_raw)

    # Verify derived rule mapping matches manifest
    manifest_rule_mapping = legal_src.get("rule_mapping_verified", False)
    if derived_rule_mapping != manifest_rule_mapping:
        raise ValueError(
            f"rule_mapping_verified mismatch: content-derived={derived_rule_mapping} "
            f"!= manifest={manifest_rule_mapping}"
        )
    rule_mapping_verified = derived_rule_mapping

    # --- Source 2: WTI metadata artifact ---
    wti_id = "amsterdam-omgevingsplan-cvdr696291-v15-wti"
    wti_src = _require_source_entry(manifest, wti_id)
    wti_raw, _, _ = _verify_and_load_artifact(wti_src, "WTI metadata")
    wti_facts = _parse_wti_evidence(wti_raw)

    # Verify WTI-derived facts against manifest
    if wti_facts["version_number"] != legal_src.get("version_number"):
        raise ValueError(
            f"WTI version_number {wti_facts['version_number']} "
            f"!= manifest {legal_src.get('version_number')}"
        )
    if wti_facts["effective_from"] != legal_src.get("effective_from"):
        raise ValueError(
            f"WTI effective_from {wti_facts['effective_from']} "
            f"!= manifest {legal_src.get('effective_from')}"
        )

    version_verified = True
    effective_status_verified = True

    # --- Source 3: Amendment publication metadata ---
    amendment_id = "amsterdam-gmb-2026-243575-metadata"
    amendment_src = _require_source_entry(manifest, amendment_id)
    amendment_raw, _, _ = _verify_and_load_artifact(
        amendment_src, "Amendment publication"
    )
    amendment_facts = _parse_amendment_evidence(amendment_raw)

    # Verify amendment chain linkage including dates
    amendment_chain_verified = (
        wti_facts["amendment_publication"] == amendment_facts["publication_id"]
        and amendment_facts["publication_id"] == "gmb-2026-243575"
        and amendment_facts["official_version_identifier"] == "CVDR696291_15"
        and amendment_facts["decision_date"] == "2026-05-07"
        and amendment_facts["publication_date"] == "2026-05-22"
    )
    if not amendment_chain_verified:
        raise ValueError(
            f"Amendment chain mismatch: "
            f"WTI={wti_facts['amendment_publication']}, "
            f"gmb={amendment_facts['publication_id']}, "
            f"version={amendment_facts['official_version_identifier']}, "
            f"decision={amendment_facts.get('decision_date')}, "
            f"pub={amendment_facts.get('publication_date')}"
        )

    # --- Fail closed: every gate must be true ---
    if not version_verified:
        raise ValueError("version_verified=false — cannot proceed")
    if not effective_status_verified:
        raise ValueError("effective_status_verified=false — cannot proceed")
    if not amendment_chain_verified:
        raise ValueError("amendment_chain_verified=false — cannot proceed")
    if not rule_mapping_verified:
        raise ValueError("rule_mapping_verified=false — cannot proceed")

    source_verified = True  # All gates passed

    # --- Construct artifact (all verification flags default False) ---
    artifact = AmsterdamSourceArtifact(
        source_id=AMSTERDAM_OMGEVINGSPLAN_ID,
        title=AMSTERDAM_OMGEVINGSPLAN_TITLE,
        source_url=AMSTERDAM_OMGEVINGSPLAN_VERSION_URL,
        cvdr_id="CVDR696291",
        version_number=wti_facts["version_number"],
        resolved_version_ref="CVDR696291/15",
        resolved_version_url=AMSTERDAM_OMGEVINGSPLAN_VERSION_URL,
        retrieved_at=legal_src.get("retrieved_at", ""),
        effective_from=wti_facts["effective_from"],
        effective_until=wti_facts["effective_until"],
        artifact_sha256=legal_src["artifact_sha256"],
        normalized_content_sha256=legal_src["normalized_content_sha256"],
        regulatory_state=wti_facts["regulatory_state"],
        latest_amendment_publication=wti_facts["amendment_publication"],
        official_version_identifier=amendment_facts["official_version_identifier"],
        rule_mapping_version="CVDR696291/15",
    )

    # Set verification flags via __setattr__ (frozen dataclass)
    object.__setattr__(artifact, "source_verified", source_verified)
    object.__setattr__(artifact, "version_verified", version_verified)
    object.__setattr__(artifact, "effective_status_verified", effective_status_verified)
    object.__setattr__(artifact, "amendment_chain_verified", amendment_chain_verified)
    object.__setattr__(artifact, "rule_mapping_verified", rule_mapping_verified)

    return artifact


def fetch_omgevingsplan_artifact() -> dict:
    """Fetch the Amsterdam Omgevingsplan from Overheid.nl.

    NOTE: Live fetch — use sealed snapshot in CI.
    """
    import urllib.request
    try:
        req = urllib.request.Request(
            AMSTERDAM_OMGEVINGSPLAN_VERSION_URL,
            headers={"Accept": "text/html", "User-Agent": "GeoRisk-Engine/1.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return {
                "url": AMSTERDAM_OMGEVINGSPLAN_VERSION_URL,
                "cvdr_id": AMSTERDAM_OMGEVINGSPLAN_CVDR_ID,
                "version_number": AMSTERDAM_OMGEVINGSPLAN_VERSION_NUMBER,
                "content": raw.decode("utf-8", errors="replace"),
                "content_bytes": raw,
                "content_type": resp.headers.get("Content-Type", ""),
            }
    except Exception as e:
        raise RuntimeError(
            f"Omgevingsplan fetch failed: {e}"
        ) from e

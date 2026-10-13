"""Source qualification + sealed evidence pack for a real flood-hazard map.

Before a real return-period flood-hazard map (``flood_hazard_map``) may be trusted
as the reference-level source — and long before v0.4 flood could become the default
— the *source* must be **qualified**: a fail-closed check that the map is real,
licensed, in the right datum, covers the required area at the required return
periods, and is bound to a **sealed evidence pack** by hash.

The evidence pack is the auditable artifact a regulated buyer asks for: it names
the source, the exact map artifact (by SHA-256), the licence/use-rights, the datum,
the methodology citation, and the coverage the source is claimed to satisfy. The
gate verifies every claim against the actual sealed map and fails closed with the
reason on any gap. Nothing here promotes v0.4 to default — that is a separate
decision gated on this qualification plus exact-head test/review.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.loss.flood_hazard_map import FloodHazardMap, load_flood_hazard_map_from_path

REQUIRED_DATUM = "NAP"  # the NL elevation datum the depth math shares


def _is_sha256_hex(value: str) -> bool:
    v = value.strip().lower()
    return len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class FloodMapLicence(BaseModel):
    """Use rights for a flood-hazard source (e.g. NL LIWO / Rijkswaterstaat)."""

    licensor: str
    use_rights: str  # e.g. "public-with-attribution", "commercial"
    attribution: str
    valid_from: date
    valid_until: date | None = None  # None = perpetual


class RequiredPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    label: str = ""


class FloodSourceEvidencePack(BaseModel):
    """The sealed evidence that qualifies a real flood-hazard map source."""

    source_id: str
    map_artifact: str  # filename of the sealed map, for the record
    map_artifact_sha256: str  # binds this pack to the exact sealed map bytes
    datum: str
    licence: FloodMapLicence
    methodology: str
    required_points: list[RequiredPoint]
    required_return_periods: list[int]
    note: str = ""

    def seal_sha256(self) -> str:
        """Canonical SHA-256 of the pack contents (the pack's own seal)."""
        return hashlib.sha256(_canonical(self.model_dump(mode="json"))).hexdigest()


@dataclass(frozen=True)
class FloodSourceQualificationVerdict:
    """Fail-closed verdict: is this flood-hazard source qualified for use?"""

    qualified: bool
    source_id: str
    real_source_ok: bool
    artifact_bound_ok: bool
    licence_ok: bool
    datum_ok: bool
    coverage_ok: bool
    methodology_ok: bool
    pack_sha256: str
    reasons: list[str] = field(default_factory=list)
    evaluated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualified": self.qualified,
            "source_id": self.source_id,
            "checks": {
                "real_source_ok": self.real_source_ok,
                "artifact_bound_ok": self.artifact_bound_ok,
                "licence_ok": self.licence_ok,
                "datum_ok": self.datum_ok,
                "coverage_ok": self.coverage_ok,
                "methodology_ok": self.methodology_ok,
            },
            "pack_sha256": self.pack_sha256,
            "reasons": list(self.reasons),
            "evaluated_at": self.evaluated_at,
        }


def load_evidence_pack(path: str | Path) -> FloodSourceEvidencePack:
    return FloodSourceEvidencePack(**json.loads(Path(path).read_text(encoding="utf-8")))


def evaluate_flood_source_qualification(
    *,
    pack: FloodSourceEvidencePack,
    map_path: str | Path,
    as_of: date,
    required_datum: str = REQUIRED_DATUM,
    evaluated_at: str | None = None,
) -> FloodSourceQualificationVerdict:
    """Decide whether a flood-hazard source is qualified for use (fail-closed).

    Verifies, against the actual sealed map at ``map_path``: it is real (not a
    labelled synthetic fixture) and its provenance sidecar checks out; the pack's
    ``map_artifact_sha256`` binds to the exact bytes; the licence is in effect with
    use rights + attribution; the datum matches; every required point is covered at
    every required return period; and a methodology is cited.
    """
    reasons: list[str] = []
    p = Path(map_path)

    # --- load the map (provenance-verified for a real one) ---
    fmap: FloodHazardMap | None = None
    real_source_ok = False
    try:
        fmap = load_flood_hazard_map_from_path(p)
    except (ValueError, FileNotFoundError, OSError) as exc:
        reasons.append(f"flood-hazard map could not be loaded/verified: {exc}")
    if fmap is not None:
        if fmap.synthetic:
            reasons.append(
                "flood-hazard map is a labelled SYNTHETIC fixture — a qualified "
                "source must be real (vendor NL LIWO / flood-extent water levels)"
            )
        else:
            real_source_ok = True

    # --- artifact binding: pack SHA-256 must match the exact map bytes ---
    artifact_bound_ok = False
    if not _is_sha256_hex(pack.map_artifact_sha256):
        reasons.append("pack.map_artifact_sha256 is not a 64-hex SHA-256 digest")
    elif p.exists():
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual == pack.map_artifact_sha256.strip().lower():
            artifact_bound_ok = True
        else:
            reasons.append(
                f"pack does not bind to this map artifact "
                f"({actual[:16]}… vs pack {pack.map_artifact_sha256[:16]}…)"
            )
    else:
        reasons.append(f"map artifact {p.name!r} does not exist")

    # --- licence ---
    lic = pack.licence
    licence_ok = False
    if not lic.licensor.strip() or not lic.attribution.strip():
        reasons.append("licence is missing a licensor or attribution")
    elif not lic.use_rights.strip():
        reasons.append("licence does not state use rights")
    elif lic.valid_from > as_of:
        reasons.append(f"licence is not yet in effect (valid_from {lic.valid_from})")
    elif lic.valid_until is not None and lic.valid_until < as_of:
        reasons.append(f"licence expired on {lic.valid_until}")
    else:
        licence_ok = True

    # --- datum consistency (elevation and reference level must share a datum) ---
    datum_ok = False
    map_datum = fmap.datum if fmap is not None else "?"
    if pack.datum != required_datum:
        reasons.append(f"pack datum {pack.datum!r} is not the required {required_datum!r}")
    elif fmap is not None and map_datum != required_datum:
        reasons.append(f"map datum {map_datum!r} is not the required {required_datum!r}")
    else:
        datum_ok = True

    # --- coverage: every required point at every required return period ---
    # Coverage is a property of the map data, checked whenever the map loaded —
    # independent of whether the source is real (that is its own control).
    coverage_ok = False
    if not pack.required_points or not pack.required_return_periods:
        reasons.append("pack declares no required points / return periods to qualify")
    elif fmap is not None:
        gaps: list[str] = []
        for pt in pack.required_points:
            for rp in pack.required_return_periods:
                try:
                    fmap.reference_level_at(pt.lat, pt.lon, rp)
                except ValueError:
                    gaps.append(f"{pt.label or f'{pt.lat},{pt.lon}'}@T{rp}")
        if gaps:
            reasons.append(f"map does not cover required point(s)/period(s): {gaps[:6]}")
        else:
            coverage_ok = True
    else:
        reasons.append("coverage not verifiable (map not loaded)")

    # --- methodology ---
    methodology_ok = bool(pack.methodology.strip())
    if not methodology_ok:
        reasons.append("pack cites no methodology / source")

    qualified = not reasons
    return FloodSourceQualificationVerdict(
        qualified=qualified,
        source_id=pack.source_id,
        real_source_ok=real_source_ok,
        artifact_bound_ok=artifact_bound_ok,
        licence_ok=licence_ok,
        datum_ok=datum_ok,
        coverage_ok=coverage_ok,
        methodology_ok=methodology_ok,
        pack_sha256=pack.seal_sha256(),
        reasons=reasons,
        evaluated_at=evaluated_at,
    )


__all__ = [
    "REQUIRED_DATUM",
    "FloodMapLicence",
    "FloodSourceEvidencePack",
    "FloodSourceQualificationVerdict",
    "RequiredPoint",
    "evaluate_flood_source_qualification",
    "load_evidence_pack",
]

"""Tests for flood-source qualification + the sealed evidence pack gate."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from app.loss.flood_hazard_map import _CURVES_DIR
from app.loss.flood_source_qualification import (
    FloodMapLicence,
    FloodSourceEvidencePack,
    RequiredPoint,
    evaluate_flood_source_qualification,
    load_evidence_pack,
)

_AS_OF = date(2026, 6, 1)
_FIXTURE_MAP = _CURVES_DIR / "flood_hazard_map_fixture_v0.1.json"
# Pilot points (cells 52.38,4.88 and 52.37,4.92).
_PTS = [RequiredPoint(lat=52.3782, lon=4.8835, label="cluster"),
        RequiredPoint(lat=52.3698, lon=4.9247, label="outlier")]


def _write_real_map(tmp_path: Path) -> tuple[Path, str]:
    obj = {
        "map_id": "flood_hazard_map", "version": "1.0", "source": "NL LIWO test",
        "datum": "NAP", "cell_size_deg": 0.01, "synthetic": False, "populated": True,
        "levels": [
            {"cell_id": "52.38,4.88", "return_period_years": 100, "water_level_m": 1.62},
            {"cell_id": "52.37,4.92", "return_period_years": 100, "water_level_m": 1.41},
        ],
    }
    raw = json.dumps(obj, indent=2, ensure_ascii=True).encode("utf-8")
    p = tmp_path / "flood_hazard_map_v1.0.json"
    p.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    (tmp_path / "flood_hazard_map_v1.0.provenance.json").write_text(
        json.dumps({"artifact_sha256": sha})
    )
    return p, sha


def _pack(sha: str, **over) -> FloodSourceEvidencePack:
    base = dict(
        source_id="nl_liwo_flood_hazard",
        map_artifact="flood_hazard_map_v1.0.json",
        map_artifact_sha256=sha,
        datum="NAP",
        licence=FloodMapLicence(
            licensor="Rijkswaterstaat / LIWO", use_rights="public-with-attribution",
            attribution="Bron: LIWO", valid_from=date(2026, 1, 1), valid_until=date(2027, 1, 1),
        ),
        methodology="NL LIWO overstromingsdiepte, test DOI",
        required_points=_PTS,
        required_return_periods=[100],
    )
    base.update(over)
    return FloodSourceEvidencePack(**base)


def test_real_map_with_matching_pack_is_qualified(tmp_path):
    p, sha = _write_real_map(tmp_path)
    v = evaluate_flood_source_qualification(pack=_pack(sha), map_path=p, as_of=_AS_OF)
    assert v.qualified is True and v.reasons == []
    assert all([v.real_source_ok, v.artifact_bound_ok, v.licence_ok,
                v.datum_ok, v.coverage_ok, v.methodology_ok])


def test_synthetic_fixture_map_is_not_qualified():
    sha = hashlib.sha256(_FIXTURE_MAP.read_bytes()).hexdigest()
    v = evaluate_flood_source_qualification(pack=_pack(sha), map_path=_FIXTURE_MAP, as_of=_AS_OF)
    # Artifact binds, but a synthetic fixture can never qualify.
    assert v.qualified is False and v.artifact_bound_ok is True and v.real_source_ok is False
    assert any("SYNTHETIC" in r for r in v.reasons)


def test_artifact_binding_mismatch_fails(tmp_path):
    p, _ = _write_real_map(tmp_path)
    v = evaluate_flood_source_qualification(pack=_pack("a" * 64), map_path=p, as_of=_AS_OF)
    assert v.qualified is False and v.artifact_bound_ok is False


def test_non_sha256_binding_rejected(tmp_path):
    p, _ = _write_real_map(tmp_path)
    v = evaluate_flood_source_qualification(pack=_pack("not-a-hash"), map_path=p, as_of=_AS_OF)
    assert v.artifact_bound_ok is False
    assert any("not a 64-hex" in r for r in v.reasons)


def test_expired_licence_fails(tmp_path):
    p, sha = _write_real_map(tmp_path)
    lic = FloodMapLicence(licensor="X", use_rights="commercial", attribution="a",
                          valid_from=date(2025, 1, 1), valid_until=date(2025, 12, 31))
    v = evaluate_flood_source_qualification(pack=_pack(sha, licence=lic), map_path=p, as_of=_AS_OF)
    assert v.licence_ok is False and v.qualified is False
    assert any("expired" in r for r in v.reasons)


def test_licence_not_yet_in_effect_fails(tmp_path):
    p, sha = _write_real_map(tmp_path)
    lic = FloodMapLicence(licensor="X", use_rights="commercial", attribution="a",
                          valid_from=date(2027, 1, 1))
    v = evaluate_flood_source_qualification(pack=_pack(sha, licence=lic), map_path=p, as_of=_AS_OF)
    assert v.licence_ok is False and any("not yet in effect" in r for r in v.reasons)


def test_datum_mismatch_fails(tmp_path):
    p, sha = _write_real_map(tmp_path)
    v = evaluate_flood_source_qualification(pack=_pack(sha, datum="WGS84"), map_path=p, as_of=_AS_OF)
    assert v.datum_ok is False and any("datum" in r for r in v.reasons)


def test_coverage_gap_fails(tmp_path):
    p, sha = _write_real_map(tmp_path)
    # Require a return period (10yr) the real map does not carry.
    v = evaluate_flood_source_qualification(
        pack=_pack(sha, required_return_periods=[10]), map_path=p, as_of=_AS_OF
    )
    assert v.coverage_ok is False and any("does not cover" in r for r in v.reasons)


def test_missing_methodology_fails(tmp_path):
    p, sha = _write_real_map(tmp_path)
    v = evaluate_flood_source_qualification(pack=_pack(sha, methodology="  "), map_path=p, as_of=_AS_OF)
    assert v.methodology_ok is False and any("methodology" in r for r in v.reasons)


def test_pack_seal_is_deterministic_and_survives_roundtrip(tmp_path):
    p, sha = _write_real_map(tmp_path)
    pack = _pack(sha)
    seal = pack.seal_sha256()
    # Write with an extra pack_sha256 key (as the build script does) and reload.
    body = pack.model_dump(mode="json")
    body["pack_sha256"] = seal
    packfile = tmp_path / "pack.json"
    packfile.write_text(json.dumps(body))
    reloaded = load_evidence_pack(packfile)
    assert reloaded.seal_sha256() == seal  # extra key ignored, seal stable


def test_verdict_to_dict_shape(tmp_path):
    p, sha = _write_real_map(tmp_path)
    v = evaluate_flood_source_qualification(pack=_pack(sha), map_path=p, as_of=_AS_OF)
    d = v.to_dict()
    assert d["qualified"] is True and set(d["checks"]) == {
        "real_source_ok", "artifact_bound_ok", "licence_ok",
        "datum_ok", "coverage_ok", "methodology_ok",
    }
    assert len(d["pack_sha256"]) == 64

#!/usr/bin/env python3
"""Deterministic generator for the Amsterdam Hemelwater Regulatory Evidence Pack.

Produces a machine-readable JSON evidence pack that maps Dutch
hemelwater (rainwater management) regulatory rules to per-asset
regulatory screening states.

Usage:
    python scripts/generate_regulatory_evidence_pack.py \
        --portfolio data/portfolios/synthetic/reference_portfolio.json \
        --output data/regulatory_evidence_packs/nl-amsterdam-hemelwater-2026-v1.json

This tool does NOT:
- Access any external data source
- Modify any readiness flags or release manifest
- Produce compliance certifications
- Replace human legal review

All outputs are explicitly labelled as decision-support evidence.

Provenance chain:
    official artifact bytes
        → source SHA256 (artifact_sha256)
        → article / paragraph / lid
        → threshold value
        → rule
        → asset applicability evidence
        → evidence pack
        → pack SHA256

The pack SHA256 and the artifact SHA256 are two separate checksums.
The artifact SHA256 fingerprints the retrieved official publication;
the pack SHA256 fingerprints the generated evidence pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.regulation.models import (
    AssetVerification,
    PackClassification,
    Jurisdiction,
    RegulatoryRule,
    RegulatorySource,
)
from app.regulation.rules import (
    PLACEHOLDER_NOT_VERIFIED,
    amsterdam_hemelwater_classification,
    amsterdam_hemelwater_jurisdiction,
    amsterdam_hemelwater_provenance,
    amsterdam_hemelwater_rules,
    amsterdam_hemelwater_sources,
    amsterdam_source_artifacts,
)
from app.regulation.verify import verify_asset

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERATOR_VERSION = "0.2.0"
PACK_ID = "NL-AMSTERDAM-HEMELWATER-2026-V1"
PACK_VERSION = 1
SCHEMA_VERSION = "1.1"
DEFAULT_SEED = 42


# ---------------------------------------------------------------------------
# Deterministic JSON serialization
# ---------------------------------------------------------------------------

def _deterministic_json(obj: object) -> str:
    """Serialize to canonical JSON: sorted keys, no extra whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compute_checksum(content_dict: dict) -> str:
    """SHA-256 of deterministic JSON serialization of content (excluding envelope)."""
    canonical = _deterministic_json(content_dict)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Build the evidence pack
# ---------------------------------------------------------------------------

def build_evidence_pack(
    assets: list[dict],
    *,
    deterministic_seed: int = DEFAULT_SEED,
    output_path: str | None = None,
) -> dict:
    """Build the complete evidence pack dict.

    Parameters
    ----------
    assets : list[dict]
        Portfolio assets. Each must have at minimum:
        asset_id, address, coordinates, built_area_m2,
        use_class, municipality, water_authority.
    deterministic_seed : int
        Seed for reproducibility documentation (the generator
        itself is fully deterministic from inputs).
    output_path : str | None
        If provided, written atomically.
    """
    rules = amsterdam_hemelwater_rules()
    sources = amsterdam_hemelwater_sources()
    artifacts = amsterdam_source_artifacts()
    provenance = amsterdam_hemelwater_provenance()
    jurisdiction = amsterdam_hemelwater_jurisdiction()
    classification = amsterdam_hemelwater_classification()

    # Source hash verification
    for src in sources:
        if src.status not in ("current",):
            raise SystemExit(
                f"FAIL-CLOSED: source '{src.source_id}' has status '{src.status}'; "
                f"only 'current' sources are permitted"
            )
        if not src.source_checksums_verified:
            if src.content_hash != PLACEHOLDER_NOT_VERIFIED:
                raise SystemExit(
                    f"FAIL-CLOSED: source '{src.source_id}' has source_checksums_verified=False "
                    f"but content_hash is not PLACEHOLDER_NOT_VERIFIED"
                )

    # Verify all source_ids referenced by rules exist
    source_ids = {s.source_id for s in sources}
    for rule in rules:
        if rule.source_id not in source_ids:
            raise SystemExit(
                f"FAIL-CLOSED: rule '{rule.rule_id}' references unknown source '{rule.source_id}'"
            )

    # Verify all asset_ids are unique
    asset_ids = [a.get("asset_id") for a in assets]
    if len(asset_ids) != len(set(asset_ids)):
        duplicates = [aid for aid in asset_ids if asset_ids.count(aid) > 1]
        raise SystemExit(
            f"FAIL-CLOSED: duplicate asset IDs found: {set(duplicates)}"
        )

    # Verify asset coordinates are in valid CRS
    valid_crs = {"EPSG:28992", "EPSG:4326"}
    for asset in assets:
        crs = asset.get("coordinates", {}).get("crs", "")
        if crs not in valid_crs:
            raise SystemExit(
                f"FAIL-CLOSED: asset '{asset.get('asset_id')}' has invalid CRS '{crs}'; "
                f"supported: {valid_crs}"
            )

    # Perform verification
    # FAIL-CLOSED: applicability_verified is ALWAYS False until
    # independent BAG identity, building date, use-class, exemption,
    # transitional provision, and water-authority evidence is provided.
    # Municipality name matching is a geographic screening candidate
    # only — it is NOT independent applicability verification.
    verifications: list[AssetVerification] = []
    for asset in assets:
        applicability_verified = False
        municipality = asset.get("municipality", "")
        applicability_reason = (
            f"Municipality screening candidate: {municipality}. "
            f"Applicability NOT independently verified — requires BAG "
            f"identity, building date, use-class, exemption, and "
            f"water-authority evidence."
        )

        verification = verify_asset(
            asset=asset,
            rules=rules,
            applicability_verified=applicability_verified,
            applicability_reason=applicability_reason,
        )
        verifications.append(verification)

    # Build the pack (without checksum — added last)
    now_iso = datetime.now(timezone.utc).isoformat()

    content_dict = {
        "pack_id": PACK_ID,
        "schema_version": SCHEMA_VERSION,
        "pack_version": PACK_VERSION,
        "regulatory_domain": "hemelwater",
        "jurisdiction": {
            "level": jurisdiction.level,
            "name": jurisdiction.name,
            "authority_ids": list(jurisdiction.authority_ids),
        },
        "classification": {
            "evidence_class": classification.evidence_class,
            "customer_data_status": classification.customer_data_status,
            "production_eligible": classification.production_eligible,
            "decision_use_approved": classification.decision_use_approved,
        },
        "source_registry": [
            {
                "source_id": s.source_id,
                "authority": s.authority,
                "title": s.title,
                "reference_url": s.reference_url,
                "content_hash": s.content_hash,
                "source_checksums_verified": s.source_checksums_verified,
                "status": s.status,
                "effective_date": s.effective_date,
                "publication_reference": s.publication_reference,
            }
            for s in sources
        ],
        "official_source_artifacts": [
            {
                "source_id": a.source_id,
                "authority": a.authority,
                "official_publication_id": a.official_publication_id,
                "title": a.title,
                "source_url": a.source_url,
                "retrieved_at": a.retrieved_at,
                "effective_from": a.effective_from,
                "effective_until": a.effective_until,
                "mime_type": a.mime_type,
                "byte_length": a.byte_length,
                "artifact_sha256": a.artifact_sha256,
                "source_checksums_verified": a.source_checksums_verified,
                "status": a.status,
                "notes": a.notes,
            }
            for a in artifacts.values()
        ],
        "threshold_provenance": [
            {
                "rule_id": p.rule_id,
                "source_id": p.source_id,
                "official_artifact_sha256": p.official_artifact_sha256,
                "article_reference": p.article_reference,
                "paragraph_reference": p.paragraph_reference,
                "lid_reference": p.lid_reference,
                "page_reference": p.page_reference,
                "effective_date": p.effective_date,
                "provenance_verified": p.provenance_verified,
            }
            for p in provenance
        ],
        "regulatory_rules": [
            {
                "rule_id": r.rule_id,
                "source_id": r.source_id,
                "rule_type": r.rule_type,
                "parameter_name": r.parameter_name,
                "threshold_value": r.threshold_value,
                "threshold_unit": r.threshold_unit,
                "comparison": r.comparison,
                "applicability_filter": {
                    k: v
                    for k, v in {
                        "municipality": r.applicability_filter.municipality,
                        "use_class": r.applicability_filter.use_class,
                        "water_authority": r.applicability_filter.water_authority,
                        "min_built_area_m2": r.applicability_filter.min_built_area_m2,
                        "max_built_area_m2": r.applicability_filter.max_built_area_m2,
                    }.items()
                    if v is not None
                },
                "publication_section": r.publication_section,
                "publication_page": r.publication_page,
                "effective_date": r.effective_date,
                "threshold_source_verified": r.threshold_source_verified,
            }
            for r in rules
        ],
        "asset_verifications": [v.to_dict() for v in verifications],
        "generator_version": GENERATOR_VERSION,
        "deterministic_seed": deterministic_seed,
    }

    # Compute checksum over content (excluding volatile envelope fields)
    # Canonicalization contract: checksum covers everything EXCEPT
    # checksum, generated_at, and envelope_timestamp
    checksum = _compute_checksum(content_dict)
    content_dict["checksum"] = {
        "content_sha256": checksum,
        "algorithm": "SHA-256",
    }
    # Volatile envelope fields — NOT part of checksum
    content_dict["generated_at"] = now_iso

    # Atomic write
    if output_path:
        out = Path(output_path)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(_deterministic_json(content_dict), encoding="utf-8")
        tmp.replace(out)

    return content_dict


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Amsterdam Hemelwater Regulatory Evidence Pack",
    )
    parser.add_argument(
        "--portfolio",
        required=True,
        help="Path to portfolio JSON file (array of assets)",
    )
    parser.add_argument(
        "--output",
        default="data/regulatory_evidence_packs/nl-amsterdam-hemelwater-2026-v1.json",
        help="Output path for the evidence pack",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Deterministic seed for documentation",
    )
    args = parser.parse_args()

    portfolio_path = Path(args.portfolio)
    if not portfolio_path.exists():
        print(f"ERROR: portfolio not found: {portfolio_path}", file=sys.stderr)
        sys.exit(1)

    with open(portfolio_path, encoding="utf-8") as f:
        portfolio = json.load(f)

    # Portfolio may be a GeoJSON FeatureCollection or a plain array
    if isinstance(portfolio, dict) and "features" in portfolio:
        assets = [feat["properties"] for feat in portfolio["features"]]
        # Inject coordinates from geometry — fail-closed for non-Point
        for feat, asset in zip(portfolio["features"], assets):
            geom = feat.get("geometry", {})
            geom_type = geom.get("type", "")
            if geom_type != "Point":
                raise SystemExit(
                    f"FAIL-CLOSED: asset '{asset.get('asset_id')}' has "
                    f"geometry type '{geom_type}'; only Point geometry "
                    f"is supported.  For Polygon/MultiPolygon (e.g. BAG "
                    f"footprints), extract centroid or reference point "
                    f"before passing to this generator."
                )
            coords = geom.get("coordinates", [0, 0])
            asset["coordinates"] = {
                "crs": "EPSG:4326",
                "x": coords[0],
                "y": coords[1],
            }
    elif isinstance(portfolio, list):
        assets = portfolio
    else:
        print("ERROR: portfolio must be a JSON array or GeoJSON FeatureCollection", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(assets)} assets from {portfolio_path}")

    pack = build_evidence_pack(
        assets=assets,
        deterministic_seed=args.seed,
        output_path=args.output,
    )

    # Summary
    verifications = pack["asset_verifications"]
    threshold_satisfied = sum(1 for v in verifications if v["overall_status"] == "threshold_satisfied")
    threshold_not_satisfied = sum(1 for v in verifications if v["overall_status"] == "threshold_not_satisfied")
    applicability_unverified = sum(1 for v in verifications if v["overall_status"] == "applicability_unverified")
    source_unverified = sum(1 for v in verifications if v["overall_status"] == "source_unverified")
    partial = sum(1 for v in verifications if v["overall_status"] == "partial")
    not_applicable = sum(1 for v in verifications if v["overall_status"] == "not_applicable")
    insufficient = sum(1 for v in verifications if v["overall_status"] == "insufficient_data")

    print(f"\nPack: {pack['pack_id']}")
    print(f"Checksum: {pack['checksum']['content_sha256']}")
    print(f"\nVerification results:")
    print(f"  Threshold satisfied:       {threshold_satisfied}")
    print(f"  Threshold not satisfied:   {threshold_not_satisfied}")
    print(f"  Applicability unverified:  {applicability_unverified}")
    print(f"  Source unverified:         {source_unverified}")
    print(f"  Partial:                   {partial}")
    print(f"  Not applicable:            {not_applicable}")
    print(f"  Insufficient data:         {insufficient}")
    print(f"\nOfficial source artifacts: {len(pack['official_source_artifacts'])}")
    print(f"Threshold provenance records: {len(pack['threshold_provenance'])}")
    print(f"\nOutput: {args.output}")


if __name__ == "__main__":
    main()

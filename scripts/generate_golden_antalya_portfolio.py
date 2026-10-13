#!/usr/bin/env python3
"""Generate Antalya golden portfolio GeoJSON + CI regression baseline.

Synthetic assets on real Antalya-area geographies; fictional values only.
Re-run when methodology intentionally changes, then commit both artefacts.

  PYTHONPATH=. python scripts/generate_golden_antalya_portfolio.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.adaptation.evidence import ADAPTATION_EVIDENCE_METHODOLOGY_VERSION  # noqa: E402
from app.loss.damage_curves import DAMAGE_CURVES_VERSION  # noqa: E402
from app.loss.expected_loss import EXPECTED_LOSS_METHODOLOGY_VERSION  # noqa: E402
from app.pipeline.contract import PipelineContext  # noqa: E402
from app.pipeline.stubs import StubFiveLayerPipeline  # noqa: E402
from app.portfolios.golden import (  # noqa: E402
    ANTALYA_BASELINE_PATH,
    ANTALYA_GEOJSON_PATH,
    GOLDEN_ANTALYA_ID,
    GOLDEN_ANTALYA_VALUATION_DATE,
    GOLDEN_DIR,
)
from app.schemas.five_layer import METHODOLOGY_VERSION as FIVE_LAYER_METHODOLOGY_VERSION  # noqa: E402
from app.schemas.portfolio import UniversalAsset  # noqa: E402
from app.schemas.portfolio_demo import METHODOLOGY_DOCUMENT_VERSION  # noqa: E402
from app.services.audit_trail import AppendOnlyAuditTrail  # noqa: E402

# Real district / corridor centroids (WGS84) — Antalya metro + tourism coast.
_CLUSTERS: list[tuple[str, float, float, str, str]] = [
    # name, lat, lon, building_type, use_class
    ("kaleici", 36.8841, 30.7056, "hotel", "tourism"),
    ("muratpasa", 36.8905, 30.7133, "apartment", "residential"),
    ("konyaalti", 36.8620, 30.6370, "apartment", "residential"),
    ("konyaalti_beach", 36.8550, 30.6200, "hotel", "tourism"),
    ("lara", 36.8510, 30.7900, "hotel", "tourism"),
    ("kundu", 36.8480, 30.8200, "hotel", "tourism"),
    ("kepez", 36.9250, 30.7200, "apartment", "residential"),
    ("aksu", 36.9500, 30.8500, "retail", "commercial"),
    ("dosemealti", 37.0200, 30.6000, "office", "commercial"),
    ("belek", 36.8620, 31.0550, "hotel", "tourism"),
    ("serik", 36.9167, 31.1000, "apartment", "residential"),
    ("manavgat_west", 36.7865, 31.3000, "hotel", "tourism"),
]


def _jitter(lat: float, lon: float, seed: str, meters: float = 900.0) -> tuple[float, float]:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    u = int(digest[:8], 16) / 0xFFFFFFFF
    v = int(digest[8:16], 16) / 0xFFFFFFFF
    # Approx degrees at Antalya latitude.
    dlat = (meters / 111_320.0) * (u * 2 - 1)
    dlon = (meters / (111_320.0 * math.cos(math.radians(lat)))) * (v * 2 - 1)
    return round(lat + dlat, 6), round(lon + dlon, 6)


def _fictional_value(seed: str, building_type: str) -> float:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    unit = int(digest[:8], 16) / 0xFFFFFFFF
    bases = {
        "hotel": (3_500_000, 18_000_000),
        "apartment": (800_000, 4_500_000),
        "office": (1_200_000, 6_000_000),
        "retail": (900_000, 3_500_000),
    }
    lo, hi = bases.get(building_type, (1_000_000, 5_000_000))
    return round(lo + unit * (hi - lo), 2)


def build_assets(n: int = 100) -> list[UniversalAsset]:
    assets: list[UniversalAsset] = []
    for i in range(n):
        cluster = _CLUSTERS[i % len(_CLUSTERS)]
        name, base_lat, base_lon, building, use = cluster
        seed = f"antalya-v1-{i:03d}-{name}"
        lat, lon = _jitter(base_lat, base_lon, seed)
        year = 1985 + (int(hashlib.sha256(seed.encode()).hexdigest()[16:18], 16) % 36)
        floors = 2 + (int(hashlib.sha256(seed.encode()).hexdigest()[18:20], 16) % 12)
        assets.append(
            UniversalAsset(
                asset_id=f"ANT-G-{i:03d}",
                latitude=lat,
                longitude=lon,
                address=f"Synthetic {name.replace('_', ' ').title()} parcel {i:03d}, Antalya",
                asset_value=_fictional_value(seed, building),
                building_type=building,
                use_class=use,
                construction_year=year,
                floors=floors,
                insurance_coverage=round(_fictional_value(seed + "-ins", building) * 0.6, 2),
                ltv=round(0.45 + (i % 40) / 100.0, 2),
                loan_id=f"SYN-LN-{i:03d}",
            )
        )
    return assets


def assets_to_geojson(assets: list[UniversalAsset]) -> dict:
    features = []
    for a in assets:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [a.longitude, a.latitude],
                },
                "properties": {
                    "asset_id": a.asset_id,
                    "address": a.address,
                    "asset_value": a.asset_value,
                    "building_type": a.building_type,
                    "use_class": a.use_class,
                    "construction_year": a.construction_year,
                    "floors": a.floors,
                    "insurance_coverage": a.insurance_coverage,
                    "ltv": a.ltv,
                    "loan_id": a.loan_id,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "properties": {
            "portfolio_id": GOLDEN_ANTALYA_ID,
            "market": "TR-Antalya",
            "synthetic": True,
            "disclaimer": (
                "Fictional assets on real geographies for demo/CI only. "
                "No real customer or personal data."
            ),
            "valuation_date": GOLDEN_ANTALYA_VALUATION_DATE.isoformat(),
            "asset_count": len(assets),
        },
        "features": features,
    }


def compute_baseline(assets: list[UniversalAsset]) -> dict:
    trail = AppendOnlyAuditTrail()
    pipeline = StubFiveLayerPipeline(trail=trail)
    per_asset: list[dict] = []
    eals: list[float] = []
    scores: list[float] = []
    recommendations: dict[str, int] = {}

    for asset in assets:
        ctx = PipelineContext(
            asset=asset,
            valuation_date=GOLDEN_ANTALYA_VALUATION_DATE,
            parameters={"golden_portfolio": GOLDEN_ANTALYA_ID},
        )
        result = pipeline.run(ctx)
        eal = result.financial_translation.eal_absolute
        score = result.financial_translation.risk_score
        rec = result.adaptation_evidence.recommended_measure_id or "none"
        eals.append(eal)
        scores.append(score)
        recommendations[rec] = recommendations.get(rec, 0) + 1
        per_asset.append(
            {
                "asset_id": asset.asset_id,
                "eal_absolute": eal,
                "risk_score": score,
                "recommended_measure_id": rec,
                "scenario_eal_2030": result.financial_translation.scenario_deltas.get("2030"),
                "scenario_eal_2050": result.financial_translation.scenario_deltas.get("2050"),
            }
        )

    return {
        "portfolio_id": GOLDEN_ANTALYA_ID,
        "valuation_date": GOLDEN_ANTALYA_VALUATION_DATE.isoformat(),
        "asset_count": len(assets),
        "methodology": {
            "document": METHODOLOGY_DOCUMENT_VERSION,
            "five_layer": FIVE_LAYER_METHODOLOGY_VERSION,
            "expected_loss": EXPECTED_LOSS_METHODOLOGY_VERSION,
            "damage_curves": DAMAGE_CURVES_VERSION,
            "adaptation_evidence": ADAPTATION_EVIDENCE_METHODOLOGY_VERSION,
            "pipeline_contract": FIVE_LAYER_METHODOLOGY_VERSION,
        },
        "aggregates": {
            "eal_sum": round(sum(eals), 2),
            "eal_mean": round(sum(eals) / len(eals), 2),
            "risk_score_mean": round(sum(scores) / len(scores), 4),
            "recommended_measure_counts": dict(sorted(recommendations.items())),
        },
        "assets": per_asset,
        # Relative tolerance for aggregate drift; per-asset EAL compared exactly
        # after rounding to 2 decimals (same as engine output).
        "tolerances": {
            "eal_sum_rel": 0.0,
            "eal_mean_rel": 0.0,
            "risk_score_mean_abs": 0.0,
            "per_asset_eal_abs": 0.0,
        },
    }


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    assets = build_assets(100)
    assert len(assets) == 100
    geojson = assets_to_geojson(assets)
    ANTALYA_GEOJSON_PATH.write_text(json.dumps(geojson, indent=2) + "\n", encoding="utf-8")
    baseline = compute_baseline(assets)
    ANTALYA_BASELINE_PATH.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ANTALYA_GEOJSON_PATH} ({len(assets)} assets)")
    print(f"Wrote {ANTALYA_BASELINE_PATH}")
    print(f"eal_sum={baseline['aggregates']['eal_sum']} risk_mean={baseline['aggregates']['risk_score_mean']}")


if __name__ == "__main__":
    main()

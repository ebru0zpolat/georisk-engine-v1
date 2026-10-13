#!/usr/bin/env python3
"""Generate Rotterdam port/logistics golden portfolio GeoJSON + CI baseline.

Synthetic industrial/logistics collateral on real Rotterdam-port geographies;
fictional EUR values only. Same stub five-layer pipeline as Antalya — not pack-nl.

  PYTHONPATH=. python scripts/generate_golden_rotterdam_port_portfolio.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.adaptation.evidence import ADAPTATION_EVIDENCE_METHODOLOGY_VERSION  # noqa: E402
from app.loss.damage_curves import DAMAGE_CURVES_VERSION  # noqa: E402
from app.loss.expected_loss import EXPECTED_LOSS_METHODOLOGY_VERSION  # noqa: E402
from app.pipeline.contract import PipelineContext  # noqa: E402
from app.pipeline.stubs import StubFiveLayerPipeline  # noqa: E402
from app.portfolios.golden import (  # noqa: E402
    GOLDEN_DIR,
    GOLDEN_ROTTERDAM_PORT_ID,
    GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
    ROTTERDAM_PORT_BASELINE_PATH,
    ROTTERDAM_PORT_GEOJSON_PATH,
)
from app.schemas.five_layer import METHODOLOGY_VERSION as FIVE_LAYER_METHODOLOGY_VERSION  # noqa: E402
from app.schemas.portfolio import UniversalAsset  # noqa: E402
from app.schemas.portfolio_demo import METHODOLOGY_DOCUMENT_VERSION  # noqa: E402
from app.services.audit_trail import AppendOnlyAuditTrail  # noqa: E402

# Real Rotterdam harbour / logistics corridor centroids (WGS84).
_CLUSTERS: list[tuple[str, float, float, str, str]] = [
    # name, lat, lon, building_type, use_class
    ("maasvlakte", 51.9550, 4.0250, "port_terminal", "logistics"),
    ("europoort", 51.9200, 4.1500, "warehouse", "logistics"),
    ("botlek", 51.8800, 4.2800, "warehouse", "industrial"),
    ("pernis", 51.8850, 4.3800, "logistics_park", "logistics"),
    ("vondelingenplaat", 51.8900, 4.3500, "cold_storage", "logistics"),
    ("waalhaven", 51.8850, 4.4500, "warehouse", "logistics"),
    ("merwehaven", 51.9100, 4.4600, "office", "commercial"),
    ("rozenburg", 51.9050, 4.2500, "logistics_park", "logistics"),
    ("spijkenisse", 51.8500, 4.3300, "warehouse", "logistics"),
    ("rijnhaven", 51.9000, 4.4900, "office", "commercial"),
    ("emshaven_corridor", 51.8700, 4.4000, "port_terminal", "industrial"),
    ("dordrecht_hinterland", 51.8100, 4.6900, "warehouse", "logistics"),
]


def _jitter(lat: float, lon: float, seed: str, meters: float = 700.0) -> tuple[float, float]:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    u = int(digest[:8], 16) / 0xFFFFFFFF
    v = int(digest[8:16], 16) / 0xFFFFFFFF
    dlat = (meters / 111_320.0) * (u * 2 - 1)
    dlon = (meters / (111_320.0 * math.cos(math.radians(lat)))) * (v * 2 - 1)
    return round(lat + dlat, 6), round(lon + dlon, 6)


def _fictional_value(seed: str, building_type: str) -> float:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    unit = int(digest[:8], 16) / 0xFFFFFFFF
    bases = {
        "port_terminal": (8_000_000, 45_000_000),
        "warehouse": (2_500_000, 18_000_000),
        "logistics_park": (4_000_000, 28_000_000),
        "cold_storage": (3_000_000, 16_000_000),
        "office": (1_500_000, 9_000_000),
    }
    lo, hi = bases.get(building_type, (2_000_000, 12_000_000))
    return round(lo + unit * (hi - lo), 2)


def build_assets(n: int = 100) -> list[UniversalAsset]:
    assets: list[UniversalAsset] = []
    for i in range(n):
        cluster = _CLUSTERS[i % len(_CLUSTERS)]
        name, base_lat, base_lon, building, use = cluster
        seed = f"rotterdam-port-v1-{i:03d}-{name}"
        lat, lon = _jitter(base_lat, base_lon, seed)
        year = 1975 + (int(hashlib.sha256(seed.encode()).hexdigest()[16:18], 16) % 45)
        floors = 1 + (int(hashlib.sha256(seed.encode()).hexdigest()[18:20], 16) % 6)
        assets.append(
            UniversalAsset(
                asset_id=f"RTM-G-{i:03d}",
                latitude=lat,
                longitude=lon,
                address=f"Synthetic {name.replace('_', ' ').title()} parcel {i:03d}, Rotterdam",
                asset_value=_fictional_value(seed, building),
                building_type=building,
                use_class=use,
                construction_year=year,
                floors=floors,
                insurance_coverage=round(_fictional_value(seed + "-ins", building) * 0.55, 2),
                ltv=round(0.40 + (i % 45) / 100.0, 2),
                loan_id=f"SYN-RTM-LN-{i:03d}",
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
                    "currency": "EUR",
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
            "portfolio_id": GOLDEN_ROTTERDAM_PORT_ID,
            "market": "NL-Rotterdam-port",
            "currency": "EUR",
            "synthetic": True,
            "pack_note": (
                "Same global stub MDR / stub hazard pipeline as Antalya — "
                "not pack-nl calibrated (pack loader is Phase B)."
            ),
            "disclaimer": (
                "Fictional port/logistics collateral on real Rotterdam geographies "
                "for demo/CI geographic-generalisation only. No real customer data."
            ),
            "valuation_date": GOLDEN_ROTTERDAM_PORT_VALUATION_DATE.isoformat(),
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
            valuation_date=GOLDEN_ROTTERDAM_PORT_VALUATION_DATE,
            parameters={
                "golden_portfolio": GOLDEN_ROTTERDAM_PORT_ID,
                "future_pack_id": "pack-nl",
            },
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
        "portfolio_id": GOLDEN_ROTTERDAM_PORT_ID,
        "valuation_date": GOLDEN_ROTTERDAM_PORT_VALUATION_DATE.isoformat(),
        "currency": "EUR",
        "market": "NL-Rotterdam-port",
        "asset_count": len(assets),
        "methodology": {
            "document": METHODOLOGY_DOCUMENT_VERSION,
            "five_layer": FIVE_LAYER_METHODOLOGY_VERSION,
            "expected_loss": EXPECTED_LOSS_METHODOLOGY_VERSION,
            "damage_curves": DAMAGE_CURVES_VERSION,
            "adaptation_evidence": ADAPTATION_EVIDENCE_METHODOLOGY_VERSION,
            "pipeline_contract": FIVE_LAYER_METHODOLOGY_VERSION,
        },
        "honesty": {
            "synthetic": True,
            "pack_nl_calibrated": False,
            "same_stub_pipeline_as": "golden-antalya-v1",
        },
        "aggregates": {
            "eal_sum": round(sum(eals), 2),
            "eal_mean": round(sum(eals) / len(eals), 2),
            "risk_score_mean": round(sum(scores) / len(scores), 4),
            "recommended_measure_counts": dict(sorted(recommendations.items())),
        },
        "assets": per_asset,
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
    geojson = assets_to_geojson(assets)
    ROTTERDAM_PORT_GEOJSON_PATH.write_text(
        json.dumps(geojson, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {ROTTERDAM_PORT_GEOJSON_PATH} ({len(assets)} assets)")
    baseline = compute_baseline(assets)
    ROTTERDAM_PORT_BASELINE_PATH.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {ROTTERDAM_PORT_BASELINE_PATH}")
    agg = baseline["aggregates"]
    print(f"eal_sum={agg['eal_sum']} risk_mean={agg['risk_score_mean']}")


if __name__ == "__main__":
    main()

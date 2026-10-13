"""Real-data five-layer run for the Amsterdam controlled pilot.

Wires the **real** inputs the pilot already holds — sealed BAG identity/geometry
(``real_assets.load_pilot_assets``) and a sealed real hazard snapshot
(``hazard_snapshot``, ERA5 Tmax + Copernicus DEM) — through the country-agnostic
hazard modules and the **real** expected-loss engine (``run_five_layer``).

Honesty ledger for one run
--------------------------
| Layer            | Basis                                             |
|------------------|---------------------------------------------------|
| Hazard           | REAL — ERA5 95th-pct Tmax + Copernicus DEM elev.  |
| Exposure (where) | REAL — sealed BAG Adres→VBO→Pand identity/geometry|
| Exposure (value) | SYNTHETIC-INDICATIVE — floor area × labelled €/m² |
| Vulnerability    | Heuristic v0.1 (construction year / use class)    |
| Financial (EAL)  | REAL engine — expected-loss v0.3 over the above   |
| Damage curves    | SYNTHETIC-LABELLED — ``stub_global_mdr`` v0.1.x   |
| Adaptation       | Catalogue v0.1 (cost / avoided-loss ratios)       |

The single fabricated *number* the user cannot verify offline — asset monetary
value — is labelled everywhere and isolated to one function
(``indicative_asset_value_eur``). The hazard layer is genuinely real; the damage
curve is synthetic-but-labelled (explicitly permitted for a five-layer demo).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.hazards.extreme_heat import ExtremeHeatHazardModule
from app.hazards.flood import FloodHazardModule
from app.loss.damage_curves import DAMAGE_CURVES_VERSION
from app.loss.expected_loss import EXPECTED_LOSS_METHODOLOGY_VERSION
from app.nl_pilot.hazard_snapshot import SealedHazardSnapshot
from app.nl_pilot.real_assets import RealAmsterdamAsset, load_pilot_assets
from app.schemas.five_layer import (
    METHODOLOGY_VERSION as PIPELINE_METHODOLOGY_VERSION,
    FiveLayerResult,
    HazardComponent,
    HazardLayer,
)
from app.schemas.portfolio import UniversalAsset
from app.services.audit_trail import AppendOnlyAuditTrail, get_audit_trail
from app.services.five_layer_pipeline import run_five_layer

# Netherlands pilot valuation date — after the sealed climate window (no lookahead).
PILOT_VALUATION_DATE = date(2025, 1, 1)

VALUE_BASIS_ID = "synthetic_indicative_value_eur_per_m2_v0.1"

# Labelled indicative €/m² by mapped building type. SYNTHETIC — not a valuation.
# Replace with client-supplied collateral values or a licensed AVM in production.
_INDICATIVE_EUR_PER_M2: dict[str, float] = {
    "retail": 3500.0,
    "office": 3000.0,
    "industrial": 1500.0,
    "residential": 4000.0,
    "hotel": 4500.0,
    "other": 2500.0,
}

# BAG ``gebruiksdoel`` → (building_type for damage-curve selection, use_class label).
_GEBRUIKSDOEL_MAP: dict[str, tuple[str, str]] = {
    "winkelfunctie": ("retail", "commercial_retail"),
    "kantoorfunctie": ("office", "commercial_office"),
    "bijeenkomstfunctie": ("retail", "assembly"),
    "industriefunctie": ("industrial", "industrial"),
    "woonfunctie": ("residential", "residential"),
    "logiesfunctie": ("hotel", "accommodation"),
    "gezondheidszorgfunctie": ("office", "healthcare"),
    "onderwijsfunctie": ("office", "education"),
    "sportfunctie": ("retail", "sport"),
    "overige gebruiksfunctie": ("other", "other"),
}
_DEFAULT_BUILDING = ("office", "unknown")


def map_gebruiksdoel(gebruiksdoel: str) -> tuple[str, str]:
    """Map a Dutch BAG use function to (building_type, use_class)."""
    return _GEBRUIKSDOEL_MAP.get(gebruiksdoel.strip().lower(), _DEFAULT_BUILDING)


def floor_area_m2(asset: RealAmsterdamAsset) -> float:
    """Best-available real floor area: VBO ``oppervlakte`` or Pand footprint.

    Some VBO records carry placeholder areas (e.g. 1 m²); fall back to the
    sealed Pand footprint so the indicative value is not degenerate.
    """
    vbo = float(asset.oppervlakte_m2 or 0.0)
    pand = float(asset.pand_footprint_area_m2 or 0.0)
    return max(vbo, pand, 1.0)


def indicative_asset_value_eur(building_type: str, area_m2: float) -> float:
    """SYNTHETIC indicative value = floor area × labelled €/m². Not a valuation."""
    rate = _INDICATIVE_EUR_PER_M2.get(building_type, _INDICATIVE_EUR_PER_M2["other"])
    return round(max(area_m2, 1.0) * rate, 2)


def real_asset_to_universal(asset: RealAmsterdamAsset) -> tuple[UniversalAsset, dict[str, Any]]:
    """Convert a verified BAG asset to ``UniversalAsset`` with provenance notes."""
    building_type, use_class = map_gebruiksdoel(asset.gebruiksdoel)
    area = floor_area_m2(asset)
    value = indicative_asset_value_eur(building_type, area)
    universal = UniversalAsset(
        asset_id=asset.asset_id,
        address=asset.address,
        latitude=float(asset.coordinates_y),
        longitude=float(asset.coordinates_x),
        asset_value=value,
        building_type=building_type,
        use_class=use_class,
        construction_year=asset.bouwjaar or None,
    )
    provenance = {
        "asset_id": asset.asset_id,
        "bag_pand_id": asset.bag_pand_id,
        "bag_verblijfsobject_id": asset.bag_verblijfsobject_id,
        "gebruiksdoel": asset.gebruiksdoel,
        "building_type": building_type,
        "use_class": use_class,
        "floor_area_m2": round(area, 2),
        "asset_value_eur": value,
        "value_basis": VALUE_BASIS_ID,
        "identity_verified": asset.asset_identity_verified,
        "geometry_verified": asset.building_geometry_verified,
    }
    return universal, provenance


def build_real_hazard_layer(
    universal: UniversalAsset,
    snapshot: SealedHazardSnapshot,
    valuation_date: date,
) -> tuple[HazardLayer, dict[str, Any]]:
    """Compute the real flood + extreme-heat Hazard layer from the sealed snapshot."""
    flood = FloodHazardModule(raster=snapshot).evaluate(
        latitude=universal.latitude,
        longitude=universal.longitude,
        valuation_date=valuation_date,
    )
    heat = ExtremeHeatHazardModule(raster=snapshot).evaluate(
        latitude=universal.latitude,
        longitude=universal.longitude,
        valuation_date=valuation_date,
    )
    components = [
        HazardComponent(hazard_id="flood", intensity=flood.intensity),
        HazardComponent(hazard_id="extreme_heat", intensity=heat.intensity),
    ]
    composite = round(sum(c.intensity for c in components) / len(components), 6)
    data_versions = {
        **flood.data_versions,
        **heat.data_versions,
        **snapshot.data_versions(),
        "hazard_basis": "real_open_meteo_era5_dem",
    }
    hazard_layer = HazardLayer(
        components=components,
        composite_intensity=composite,
        data_versions=data_versions,
    )
    detail = {
        "flood_intensity": flood.intensity,
        "flood_score_0_100": flood.score_0_100,
        "elevation_m": flood.metadata.get("elevation_m"),
        "elevation_band": flood.metadata.get("elevation_band"),
        "extreme_heat_intensity": heat.intensity,
        "extreme_heat_score_0_100": heat.score_0_100,
        "p95_tmax_c": heat.metadata.get("temperature_c"),
        "composite_intensity": composite,
    }
    return hazard_layer, detail


def run_real_five_layer(
    *,
    snapshot: SealedHazardSnapshot,
    assets: list[RealAmsterdamAsset] | None = None,
    valuation_date: date = PILOT_VALUATION_DATE,
    trail: AppendOnlyAuditTrail | None = None,
) -> dict[str, Any]:
    """Run the real five-layer pipeline over the pilot assets; return an evidence bundle."""
    store = get_audit_trail() if trail is None else trail
    real_assets = assets if assets is not None else load_pilot_assets()

    rows: list[dict[str, Any]] = []
    total_value = 0.0
    total_eal = 0.0
    for asset in real_assets:
        universal, asset_prov = real_asset_to_universal(asset)
        hazard_layer, hazard_detail = build_real_hazard_layer(
            universal, snapshot, valuation_date
        )
        result: FiveLayerResult = run_five_layer(
            universal,
            valuation_date,
            trail=store,
            hazard=hazard_layer,
        )
        total_value += float(universal.asset_value)
        total_eal += float(result.financial.eal_absolute)
        rows.append(
            {
                **asset_prov,
                "latitude": universal.latitude,
                "longitude": universal.longitude,
                "hazard": hazard_detail,
                "eal_absolute": result.financial.eal_absolute,
                "eal_pct_of_value": result.financial.eal_pct_of_value,
                "risk_score": result.financial.risk_score,
                "insurability": result.financial.insurability,
                "recommended_measure_id": result.adaptation.recommended_measure_id,
                "residual_risk_score": result.adaptation.residual_risk_score,
                "audit_record_id": result.audit_record_id,
            }
        )

    weighted_pct = round((total_eal / total_value) * 100.0, 4) if total_value else 0.0
    return {
        "portfolio_id": "nl-amsterdam-real-pilot-v1",
        "valuation_date": valuation_date.isoformat(),
        "asset_count": len(rows),
        "data_provenance": {
            "hazard_snapshot": snapshot.provenance(),
            "exposure_source": "sealed BAG Adres→VBO→Pand (Kadaster/PDOK, Public Domain)",
        },
        "methodology": {
            "pipeline": PIPELINE_METHODOLOGY_VERSION,
            "expected_loss": EXPECTED_LOSS_METHODOLOGY_VERSION,
            "damage_curves": DAMAGE_CURVES_VERSION,
        },
        "honesty_labels": {
            "hazard_layer": (
                "REAL — ERA5 95th-pct daily Tmax (Open-Meteo/Copernicus) + "
                "Copernicus DEM GLO-90 elevation"
            ),
            "exposure_location": "REAL — sealed, hash-verified BAG identity + geometry",
            "asset_value": (
                f"SYNTHETIC-INDICATIVE — floor area × labelled €/m² ({VALUE_BASIS_ID}); "
                "replace with client collateral values"
            ),
            "damage_curves": (
                f"SYNTHETIC-LABELLED — stub_global_mdr {DAMAGE_CURVES_VERSION} "
                "(source: synthetic calibration)"
            ),
            "snapshot_kind": (
                "SYNTHETIC TEST FIXTURE — not real observations"
                if snapshot.synthetic
                else "SEALED REAL CAPTURE"
            ),
        },
        "portfolio_totals": {
            "total_indicative_value_eur": round(total_value, 2),
            "total_eal_absolute_eur": round(total_eal, 2),
            "weighted_eal_pct_of_value": weighted_pct,
        },
        "assets": rows,
    }


__all__ = [
    "PILOT_VALUATION_DATE",
    "VALUE_BASIS_ID",
    "build_real_hazard_layer",
    "floor_area_m2",
    "indicative_asset_value_eur",
    "map_gebruiksdoel",
    "real_asset_to_universal",
    "run_real_five_layer",
]

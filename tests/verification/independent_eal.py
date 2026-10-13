"""Independent EAL reimplementation for audit / CI verification.

MUST NOT import app.loss or app.services. Formula: METHODOLOGY.md (v0.3).
Update from that note — never by copying pipeline code. Stdlib only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_curves(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw, list(raw["curves"])


def select_curve(curves: list[dict[str, Any]], *, building_type: str, use_class: str, hazard_id: str) -> dict[str, Any]:
    bt, uc, hz = building_type.lower(), use_class.lower(), hazard_id.lower()
    best, best_score = None, -1
    for c in curves:
        c_hz, c_bt, c_uc = c["hazard_id"].lower(), c["building_type"].lower(), c.get("use_class", "*").lower()
        if c_hz not in (hz, "*") or c_bt not in (bt, "*") or c_uc not in (uc, "*"):
            continue
        score = (4 if c_hz == hz else 0) + (2 if c_bt == bt else 0) + (1 if c_uc == uc else 0)
        if score > best_score:
            best, best_score = c, score
    if best is None:
        raise ValueError(f"no curve for {building_type}/{use_class}/{hazard_id}")
    return best


def mdr(curve: dict[str, Any], intensity: float) -> float:
    """Full-precision MDR (no intermediate round)."""
    i = max(0.0, min(1.0, float(intensity)))
    return max(0.0, min(1.0, float(curve["scale"]) * (i ** float(curve["exponent"]))))


# --- v0.4 depth-damage (JRC) support -------------------------------------
_OCCUPANCY = {"residential": "residential", "apartment": "residential", "hotel": "commercial",
              "office": "commercial", "retail": "commercial", "commercial": "commercial",
              "industrial": "industrial", "other": "commercial"}


def select_depth_curve(dcurves: list[dict[str, Any]], occupancy: str) -> dict[str, Any]:
    """Select the occupancy curve (continent '*' default, matching the engine)."""
    for c in dcurves:
        if c["occupancy"].lower() == occupancy and str(c.get("continent", "*")).lower() == "*":
            return c
    raise ValueError(f"no depth curve for occupancy {occupancy}")


def dmg_at_depth(curve: dict[str, Any], depth: float) -> float:
    """Monotonic linear interpolation of damage fraction at a depth (full precision)."""
    pts, d = curve["points"], float(depth)
    if d <= pts[0]["depth_m"]:
        return float(pts[0]["damage_ratio"])
    if d >= pts[-1]["depth_m"]:
        return float(pts[-1]["damage_ratio"])
    for i in range(1, len(pts)):
        if d <= pts[i]["depth_m"]:
            p0, p1 = pts[i - 1], pts[i]
            f = (d - p0["depth_m"]) / (p1["depth_m"] - p0["depth_m"])
            return max(0.0, min(1.0, p0["damage_ratio"] + f * (p1["damage_ratio"] - p0["damage_ratio"])))
    return float(pts[-1]["damage_ratio"])


def eal_current(asset: dict[str, Any], intensities: dict[str, float], curves: list[dict[str, Any]],
                depths: dict[str, float] | None = None, depth_curves: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Current-climate EAL from first principles (methodology v0.3, or v0.4 hybrid).

    v0.4: a hazard with a supplied depth + depth_curves uses the JRC depth curve
    for its MDR; every other hazard, and all v0.3 records, use the power curve.
    Intermediates stay full precision; round only final EAL and display fields.
    """
    value = float(asset["asset_value"])
    vuln = max(0.05, float(asset.get("fragility_factor", 1.0)) * (1.0 - float(asset.get("adaptation_capacity_factor", 0.0))))
    s = sum(float(v) for v in intensities.values())
    steps: list[dict[str, Any]] = []
    survival = 1.0
    for hid, raw_i in intensities.items():
        intensity = float(raw_i)
        if depths and hid in depths and depth_curves:
            occ = _OCCUPANCY.get(str(asset["building_type"]).lower(), "commercial")
            dcurve = select_depth_curve(depth_curves, occ)
            ratio, curve_id, exp, scale = dmg_at_depth(dcurve, depths[hid]), dcurve["curve_id"], None, None
        else:
            curve = select_curve(curves, building_type=asset["building_type"], use_class=asset["use_class"], hazard_id=hid)
            ratio, curve_id, exp, scale = mdr(curve, intensity), curve["curve_id"], curve["exponent"], curve["scale"]
        share = (intensity / s) if s > 0 else 0.0
        notional = 0.0 if s <= 0 else value * ratio * vuln
        survival *= 1.0 - ratio
        steps.append({
            "hazard_id": hid, "intensity": intensity, "curve_id": curve_id,
            "exponent": exp, "scale": scale, "mdr": ratio,
            # Display-boundary rounding only:
            "attribution_share": round(share, 6), "loss": round(notional, 2),
            "formula": f"notional {value} × {ratio} × {vuln}",
        })
    if s <= 0:
        eal, combo = 0.0, 0.0
    else:
        combo = max(0.0, min(1.0, 1.0 - survival))
        eal = min(value, round(value * combo * vuln, 2))
    return {
        "asset_id": asset["asset_id"], "asset_value": value, "vulnerability": vuln,
        "intensity_sum": s, "combined_mdr": combo, "steps": steps,
        "eal_absolute": eal,
        "eal_pct_of_value": round((eal / value) * 100.0, 6) if value and eal else 0.0,
    }


def eal_from_trail(record: dict[str, Any], curves_path: str | Path,
                   depth_curves_path: str | Path | None = None) -> dict[str, Any]:
    meta, curves = load_curves(curves_path)
    depths = record["inputs"].get("depths")
    depth_curves = None
    if depth_curves_path is not None:
        depth_curves = json.loads(Path(depth_curves_path).read_text(encoding="utf-8"))["curves"]
    out = eal_current(
        record["inputs"]["asset"], record["inputs"]["hazards"]["current"], curves, depths, depth_curves
    )
    out.update({
        "catalogue_id": meta.get("catalogue_id"), "catalogue_version": meta.get("version"),
        "trail_record_id": record.get("record_id"), "trail_record_hash": record.get("record_hash"),
        "valuation_date": record.get("valuation_date"),
    })
    for key, label in (("horizon_2030", "2030"), ("horizon_2050", "2050")):
        horizon = record["inputs"]["hazards"].get(key) or {}
        if horizon:
            out[f"eal_{label}"] = eal_current(
                record["inputs"]["asset"], horizon, curves
            )["eal_absolute"]
    return out


__all__ = ["eal_current", "eal_from_trail", "load_curves", "mdr", "select_curve"]

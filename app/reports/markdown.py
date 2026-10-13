from app.schemas.industrial_verification import IndustrialVerificationRef
from app.schemas.risk import RiskScoreResponse

_DEFAULT_LINKED_AUDIT_NOTE = "(must equal score **Audit ID** below)"


def format_industrial_verification_markdown(
    iv: IndustrialVerificationRef | None,
    *,
    linked_audit_note: str = _DEFAULT_LINKED_AUDIT_NOTE,
) -> str:
    """Markdown block for ``## Industrial verification``; empty if ``iv`` is None."""
    if iv is None:
        return ""
    near = iv.nearest_primary_audit
    if near is not None:
        near_lines = f"""- Nearest Primary Audit AOI: **{near.facility_name_tr}** (`{near.facility_id}`) at **{near.distance_km} km**
"""
    else:
        near_lines = "- Nearest Primary Audit AOI: *no facility within configured match radius*\n"
    pipes = "\n".join(
        f"  - `{p.id}` — {p.label_tr} (`{p.methodology_doc}` → `{p.production_entrypoint}`)"
        for p in iv.pipelines
    )
    return f"""
## Industrial verification (bundled on same audit id)
- **Linked audit ID:** `{iv.linked_audit_id}` {linked_audit_note}
- **Risk model version:** {iv.risk_model_version}
{near_lines}
### Operational pipelines (reference)
{pipes}

*Disclaimer (TR):* {iv.disclaimer_tr}
"""


def build_markdown_report(result: RiskScoreResponse) -> str:
    g = result.gee_features
    ag_surface = ""
    if g.ndvi_mean is not None or g.soil_moisture_proxy is not None:
        ag_surface = f"""
### Agriculture surface proxies (current window)
- NDVI mean: {g.ndvi_mean if g.ndvi_mean is not None else '—'}
- Soil moisture proxy: {g.soil_moisture_proxy if g.soil_moisture_proxy is not None else '—'}
<i>Stub or satellite-derived; not a regulatory soil survey.</i>
"""
    baseline_block = ""
    gb = result.gee_baseline
    if gb is not None:
        nl = gb.night_lights
        nx = gb.no2
        baseline_block = f"""
## GEE baseline comparison
<i>Baseline is the configured multi-year climatological reference (default 30-year WMO 1991–2020).</i>
### Night lights (vs baseline)
- Current mean: {nl.current_mean}; baseline mean: {nl.baseline_mean}
- Absolute change: {nl.absolute_change}; percent change: {nl.percent_change}%
- z-score (placeholder): {nl.z_score}

### NO₂ (vs baseline)
- Current mean: {nx.current_mean}; baseline mean: {nx.baseline_mean}
- Absolute change: {nx.absolute_change}; percent change: {nx.percent_change}%
- z-score (placeholder): {nx.z_score}
"""
    return f"""# GeoRisk Engine Report

## Asset
- Name: {result.asset_name}
- Sector: {result.sector}
- Location: {result.latitude}, {result.longitude}
- Radius: {result.radius_km} km

## Overall Risk
- Score: {result.overall_score}/100
- Band: {result.risk_band}
- Data mode: {result.data_mode}{" (not production-eligible)" if not result.production_eligible else ""}

## Component Scores
- Industrial: {result.components.industrial}
- Pollution: {result.components.pollution}
- Land: {result.components.land}
- Ocean: {result.components.ocean}
- Agriculture: {result.components.agriculture}
- Sensitivity: {result.components.sensitivity}

## GEE features (current window)
*Versus default climatological baseline (30-year WMO 1991–2020 unless overridden in the request or via `CLIMATE_BASELINE_*`).*
- Night lights (mean): {g.night_lights_mean}
- NO₂ (mean): {g.no2_mean}
{ag_surface}{baseline_block}
## Key Flags
{chr(10).join(f"- {flag}" for flag in result.flags) if result.flags else "- None"}

## Interpretation
{result.interpretation}
{format_industrial_verification_markdown(
        result.industrial_verification,
        linked_audit_note=_DEFAULT_LINKED_AUDIT_NOTE,
    )}
## Audit
- Audit ID: {result.audit_id}
- Generated At: {result.generated_at}
"""

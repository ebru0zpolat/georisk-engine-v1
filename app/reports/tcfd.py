"""TCFD-aligned disclosure export.

Maps a ``RiskScoreResponse`` onto the four core pillars of the Task Force on
Climate-related Financial Disclosures (TCFD) recommendations: Governance,
Strategy, Risk Management, and Metrics & Targets.

This is a structured narrative export intended to sit alongside (not
replace) the existing audit-style risk report (``app.reports.markdown``).
"""

from app.schemas.risk import RiskScoreResponse

# Hazard-to-TCFD-category mapping used to group component scores under the
# "physical risk" sub-categories commonly referenced in TCFD climate-risk
# disclosures.
_PHYSICAL_RISK_LABELS: dict[str, str] = {
    "industrial": "Industrial activity / operational exposure",
    "pollution": "Pollution / emissions exposure",
    "land": "Land-use change exposure",
    "ocean": "Ocean / coastal exposure",
    "agriculture": "Agricultural / land productivity exposure",
    "sensitivity": "Ecological sensitivity exposure",
    "flood": "Flood hazard (acute physical risk)",
    "heat": "Heat stress hazard (chronic physical risk)",
}


def _component_rows(result: RiskScoreResponse) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for field, label in _PHYSICAL_RISK_LABELS.items():
        value = getattr(result.components, field, None)
        if value is not None:
            rows.append((label, value))
    return rows


def build_tcfd_report(result: RiskScoreResponse) -> str:
    """Render a TCFD-aligned markdown disclosure for ``result``.

    Structured under the four TCFD recommendation pillars: Governance,
    Strategy, Risk Management, and Metrics & Targets.
    """
    rows = _component_rows(result)
    metrics_table = "\n".join(f"| {label} | {score}/100 |" for label, score in rows)

    return f"""# TCFD-Aligned Climate Risk Disclosure

## Asset
- Name: {result.asset_name}
- Sector: {result.sector}
- Location: {result.latitude}, {result.longitude}
- Assessment radius: {result.radius_km} km
- Audit ID: {result.audit_id}
- Generated at: {result.generated_at}

## Governance
Climate-related risk for this asset is assessed through GeoRisk Engine's
automated, repeatable scoring pipeline (audit ID `{result.audit_id}`),
enabling consistent oversight of physical climate risk exposure across the
portfolio. Disclosure of this assessment should be reviewed by the entity's
designated body responsible for climate-related oversight (e.g. board
committee or equivalent).

## Strategy
The composite risk score of **{result.overall_score}/100** ({result.risk_band}
band) represents the asset's current physical climate and environmental risk
exposure. Material exposures identified below should inform resilience
planning, capital allocation, and scenario analysis for this asset over
short-, medium-, and long-term horizons.

### Identified risk flags
{chr(10).join(f"- {flag}" for flag in result.flags) if result.flags else "- None identified at current thresholds."}

### Interpretation
{result.interpretation}

## Risk Management
Physical risk exposure is assessed across the following categories, scored
0-100 (higher = greater exposure). These scores are produced by GeoRisk
Engine's risk model (audit ID `{result.audit_id}`) and should be integrated
into the entity's broader climate risk identification, assessment, and
management processes.

| Risk category | Score |
|---|---|
{metrics_table}

## Metrics & Targets
- **Composite risk score:** {result.overall_score}/100 ({result.risk_band})
- **Assessment methodology / model version:** see audit ID `{result.audit_id}`
  for the linked model version and methodology reference.

*This export is a structured input to support TCFD-aligned reporting and
does not constitute a complete TCFD disclosure on its own. Governance,
strategy, and target-setting narratives should be completed by the
disclosing entity.*
"""

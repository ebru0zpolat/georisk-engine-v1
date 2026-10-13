"""Current, deliberately conservative release manifest builder."""

from app.core.config import Settings
from app.schemas.release_manifest import ReleaseGateStates, ReleaseManifest


def build_release_manifest(settings: Settings) -> ReleaseManifest:
    """Describe the current release without inferring readiness from runtime config."""

    return ReleaseManifest(
        release_version=settings.georisk_version,
        commit_sha=settings.git_sha,
        geography="Netherlands",
        hazards=["flood", "extreme_heat"],
        asset_class="commercial_property_and_collateral",
        permitted_user_decision="analyst_prioritisation_for_deeper_assessment",
        source_versions={},
        model_versions={"risk_score": settings.risk_score_model_version},
        gates=ReleaseGateStates(),
        decision="demo_only",
        production_eligible=False,
        evidence_ids=[],
        approvals=[],
        limitations=[
            "Source and model readiness have not been approved for a named use case.",
            "Outputs are decision-support context and may include deterministic fixtures.",
            "Elevation or topographic context is not flood probability or loss evidence.",
        ],
        prohibited_uses=[
            "automated credit, underwriting, valuation, capital, or investment decisions",
            "engineering-grade flood certification",
            "validated EAL, downtime, or monetary-loss claims",
            "regulatory-compliance certification",
        ],
    )

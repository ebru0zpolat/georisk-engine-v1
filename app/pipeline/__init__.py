"""Five-layer pipeline contract (Phase A).

``Hazard → Exposure → Vulnerability → FinancialTranslation → AdaptationEvidence``
"""

from app.pipeline.contract import (
    LAYER_ORDER,
    AdaptationEvidence,
    AdaptationEvidenceResult,
    Exposure,
    ExposureResult,
    FinancialTranslation,
    FinancialTranslationResult,
    FiveLayerPipeline,
    FiveLayerPipelineResult,
    Hazard,
    HazardResult,
    PipelineContext,
    Vulnerability,
    VulnerabilityResult,
)

__all__ = [
    "LAYER_ORDER",
    "AdaptationEvidence",
    "AdaptationEvidenceResult",
    "Exposure",
    "ExposureResult",
    "FinancialTranslation",
    "FinancialTranslationResult",
    "FiveLayerPipeline",
    "FiveLayerPipelineResult",
    "Hazard",
    "HazardResult",
    "PipelineContext",
    "Vulnerability",
    "VulnerabilityResult",
]


def get_stub_pipeline(**kwargs):  # noqa: ANN003
    """Lazy import to avoid circular dependency with ``app.loss``."""
    from app.pipeline.stubs import StubFiveLayerPipeline

    return StubFiveLayerPipeline(**kwargs)

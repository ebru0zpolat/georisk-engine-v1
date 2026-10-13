"""Adaptation evidence layer — measure catalogue to avoided loss."""

from app.adaptation.catalogue import (
    ADAPTATION_CATALOGUE_VERSION,
    CatalogueMeasure,
    get_default_catalogue,
)
from app.adaptation.evidence import (
    ADAPTATION_EVIDENCE_METHODOLOGY_VERSION,
    AdaptationEvidenceOutput,
    CatalogueAdaptationEvidence,
    compute_adaptation_evidence,
)

__all__ = [
    "ADAPTATION_CATALOGUE_VERSION",
    "ADAPTATION_EVIDENCE_METHODOLOGY_VERSION",
    "AdaptationEvidenceOutput",
    "CatalogueAdaptationEvidence",
    "CatalogueMeasure",
    "compute_adaptation_evidence",
    "get_default_catalogue",
]

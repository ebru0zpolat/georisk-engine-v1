"""Industrial / ESG verification pointers bundled with risk ``audit_id`` (API product surface)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PipelineRef(BaseModel):
    """Stable id for a mühürlü operasyonel hat; doküman ve üretim girişi."""

    id: str
    label_tr: str
    methodology_doc: str = Field(
        ...,
        description="Repo-relative doc path for clients to deep-link internally.",
    )
    production_entrypoint: str = Field(
        ...,
        description="Script or API entry used to produce sealed artefacts.",
    )


class NearestPrimaryAudit(BaseModel):
    """AOI eşlemesi: istek koordinatına en yakın Primary Audit tesisi (varsa)."""

    facility_id: str
    facility_name_tr: str
    distance_km: float


class IndustrialVerificationRef(BaseModel):
    """Risk yanıtı ile aynı ``audit_id`` altında birleştirilen operasyonel doğrulama meta verisi."""

    schema_version: str = "1.0"
    linked_audit_id: str = Field(
        ...,
        description="``RiskScoreResponse.audit_id`` ile aynı; rapor ve iç loglarda çapraz referans.",
    )
    risk_model_version: str
    nearest_primary_audit: NearestPrimaryAudit | None = None
    pipelines: list[PipelineRef] = Field(default_factory=list)
    disclaimer_tr: str = (
        "Uydu proxy özetidir; düzenleyici uygunluk veya resmi beyan yerine geçmez. "
        "Mühürlü rapor üretimi ayrı betiklerle yapılır; bu nesne ürün entegrasyonu için referans taşır."
    )

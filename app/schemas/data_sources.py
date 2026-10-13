from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.data_source_registry import DataSourceEntry, list_data_sources

DataSourceTier = Literal["production", "audit", "roadmap"]
LoiStatus = Literal["active", "intent", "planned"]
DeliveryPlane = Literal["gee", "cds_zarr", "gee_audit", "stub"]
ValidationCheckStatus = Literal["pass", "fail", "warn", "skip"]
DeliveryMode = Literal["live", "fallback", "mock", "stub"]


class DataSourceOut(BaseModel):
    id: str
    name: str
    provider: str
    tier: DataSourceTier
    delivery: DeliveryPlane
    dataset_id: str | None
    bands: list[str]
    units: dict[str, str]
    fallback_policy: str
    standards_ref: str | None
    loi_status: LoiStatus
    connector_module: str | None
    feature_keys: list[str] = Field(default_factory=list)

    @classmethod
    def from_entry(cls, entry: DataSourceEntry) -> DataSourceOut:
        return cls(
            id=entry.id,
            name=entry.name,
            provider=entry.provider,
            tier=entry.tier,
            delivery=entry.delivery,
            dataset_id=entry.dataset_id,
            bands=list(entry.bands),
            units=dict(entry.units),
            fallback_policy=entry.fallback_policy,
            standards_ref=entry.standards_ref,
            loi_status=entry.loi_status,
            connector_module=entry.connector_module,
            feature_keys=list(entry.feature_keys),
        )


class DataSourcesListResponse(BaseModel):
    count: int
    sources: list[DataSourceOut]
    package_doc: str = "docs/georisk_data_source_loi_package.html"
    summary_doc: str = "docs/georisk_data_source_loi_summary.md"
    validation_package_doc: str = "docs/GeoRisk_DataSource_Validation_Package.docx"


class ValidationCheckOut(BaseModel):
    id: str
    description: str
    criterion: str
    status: ValidationCheckStatus
    detail: str


class SourceValidationOut(BaseModel):
    source_id: str
    delivery_mode: DeliveryMode
    passed: bool
    checks: list[ValidationCheckOut]


class DataSourceValidationReport(BaseModel):
    package_version: str = "v1.0"
    package_doc: str = "docs/GeoRisk_DataSource_Validation_Package.docx"
    summary_doc: str = "docs/georisk_data_source_validation_summary.md"
    registry_module: str = "app/core/data_source_registry.py"
    validation_module: str = "app/core/data_source_validation.py"
    source_count: int
    passed_count: int
    sources: list[SourceValidationOut]


def build_data_sources_response(*, tier: DataSourceTier | None = None) -> DataSourcesListResponse:
    entries = list_data_sources(tier=tier)
    return DataSourcesListResponse(
        count=len(entries),
        sources=[DataSourceOut.from_entry(e) for e in entries],
    )

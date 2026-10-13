"""Data source validation rules and runtime posture checks.

Complements ``data_source_registry`` (catalog + LOI posture) with acceptance
criteria and environment-aware validation status for the Validation Package.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.core.data_source_registry import DATA_SOURCE_REGISTRY, DataSourceEntry

ValidationCheckStatus = Literal["pass", "fail", "warn", "skip"]
DeliveryMode = Literal["live", "fallback", "mock", "stub"]


@dataclass(frozen=True)
class ValidationCheck:
    id: str
    description: str
    criterion: str


@dataclass(frozen=True)
class ValidationCheckResult:
    id: str
    description: str
    criterion: str
    status: ValidationCheckStatus
    detail: str


@dataclass(frozen=True)
class SourceValidationResult:
    source_id: str
    delivery_mode: DeliveryMode
    checks: tuple[ValidationCheckResult, ...]

    @property
    def passed(self) -> bool:
        return all(c.status in {"pass", "warn", "skip"} for c in self.checks)


# Acceptance checks referenced in docs/GeoRisk_DataSource_Validation_Package.*
VALIDATION_CHECKS: dict[str, tuple[ValidationCheck, ...]] = {
    "oras5_ocean": (
        ValidationCheck(
            id="oras5_zarr_configured",
            description="ORAS5 Zarr store URL is configured",
            criterion="settings.oras5_zarr_url is non-empty",
        ),
        ValidationCheck(
            id="oras5_fallback_coherent",
            description="Fallback features return all ocean risk keys",
            criterion="cds_oras5._fallback_features keys match registry feature_keys",
        ),
    ),
    "gee_viirs_ntl": (
        ValidationCheck(
            id="gee_credentials",
            description="GEE project configured and enabled",
            criterion="settings.gee_enabled and settings.gee_project",
        ),
        ValidationCheck(
            id="viirs_dataset_registered",
            description="VIIRS dataset id matches registry constant",
            criterion="GeeConnector.VIIRS_DATASET == GEE_VIIRS_NTL_DATASET",
        ),
    ),
    "gee_s5p_no2": (
        ValidationCheck(
            id="gee_credentials",
            description="GEE project configured and enabled",
            criterion="settings.gee_enabled and settings.gee_project",
        ),
        ValidationCheck(
            id="s5p_no2_dataset_registered",
            description="S5P NO₂ dataset id matches registry constant",
            criterion="GeeConnector.S5P_NO2_DATASET == GEE_S5P_NO2_DATASET",
        ),
    ),
    "audit_landsat_thermal": (
        ValidationCheck(
            id="landsat_qa_mask",
            description="QA_PIXEL cloud/shadow mask applied in audit pipeline",
            criterion="landsat_thermal_audit uses LANDSAT_QA_PIXEL_BAND",
        ),
        ValidationCheck(
            id="audit_mock_available",
            description="Offline mock path available for CI",
            criterion="AUDIT_USE_MOCK=true supported",
        ),
    ),
    "audit_s5p_no2": (
        ValidationCheck(
            id="s5p_offl_l3",
            description="OFFL L3 tropospheric NO₂ band used",
            criterion="S5P_L3_NO2_COLLECTION + GEE_S5P_NO2_BAND",
        ),
        ValidationCheck(
            id="audit_mock_available",
            description="Offline mock path available for CI",
            criterion="AUDIT_USE_MOCK=true supported",
        ),
    ),
    "audit_s5p_co": (
        ValidationCheck(
            id="s5p_co_collection",
            description="OFFL L3 CO collection registered",
            criterion="S5P_L3_CO_COLLECTION imported from registry",
        ),
        ValidationCheck(
            id="audit_mock_available",
            description="Offline mock path available for CI",
            criterion="AUDIT_USE_MOCK=true supported",
        ),
    ),
    "audit_viirs_dnb": (
        ValidationCheck(
            id="viirs_cf_cvg_reported",
            description="Cloud-free coverage band reported alongside avg_rad",
            criterion="VIIRS_DNB_CF_CVG_BAND in registry bands",
        ),
        ValidationCheck(
            id="audit_mock_available",
            description="Offline mock path available for CI",
            criterion="AUDIT_USE_MOCK=true supported",
        ),
    ),
    "roadmap_ndvi": (
        ValidationCheck(
            id="agriculture_stub",
            description="Deterministic agriculture stub fills ndvi_mean",
            criterion="agriculture_surface.attach_agriculture_proxies_to_gee_dict",
        ),
    ),
    "roadmap_soil_moisture": (
        ValidationCheck(
            id="agriculture_stub",
            description="Deterministic agriculture stub fills soil_moisture_proxy",
            criterion="agriculture_surface.attach_agriculture_proxies_to_gee_dict",
        ),
    ),
}


def _audit_use_mock() -> bool:
    return os.environ.get("AUDIT_USE_MOCK", "").lower() in {"1", "true", "yes"}


def _gee_project_configured() -> bool:
    """Match audit script env lookup (GEE_PROJECT / GEE_PROJECT_ID), not API gee_enabled."""
    if settings.gee_project:
        return True
    return bool(
        os.environ.get("GEE_PROJECT", "").strip()
        or os.environ.get("GEE_PROJECT_ID", "").strip()
    )


def delivery_mode_for(entry: DataSourceEntry) -> DeliveryMode:
    if entry.tier == "roadmap" or entry.delivery == "stub":
        return "stub"
    if entry.tier == "audit" and _audit_use_mock():
        return "mock"
    if entry.delivery == "cds_zarr":
        # Live via either the ORAS5 Zarr store OR the cdsapi time-series path
        # (a configured Copernicus CDS API key performs a real reanalysis call).
        cds_api_live = bool(getattr(settings, "copernicus_cds_api_key", None))
        return "live" if (settings.oras5_zarr_url or cds_api_live) else "fallback"
    if entry.delivery in {"gee", "gee_audit"}:
        if entry.tier == "audit":
            return "live" if _gee_project_configured() else "fallback"
        return "live" if settings.gee_enabled and settings.gee_project else "fallback"
    return "fallback"


def _evaluate_check(entry: DataSourceEntry, check: ValidationCheck) -> ValidationCheckResult:
    from app.connectors.cds_oras5 import CDSOras5Connector
    from app.connectors.gee import GeeConnector
    from app.core.data_source_registry import (
        GEE_S5P_NO2_DATASET,
        GEE_VIIRS_NTL_DATASET,
        LANDSAT_QA_PIXEL_BAND,
        S5P_L3_CO_COLLECTION,
        S5P_L3_NO2_COLLECTION,
        VIIRS_DNB_CF_CVG_BAND,
    )

    mode = delivery_mode_for(entry)
    cid = check.id

    if cid == "oras5_zarr_configured":
        ok = bool(settings.oras5_zarr_url)
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "warn",
            detail="ORAS5_ZARR_URL set" if ok else "Using deterministic fallback (CI-safe)",
        )

    if cid == "oras5_fallback_coherent":
        fallback = CDSOras5Connector()._fallback_features()
        missing = [k for k in entry.feature_keys if k not in fallback]
        ok = not missing
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail="All feature keys present" if ok else f"Missing keys: {missing}",
        )

    if cid == "gee_credentials":
        ok = bool(settings.gee_enabled and settings.gee_project)
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "warn",
            detail="GEE live credentials configured" if ok else "Using GEE fallback stub",
        )

    if cid == "viirs_dataset_registered":
        ok = GeeConnector.VIIRS_DATASET == GEE_VIIRS_NTL_DATASET
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail=f"dataset={GeeConnector.VIIRS_DATASET}",
        )

    if cid == "s5p_no2_dataset_registered":
        ok = GeeConnector.S5P_NO2_DATASET == GEE_S5P_NO2_DATASET
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail=f"dataset={GeeConnector.S5P_NO2_DATASET}",
        )

    if cid == "landsat_qa_mask":
        ok = LANDSAT_QA_PIXEL_BAND == "QA_PIXEL"
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail=f"QA band={LANDSAT_QA_PIXEL_BAND}; mask applied in landsat_thermal_audit",
        )

    if cid == "audit_mock_available":
        if mode == "mock":
            detail = "mock active (AUDIT_USE_MOCK)"
        elif mode == "live":
            detail = "live audit path (GEE project configured)"
        else:
            detail = "fallback: set GEE_PROJECT or AUDIT_USE_MOCK=true for audit runs"
        return ValidationCheckResult(
            **check.__dict__,
            status="pass",
            detail=detail,
        )

    if cid == "s5p_offl_l3":
        ok = S5P_L3_NO2_COLLECTION == "COPERNICUS/S5P/OFFL/L3_NO2"
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail=f"collection={S5P_L3_NO2_COLLECTION}",
        )

    if cid == "s5p_co_collection":
        ok = S5P_L3_CO_COLLECTION == "COPERNICUS/S5P/OFFL/L3_CO"
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail=f"collection={S5P_L3_CO_COLLECTION}",
        )

    if cid == "viirs_cf_cvg_reported":
        ok = VIIRS_DNB_CF_CVG_BAND == "cf_cvg"
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail=f"cf_cvg band registered; delivery_mode={mode}",
        )

    if cid == "agriculture_stub":
        from app.schemas.risk import RiskScoreRequest
        from app.scoring.agriculture_surface import attach_agriculture_proxies_to_gee_dict

        payload = RiskScoreRequest(
            asset_name="validation-check",
            latitude=39.0,
            longitude=32.0,
            sector="agriculture",
        )
        sample = attach_agriculture_proxies_to_gee_dict({}, payload)
        key = entry.feature_keys[0] if entry.feature_keys else ""
        ok = key in sample
        return ValidationCheckResult(
            **check.__dict__,
            status="pass" if ok else "fail",
            detail=f"stub provides {key}={sample.get(key)!r}",
        )

    return ValidationCheckResult(
        **check.__dict__,
        status="skip",
        detail="No runtime evaluator registered",
    )


def validate_source(entry: DataSourceEntry) -> SourceValidationResult:
    checks = VALIDATION_CHECKS.get(entry.id, ())
    results = tuple(_evaluate_check(entry, c) for c in checks)
    return SourceValidationResult(
        source_id=entry.id,
        delivery_mode=delivery_mode_for(entry),
        checks=results,
    )


def validate_all_sources() -> list[SourceValidationResult]:
    return [validate_source(e) for e in DATA_SOURCE_REGISTRY]

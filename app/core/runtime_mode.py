"""Environment classification for connector stubs vs live sources.

Test / local / demo may use labelled ``_fallback_features`` stubs.
``APP_ENV=production`` must fail closed: missing Zarr / live-source
configuration is rejected at startup, and request-time stub paths raise
``CONNECTOR_STUB_PROHIBITED`` instead of returning synthetic features.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from app.core import error_codes as codes
from app.core.exceptions import GeoRiskApiError

if TYPE_CHECKING:
    from app.core.config import Settings

DataMode = Literal["live", "stub"]

STUB_PERMITTED_ENVS = frozenset({"local", "dev", "test", "demo"})
PRODUCTION_ENVS = frozenset({"production", "prod"})

_ARCO_HOST_MARKERS = ("arco.datastores.ecmwf.int", "cds.climate.copernicus.eu")


class ConnectorStubProhibitedError(GeoRiskApiError):
    """Production refused a deterministic connector stub."""

    def __init__(self, source: str, reason: str, app_env: str) -> None:
        super().__init__(
            code=codes.CONNECTOR_STUB_PROHIBITED,
            message=(
                "Connector stubs are prohibited in production. "
                "Configure live sources or set APP_ENV=demo for labelled demo scoring."
            ),
            status_code=503,
            details={"source": source, "reason": reason, "app_env": app_env},
        )


class ProductionLiveSourceError(RuntimeError):
    """Production process refused to start without required live sources."""


def normalize_app_env(value: str | None) -> str:
    """Map aliases; unknown values fail closed as production."""
    env = (value or "").strip().lower()
    if env in {"local"}:
        return "local"
    if env in {"dev", "development"}:
        return "dev"
    if env in {"test", "testing", "ci"}:
        return "test"
    if env in {"demo"}:
        return "demo"
    if env in PRODUCTION_ENVS:
        return "production"
    if not env:
        return "local"
    return "production"


def allows_connector_stubs(settings: Settings | None = None) -> bool:
    cfg = settings or _settings()
    return normalize_app_env(cfg.app_env) in STUB_PERMITTED_ENVS


def is_production(settings: Settings | None = None) -> bool:
    cfg = settings or _settings()
    return normalize_app_env(cfg.app_env) == "production"


def oras5_uses_stub(settings: Settings | None = None) -> bool:
    """Mirror ``CDSOras5Connector.fetch_features``: Zarr, else CDS API, else stub.

    A CDS key without a Zarr URL still reads live from the CDS API, so it must
    not be labelled ``stub``. Production startup stays stricter than this
    predicate on purpose — ``missing_production_live_sources`` requires the Zarr
    URL, so a CDS-key-only deployment is refused rather than served over the
    queued retrieval path.
    """
    cfg = settings or _settings()
    return not (cfg.oras5_zarr_url or cfg.copernicus_cds_api_key)


def gee_uses_stub(settings: Settings | None = None) -> bool:
    cfg = settings or _settings()
    return not (cfg.gee_enabled and cfg.gee_project)


def connector_data_mode(settings: Settings | None = None) -> DataMode:
    if oras5_uses_stub(settings) or gee_uses_stub(settings):
        return "stub"
    return "live"


def production_eligible_for_response(settings: Settings | None = None) -> bool:
    """Whether a score may be presented as production asset-risk scoring.

    Stub responses are never eligible. Live connector reads also stay false
    while ORAS5 evidence gates remain open — this helper does not claim
    calibrated production scoring.
    """
    del settings
    return False


def refuse_connector_stub_if_production(*, source: str, reason: str) -> None:
    cfg = _settings()
    if allows_connector_stubs(cfg):
        return
    raise ConnectorStubProhibitedError(
        source=source,
        reason=reason,
        app_env=normalize_app_env(cfg.app_env),
    )


def _zarr_requires_cds_key(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in _ARCO_HOST_MARKERS)


def missing_production_live_sources(settings: Settings | None = None) -> list[str]:
    """Names of required live-source settings absent in production."""
    cfg = settings or _settings()
    if allows_connector_stubs(cfg):
        return []
    missing: list[str] = []
    if not cfg.oras5_zarr_url:
        missing.append("ORAS5_ZARR_URL")
    elif _zarr_requires_cds_key(cfg.oras5_zarr_url) and not cfg.copernicus_cds_api_key:
        missing.append("CDSAPI_KEY")
    if not cfg.gee_enabled:
        missing.append("GEE_ENABLED")
    if not cfg.gee_project:
        missing.append("GEE_PROJECT")
    return missing


def assert_production_live_sources(settings: Settings | None = None) -> None:
    """Refuse production startup when required Zarr / live sources are missing."""
    cfg = settings or _settings()
    missing = missing_production_live_sources(cfg)
    if not missing:
        return
    raise ProductionLiveSourceError(
        "APP_ENV=production requires live connector configuration; "
        f"missing {', '.join(missing)}. "
        "Set APP_ENV=demo for labelled stub scoring, or configure the live sources."
    )


def _settings():
    from app.core.config import settings

    return settings

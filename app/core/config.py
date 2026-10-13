from datetime import date
import json
import re
from typing import Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored fullmatch pattern for HTTPS Vercel preview / deployment hosts only.
# Starlette CORSMiddleware uses ``re.fullmatch`` against this string.
_DEFAULT_CORS_ORIGIN_REGEX = r"https://([a-zA-Z0-9-]+\.)+vercel\.app"


#: Deployed runtimes: the API-key gate cannot be switched off, and portfolio
#: runs require the database audit store (no file-trail fallback).
DEPLOYED_RUNTIMES = frozenset({"production", "demo"})
_AUTH_ALWAYS_REQUIRED_ENVS = DEPLOYED_RUNTIMES


class Settings(BaseSettings):
    #: ``local`` / ``dev`` / ``test`` / ``demo`` permit labelled connector stubs.
    #: ``production`` rejects missing Zarr / live-source configuration at startup.
    app_env: str = "local"
    app_name: str = "GeoRisk Engine"
    api_prefix: str = "/v1"
    #: Deployed commit SHA for health provenance. Prefer explicit ``GIT_SHA``;
    #: otherwise Railway's ``RAILWAY_GIT_COMMIT_SHA``. Local/dev defaults to
    #: ``unknown`` — never invent a SHA.
    git_sha: str = Field(
        default="unknown",
        validation_alias=AliasChoices("GIT_SHA", "RAILWAY_GIT_COMMIT_SHA", "git_sha"),
    )
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://georiskengine.com",
        "https://www.georiskengine.com",
    ]
    #: Regex for Vercel preview hosts (``None`` disables regex matching).
    cors_origin_regex: str | None = Field(
        default=_DEFAULT_CORS_ORIGIN_REGEX,
        validation_alias=AliasChoices("CORS_ORIGIN_REGEX", "cors_origin_regex"),
    )

    #: Historical ORAS5 ARCO Zarr store (1958–2014) from CDS "Analysis Ready
    #: Data". Unset → deterministic stub features. Both stores require a Bearer
    #: token sent automatically from ``copernicus_cds_api_key`` (CDSAPI_KEY).
    oras5_zarr_url: str | None = None
    #: Operational ORAS5 ARCO Zarr store (2015–present). When set, point windows
    #: spanning the 2015 boundary are served from both stores and merged.
    oras5_zarr_operational_url: str | None = None
    #: Wall-clock budget (seconds) for one synchronous ORAS5 Zarr store read.
    #: A slow/unreachable store degrades to ``DATA_SOURCE_UNAVAILABLE`` (503) at
    #: this bound instead of hanging the request worker indefinitely.
    oras5_fetch_timeout_seconds: float = 8.0

    @field_validator("git_sha", mode="before")
    @classmethod
    def normalize_git_sha(cls, v: object) -> str:
        if v is None:
            return "unknown"
        s = str(v).strip()
        if not s or s.lower() in {"none", "null", "unknown"}:
            return "unknown"
        return s

    @field_validator("oras5_zarr_url", "oras5_zarr_operational_url", mode="before")
    @classmethod
    def normalize_oras5_zarr_url(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if s.startswith("<") or "paste-zarr-store-url" in s.lower():
            return None
        return s

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                except json.JSONDecodeError as exc:
                    raise ValueError("CORS_ORIGINS must be a JSON array or comma-separated list") from exc
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON value must be an array")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in s.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return []

    @field_validator("cors_origin_regex", mode="before")
    @classmethod
    def normalize_cors_origin_regex(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in {"none", "off", "false"}:
            return None
        # Force full-string semantics even if the env omits anchors; Starlette
        # already fullmatches, but anchoring documents intent and rejects
        # accidental substring patterns.
        if not s.startswith("^"):
            s = f"^{s}"
        if not s.endswith("$"):
            s = f"{s}$"
        try:
            re.compile(s)
        except re.error as exc:
            raise ValueError(f"Invalid CORS_ORIGIN_REGEX: {exc}") from exc
        return s

    gee_project: str | None = None
    gee_enabled: bool = False
    #: Earth Engine service-account JSON key (raw JSON string). When set, GEE
    #: initialises with this credential instead of ADC / `earthengine authenticate`.
    gee_service_account_json: str | None = None

    @field_validator("gee_service_account_json", mode="before")
    @classmethod
    def normalize_gee_service_account_json(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in {"none", "changeme", "your-service-account-json"}:
            return None
        return s

    #: Default climatological reference when request omits ``baseline_*`` (WMO standard 30-year period).
    climate_baseline_start: date = date(1991, 1, 1)
    climate_baseline_end: date = date(2020, 12, 31)

    #: Version label surfaced in demo audit metadata (override via ``RISK_SCORE_MODEL_VERSION``).
    risk_score_model_version: str = "risk-score-v0.1"

    #: Opt-in for ``POST /v1/risk/data-centre/assess``. Default off. Enabling the
    #: endpoint never releases downtime hours or monetary/EAL outputs.
    data_centre_assess_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "DATA_CENTRE_ASSESS_ENABLED",
            "data_centre_assess_enabled",
        ),
    )

    #: GeoRisk engine version stamped onto validation evidence records (override via ``GEORISK_VERSION``).
    georisk_version: str = "georisk-engine-v0.1"

    #: Max distance (km) to attach ``nearest_primary_audit`` when ``include_industrial_verification_ref`` is true.
    industrial_verification_max_match_km: float = 40.0

    #: Per-asset scoring timeout for synchronous ``POST /v1/risk/batch`` (row-level ``TIMEOUT_ERROR``).
    risk_score_row_timeout_seconds: float = 5.0

    #: Max raw upload bytes for ``POST /v1/portfolio/upload`` (CSV / GeoJSON).
    portfolio_upload_max_bytes: int = Field(
        default=2_000_000,
        validation_alias=AliasChoices(
            "PORTFOLIO_UPLOAD_MAX_BYTES",
            "portfolio_upload_max_bytes",
        ),
        ge=1,
    )

    #: Require an API key on every ``/v1`` route except the health and
    #: release-manifest probes. Tri-state: ``None`` (default) follows the
    #: runtime — off in local/dev/test, always on in the deployed runtimes
    #: (production and demo). ``true`` forces it on anywhere; ``false`` is
    #: ignored in a deployed runtime (fail closed). Demo is deployed: its routes
    #: write to the shared audit trail and snapshot store, so ``APP_ENV=demo``
    #: alone must not open them. Implements the tenancy gate (MVP plan WP-1).
    api_key_required: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("API_KEY_REQUIRED", "api_key_required"),
    )
    #: Secret mixed into the API-key hash (HMAC-SHA256) so a leaked database
    #: dump cannot be replayed without the pepper. Unset → plain SHA-256 of
    #: the token (dev/test only; production should set it).
    api_key_pepper: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_KEY_PEPPER", "api_key_pepper"),
    )

    @field_validator("api_key_pepper", mode="before")
    @classmethod
    def normalize_api_key_pepper(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in {"none", "changeme", "your-pepper"}:
            return None
        return s

    @property
    def auth_required(self) -> bool:
        """Whether the API-key gate is enforced for this process."""
        from app.core.runtime_mode import normalize_app_env

        if normalize_app_env(self.app_env) in _AUTH_ALWAYS_REQUIRED_ENVS:
            return True
        return bool(self.api_key_required)

    #: Public-API rate limit (POST/PUT/PATCH/DELETE) per client IP, fixed window.
    rate_limit_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("RATE_LIMIT_ENABLED", "rate_limit_enabled"),
    )
    rate_limit_requests: int = Field(
        default=60,
        validation_alias=AliasChoices("RATE_LIMIT_REQUESTS", "rate_limit_requests"),
        ge=1,
    )
    rate_limit_window_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "RATE_LIMIT_WINDOW_SECONDS",
            "rate_limit_window_seconds",
        ),
        gt=0,
    )

    #: Exact peer IPs allowed to supply ``X-Forwarded-For`` for rate-limit keys.
    #: Does **not** enable ``X-Real-IP`` trust — see ``trust_x_real_ip``.
    trusted_proxy_ips: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("TRUSTED_PROXY_IPS", "trusted_proxy_ips"),
    )
    #: When true, treat RFC1918/loopback/link-local/RFC6598-CGNAT *peers* as
    #: trusted proxies (Railway edge uses ``100.64.0.0/10``). Forwarded hops are
    #: still validated from the right; public clients cannot spoof by sending
    #: ``X-Forwarded-For`` on a direct connection. Does **not** enable
    #: ``X-Real-IP`` — that requires ``TRUST_X_REAL_IP`` separately.
    trust_private_proxy_peers: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "TRUST_PRIVATE_PROXY_PEERS",
            "trust_private_proxy_peers",
        ),
    )
    #: When true **and** the TCP peer is trusted, honour the rightmost
    #: ``X-Real-IP`` token for rate-limit identity. Default false: many proxies
    #: sanitize XFF but forward client ``X-Real-IP`` unchanged. Enable only
    #: after confirming the edge overwrites or strips inbound client
    #: ``X-Real-IP`` (Railway: set alongside ``TRUST_PRIVATE_PROXY_PEERS`` if
    #: the platform is verified to set ``X-Real-IP`` to the connecting client).
    trust_x_real_ip: bool = Field(
        default=False,
        validation_alias=AliasChoices("TRUST_X_REAL_IP", "trust_x_real_ip"),
    )

    @field_validator("trusted_proxy_ips", mode="before")
    @classmethod
    def parse_trusted_proxy_ips(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                parsed = json.loads(s)
                if not isinstance(parsed, list):
                    raise ValueError("TRUSTED_PROXY_IPS JSON value must be an array")
                return [str(ip).strip() for ip in parsed if str(ip).strip()]
            return [part.strip() for part in s.split(",") if part.strip()]
        if isinstance(v, list):
            return [str(ip).strip() for ip in v if str(ip).strip()]
        return []

    #: Async SQLAlchemy URL for persisted case management (GEO-72).
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in {"none", "changeme"}:
            return None
        return s

    #: Where asset snapshots live (WP-2). ``memory`` = process-memory test
    #: fixture; ``db`` = the ``asset_snapshots`` table via
    #: ``app.storage.snapshot_repository.SqlAlchemySnapshotBackend``. Unset →
    #: ``db`` when ``DATABASE_URL`` is configured, else ``memory`` (see
    #: :attr:`effective_snapshot_store_backend`), so a deployment with a
    #: database does not silently keep snapshots in process memory.
    snapshot_store_backend: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SNAPSHOT_STORE_BACKEND", "snapshot_store_backend"),
    )

    @field_validator("snapshot_store_backend", mode="before")
    @classmethod
    def normalize_snapshot_store_backend(cls, v: object) -> str | None:
        if v is None or not str(v).strip():
            return None
        s = str(v).strip().lower()
        if s not in {"memory", "db"}:
            raise ValueError("SNAPSHOT_STORE_BACKEND must be 'memory' or 'db'")
        return s

    @property
    def effective_snapshot_store_backend(self) -> str:
        """The snapshot backend in force: explicit setting, else ``db`` with a database."""
        if self.snapshot_store_backend is not None:
            return self.snapshot_store_backend
        return "db" if self.database_url else "memory"

    #: Redis URL enabling the production async batch plane (Celery broker/backend +
    #: shared task status store). Unset → in-process BackgroundTasks PoC path.
    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL", "redis_url"),
    )

    @field_validator("redis_url", mode="before")
    @classmethod
    def normalize_redis_url(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in {"none", "changeme"}:
            return None
        return s

    #: Optional geocoder for ``POST /v1/risk/preview`` free-text addresses (``nominatim`` only).
    georisk_geocoder: str | None = None
    georisk_geocoder_timeout_seconds: float = 5.0
    georisk_geocoder_user_agent: str = "GeoRiskEngine/0.1 (preview-scorecard)"

    #: Copernicus CDS API key for ERA5 / Sentinel-5P raster access (GEO-191) and
    #: the cdsapi ORAS5 time-series path.
    copernicus_cds_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("COPERNICUS_CDS_API_KEY", "CDSAPI_KEY", "copernicus_cds_api_key"),
    )
    #: Copernicus CDS API base URL for the cdsapi ORAS5 time-series path.
    copernicus_cds_url: str = Field(
        default="https://cds.climate.copernicus.eu/api",
        validation_alias=AliasChoices("COPERNICUS_CDS_URL", "CDSAPI_URL", "copernicus_cds_url"),
    )

    @field_validator("copernicus_cds_api_key", mode="before")
    @classmethod
    def normalize_copernicus_cds_api_key(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in {"your-cds-api-key", "none", "changeme"}:
            return None
        return s

    @model_validator(mode="after")
    def climate_baseline_window(self) -> Self:
        if self.climate_baseline_end < self.climate_baseline_start:
            raise ValueError("climate_baseline_end must be on or after climate_baseline_start")
        return self

    @field_validator("georisk_geocoder", mode="before")
    @classmethod
    def normalize_georisk_geocoder(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s or s in {"none", "off", "false"}:
            return None
        if s != "nominatim":
            raise ValueError("georisk_geocoder must be 'nominatim' when set")
        return s

    @field_validator("gee_project", mode="before")
    @classmethod
    def normalize_gee_project(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env_field(cls, v: object) -> str:
        from app.core.runtime_mode import normalize_app_env

        if v is None:
            return "local"
        return normalize_app_env(str(v))

    @property
    def allows_connector_stubs(self) -> bool:
        from app.core.runtime_mode import allows_connector_stubs

        return allows_connector_stubs(self)

    @property
    def is_production(self) -> bool:
        from app.core.runtime_mode import is_production

        return is_production(self)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

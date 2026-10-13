import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.security import DEFAULT_ORGANISATION_ID
from app.db.base import Base

#: Portable JSON column: plain JSON everywhere, JSONB on PostgreSQL.
PortableJSON = JSON().with_variant(JSONB, "postgresql")


class CaseModel(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: Owning organisation. Defaults to the single-organisation bucket so pre-tenancy rows
    #: and the local (auth-disabled) suite keep working.
    organisation_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, server_default=DEFAULT_ORGANISATION_ID, default=DEFAULT_ORGANISATION_ID
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    asset_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)
    triage_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transitions: Mapped[list["CaseTransitionModel"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )


class CaseTransitionModel(Base):
    __tablename__ = "case_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(32), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    case: Mapped[CaseModel] = relationship(back_populates="transitions")


class OrganisationModel(Base):
    """An organisation that owns keys, cases and persisted state.

    Introduced with the tenancy work so ``organisation_id`` on the other tables
    refers to a real row. Only an identity and a human label are modelled here;
    membership, roles and billing are out of scope for the MVP.
    """

    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApiKeyModel(Base):
    """Hashed API credential bound to an organisation.

    Only the digest is stored — the plaintext is shown once, at creation, and
    never persisted (``app.core.security.hash_api_key``). A row is usable while
    ``revoked_at`` is null and (if set) ``expires_at`` is in the future.
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    #: Granted scope strings (see ``app.core.security.SCOPES``). JSON array.
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssetSnapshotModel(Base):
    """Persisted asset snapshot (WP-2).

    Replaces the process-memory ``_store`` dict in
    ``app.services.asset_snapshot_store`` so a scored asset survives a restart.
    ``organisation_id`` is the owning organisation (the value carried on
    ``Principal.organisation_id``); it defaults to the single-organisation bucket.
    """

    __tablename__ = "asset_snapshots"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, server_default=DEFAULT_ORGANISATION_ID, default=DEFAULT_ORGANISATION_ID
    )
    asset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, nullable=False)
    sector: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    components: Mapped[dict] = mapped_column(PortableJSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    data_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_geometry_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    uses_connector_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditTrailRecordModel(Base):
    """One hash-chained append-only audit record (WP-2).

    The chain is per organisation: ``(organisation_id, prev_hash)`` is unique so
    at most one successor exists for any link, and ``record_hash`` is globally
    unique. The hash is computed over ``payload`` by
    ``app.services.audit_trail.compute_record_hash`` — the same function the file
    backend uses, so both stores agree byte-for-byte.
    """

    __tablename__ = "audit_trail_records"
    __table_args__ = (
        UniqueConstraint("organisation_id", "prev_hash", name="uq_audit_trail_org_prev_hash"),
    )

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, server_default=DEFAULT_ORGANISATION_ID, default=DEFAULT_ORGANISATION_ID
    )
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    payload: Mapped[dict] = mapped_column(PortableJSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RunModel(Base):
    """One portfolio run (WP-2) — the auditable record of what was computed.

    ``analyzed_count`` + ``excluded_count`` partition the uploaded rows; the
    per-row exclusion reasons are carried in the run result (WP-6/WP-8).
    """

    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, server_default=DEFAULT_ORGANISATION_ID, default=DEFAULT_ORGANISATION_ID
    )
    portfolio_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    valuation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    analyzed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

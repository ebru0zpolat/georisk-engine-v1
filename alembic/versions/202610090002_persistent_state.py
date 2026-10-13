"""Persistent state: asset_snapshots, audit_trail_records, runs (WP-2).

Portable across SQLite (dev/test) and PostgreSQL (prod): JSON columns use
``JSON`` with a ``JSONB`` variant on PostgreSQL, timestamps use ``now()`` which
compiles to ``CURRENT_TIMESTAMP`` on SQLite.
"""

revision = "202610090002"
down_revision = "202610090001"
branch_labels = None
depends_on = None


def _json_column():
    from sqlalchemy import JSON
    from sqlalchemy.dialects import postgresql

    return JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op

    op.create_table(
        "asset_snapshots",
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("organisation_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("asset_name", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("radius_km", sa.Float(), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("components", _json_column(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("data_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("asset_geometry_hash", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("uses_connector_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index("ix_asset_snapshots_organisation_id", "asset_snapshots", ["organisation_id"], unique=False)

    op.create_table(
        "audit_trail_records",
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("organisation_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", _json_column(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint("organisation_id", "prev_hash", name="uq_audit_trail_org_prev_hash"),
        sa.UniqueConstraint("record_hash", name="uq_audit_trail_record_hash"),
    )
    op.create_index("ix_audit_trail_records_organisation_id", "audit_trail_records", ["organisation_id"], unique=False)

    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("organisation_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("portfolio_id", sa.String(length=64), nullable=True),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("analyzed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("excluded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_runs_organisation_id", "runs", ["organisation_id"], unique=False)
    op.create_index("ix_runs_portfolio_id", "runs", ["portfolio_id"], unique=False)


def downgrade() -> None:
    from alembic import op

    op.drop_index("ix_runs_portfolio_id", table_name="runs")
    op.drop_index("ix_runs_organisation_id", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_audit_trail_records_organisation_id", table_name="audit_trail_records")
    op.drop_table("audit_trail_records")
    op.drop_index("ix_asset_snapshots_organisation_id", table_name="asset_snapshots")
    op.drop_table("asset_snapshots")

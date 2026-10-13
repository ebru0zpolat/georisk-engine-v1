"""Case management tables for GEO-72 (Supabase / PostgreSQL)."""

revision = "202607040001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    op.create_table(
        "cases",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("asset_id", sa.String(length=100), nullable=True),
        sa.Column("asset_name", sa.String(length=200), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("assigned_to", sa.String(length=120), nullable=True),
        sa.Column(
            "tags",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("triage_note", sa.Text(), nullable=True),
        sa.Column("escalation_note", sa.Text(), nullable=True),
        sa.Column("close_resolution", sa.Text(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("anomaly_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cases_asset_id", "cases", ["asset_id"], unique=False)
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)

    op.create_table(
        "case_transitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("triggered_by", sa.String(length=32), nullable=False, server_default="MANUAL"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_transitions_case_id", "case_transitions", ["case_id"], unique=False)


def downgrade() -> None:
    from alembic import op

    op.drop_index("ix_case_transitions_case_id", table_name="case_transitions")
    op.drop_table("case_transitions")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_asset_id", table_name="cases")
    op.drop_table("cases")

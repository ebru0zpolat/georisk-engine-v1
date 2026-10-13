"""API keys and organisation ownership (WP-1: identity and tenancy)."""

revision = "202610090001"
down_revision = "202607040001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    op.create_table(
        "organisations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    organisations = sa.table(
        "organisations",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(organisations, [{"id": "default", "name": "Default organisation"}])

    op.add_column(
        "cases",
        sa.Column(
            "organisation_id",
            sa.String(length=64),
            nullable=False,
            server_default="default",
        ),
    )
    op.create_index("ix_cases_organisation_id", "cases", ["organisation_id"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("organisation_id", sa.String(length=64), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_organisation_id", "api_keys", ["organisation_id"], unique=False)


def downgrade() -> None:
    from alembic import op

    op.drop_index("ix_api_keys_organisation_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_cases_organisation_id", table_name="cases")
    op.drop_column("cases", "organisation_id")
    op.drop_table("organisations")

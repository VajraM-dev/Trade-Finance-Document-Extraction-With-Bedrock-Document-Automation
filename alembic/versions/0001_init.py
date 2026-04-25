"""init

Revision ID: 0001
Revises:
Create Date: 2026-04-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", CITEXT, nullable=False, unique=True),
        sa.Column("email", CITEXT, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="customer"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("key_lookup_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("key_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("last_four", sa.String(4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])

    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", UUID(as_uuid=True)),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("s3_input_uri", sa.Text(), nullable=False),
        sa.Column("s3_output_prefix", sa.Text(), nullable=False),
        sa.Column("bda_invocation_arn", sa.Text()),
        sa.Column("matched_blueprint", sa.String(64)),
        sa.Column("pages_processed", sa.Integer()),
        sa.Column("blueprint_field_count", sa.Integer()),
        sa.Column("cost_usd", sa.Numeric(10, 4)),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("extracted_fields", JSONB),
        sa.Column("raw_bda_output", JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
    )
    op.create_index("ix_jobs_user_created", "jobs", ["user_id", "created_at"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created", "jobs", ["created_at"])
    op.create_index(
        "ix_jobs_extracted_gin", "jobs", ["extracted_fields"], postgresql_using="gin"
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", UUID(as_uuid=True)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_user_id", UUID(as_uuid=True)),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip", INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_action", "audit_log", ["action"])
    op.create_index("ix_audit_created", "audit_log", ["created_at"])

    op.execute(
        """
        CREATE OR REPLACE VIEW v_user_usage_daily AS
        SELECT user_id,
               date_trunc('day', created_at) AS day,
               COUNT(*) AS jobs,
               COALESCE(SUM(pages_processed), 0) AS pages,
               COALESCE(SUM(cost_usd), 0) AS cost_usd
        FROM jobs
        WHERE status = 'success'
        GROUP BY user_id, date_trunc('day', created_at);
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW v_user_usage_monthly AS
        SELECT user_id,
               date_trunc('month', created_at) AS month,
               COUNT(*) AS jobs,
               COALESCE(SUM(pages_processed), 0) AS pages,
               COALESCE(SUM(cost_usd), 0) AS cost_usd
        FROM jobs
        WHERE status = 'success'
        GROUP BY user_id, date_trunc('month', created_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_user_usage_monthly")
    op.execute("DROP VIEW IF EXISTS v_user_usage_daily")
    op.drop_table("audit_log")
    op.drop_table("jobs")
    op.drop_table("api_keys")
    op.drop_table("users")

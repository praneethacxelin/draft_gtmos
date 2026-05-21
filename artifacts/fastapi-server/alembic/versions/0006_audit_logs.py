"""Add audit_logs table.

Stores every external API call and every data-change event so the user
can inspect the full journey of their strategy data.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_audit_logs"
down_revision = "0005_admin_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    if not inspect(bind).has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=True),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("service", sa.String(), nullable=True),
            sa.Column("strategy_id", sa.String(), nullable=True),
            sa.Column("strategy_name", sa.String(), nullable=True),
            sa.Column("http_method", sa.String(), nullable=True),
            sa.Column("endpoint_url", sa.Text(), nullable=True),
            sa.Column("request_params", postgresql.JSONB(), nullable=True),
            sa.Column("response_status", sa.Integer(), nullable=True),
            sa.Column("response_summary", postgresql.JSONB(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("curl_command", sa.Text(), nullable=True),
            sa.Column("is_live", sa.Boolean(), nullable=True, server_default=sa.text("false")),
            sa.Column("entity_type", sa.String(), nullable=True),
            sa.Column("entity_id", sa.String(), nullable=True),
            sa.Column("change_field", sa.String(), nullable=True),
            sa.Column("change_before", postgresql.JSONB(), nullable=True),
            sa.Column("change_after", postgresql.JSONB(), nullable=True),
            sa.Column("actor", sa.String(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_occurred_at ON audit_logs (occurred_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_strategy_id ON audit_logs (strategy_id)")


def downgrade() -> None:
    op.drop_index("ix_audit_logs_strategy_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_occurred_at", table_name="audit_logs")
    op.drop_table("audit_logs")

"""Ensure all strategy columns exist regardless of migration history.

The ``0001_initial`` migration uses ``Base.metadata.create_all()`` which
skips tables that already exist. This means columns added to the SQLAlchemy
model AFTER the table was first created (discovery_data, roi_json,
last_signal_scan, daily_signal_summary) are silently missing on databases
that were created before those columns were added.

This migration explicitly adds each column with IF NOT EXISTS guards so it is
safe to run on both fresh databases (where create_all already added them) and
old databases (where they are missing).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "0010_ensure_columns"
down_revision = "0009_experiments"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # ── strategies ─────────────────────────────────────────────────────────
    # discovery_data was added to db.py without a migration
    if not _has_column(bind, "strategies", "discovery_data"):
        op.add_column(
            "strategies",
            sa.Column("discovery_data", postgresql.JSONB(), nullable=True),
        )

    # roi_json was added in 0008_roi_validation but some DBs may have missed it
    if not _has_column(bind, "strategies", "roi_json"):
        op.add_column(
            "strategies",
            sa.Column("roi_json", postgresql.JSONB(), nullable=True),
        )

    # last_signal_scan & daily_signal_summary were added in 0007 but may be
    # missing on DBs where 0001 ran create_all before those columns were in model
    if not _has_column(bind, "strategies", "last_signal_scan"):
        op.add_column(
            "strategies",
            sa.Column("last_signal_scan", sa.DateTime(), nullable=True),
        )
    if not _has_column(bind, "strategies", "daily_signal_summary"):
        op.add_column(
            "strategies",
            sa.Column("daily_signal_summary", postgresql.JSONB(), nullable=True),
        )

    # updated_at may also be missing on old tables
    if not _has_column(bind, "strategies", "updated_at"):
        op.add_column(
            "strategies",
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    # ── experiment_batches / experiments ────────────────────────────────────
    # These tables are created by 0009_experiments but may be missing too
    if not insp.has_table("experiment_batches"):
        op.create_table(
            "experiment_batches",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("strategy_id", sa.String(), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("n_experiments", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("leads_per_experiment", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("status", sa.String(), server_default="draft"),
            sa.Column("hypothesis", sa.Text(), nullable=True),
            sa.Column("best_experiment_id", sa.String(), nullable=True),
            sa.Column("analysis_json", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )

    if not insp.has_table("experiments"):
        op.create_table(
            "experiments",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("batch_id", sa.String(), sa.ForeignKey("experiment_batches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("strategy_id", sa.String(), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("idx", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("hypothesis", sa.Text(), nullable=True),
            sa.Column("params_json", postgresql.JSONB(), nullable=True),
            sa.Column("source", sa.String(), server_default="ai"),
            sa.Column("status", sa.String(), server_default="draft"),
            sa.Column("result_summary_json", postgresql.JSONB(), nullable=True),
            sa.Column("leads_json", postgresql.JSONB(), nullable=True),
            sa.Column("relevancy_json", postgresql.JSONB(), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )


def downgrade() -> None:
    # Non-destructive — no downgrade needed for safety guards
    pass

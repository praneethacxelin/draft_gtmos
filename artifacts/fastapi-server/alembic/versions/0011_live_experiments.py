"""Closed-loop (live) experiment lifecycle columns.

Turns an experiment batch from a one-shot Apollo relevancy test into a real
funnel test: each variant materializes a cohort of contacts, drafts sequences,
the engineer launches sends, and a live window measures who actually replies
with positive intent (books a call / wants to move forward). The live winner is
the variant with the highest positive-intent reply rate over the window.

All columns are additive + nullable so existing batches keep working.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "0011_live_experiments"
down_revision = "0010_contact_source"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def _add(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if not _has_column(bind, table, column.name):
        op.add_column(table, column)


def upgrade() -> None:
    # ---- experiment_batches: live-window tracking ----
    _add("experiment_batches", sa.Column("live_status", sa.String(), nullable=True))
    _add("experiment_batches", sa.Column("window_months", sa.Integer(), nullable=True))
    _add("experiment_batches", sa.Column("window_started_at", sa.DateTime(), nullable=True))
    _add("experiment_batches", sa.Column("window_ends_at", sa.DateTime(), nullable=True))
    _add("experiment_batches", sa.Column("live_winner_experiment_id", sa.String(), nullable=True))
    _add("experiment_batches", sa.Column("live_analysis_json", JSONB(), nullable=True))

    # ---- experiments: per-variant live cohort + funnel metrics ----
    _add("experiments", sa.Column("cohort_size", sa.Integer(), nullable=True))
    _add("experiments", sa.Column("live_launched_at", sa.DateTime(), nullable=True))
    _add("experiments", sa.Column("live_metrics_json", JSONB(), nullable=True))


def downgrade() -> None:
    for col in (
        "live_winner_experiment_id",
        "live_analysis_json",
        "window_ends_at",
        "window_started_at",
        "window_months",
        "live_status",
    ):
        op.drop_column("experiment_batches", col)
    for col in ("live_metrics_json", "live_launched_at", "cohort_size"):
        op.drop_column("experiments", col)

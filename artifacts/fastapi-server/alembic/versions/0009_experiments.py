"""Add experiment_batches + experiments tables.

Backs the Experiments engine (``app/agents/experiments.py``): a profile can
run multiple experiment batches, each holding N Apollo-parameter variations
that are run against Apollo and analysed together to surface the best
performing parameter set and the most relevant leads for the product profile.

Experiment leads are stored inline on the experiment row (``leads_json``) and
are deliberately NOT written to the live ``contacts`` table — experiments are
exploratory and must not pollute the real pipeline.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "0009_experiments"
down_revision = "0008_roi_validation"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "experiment_batches"):
        op.create_table(
            "experiment_batches",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("strategy_id", sa.String(), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("n_experiments", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("leads_per_experiment", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("status", sa.String(), nullable=True, server_default="draft"),
            sa.Column("hypothesis", sa.Text(), nullable=True),
            sa.Column("best_experiment_id", sa.String(), nullable=True),
            sa.Column("analysis_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_experiment_batches_strategy_id", "experiment_batches", ["strategy_id"])
        op.create_index("ix_experiment_batches_user_id", "experiment_batches", ["user_id"])

    if not _has_table(bind, "experiments"):
        op.create_table(
            "experiments",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("batch_id", sa.String(), sa.ForeignKey("experiment_batches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("strategy_id", sa.String(), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("idx", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("hypothesis", sa.Text(), nullable=True),
            sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("source", sa.String(), nullable=True, server_default="ai"),
            sa.Column("status", sa.String(), nullable=True, server_default="draft"),
            sa.Column("result_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("leads_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("relevancy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_experiments_batch_id", "experiments", ["batch_id"])
        op.create_index("ix_experiments_strategy_id", "experiments", ["strategy_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "experiments"):
        op.drop_table("experiments")
    if _has_table(bind, "experiment_batches"):
        op.drop_table("experiment_batches")

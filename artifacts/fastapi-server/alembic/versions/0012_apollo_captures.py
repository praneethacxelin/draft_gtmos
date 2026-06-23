"""Silent Apollo capture store.

Mirrors every person/organization Apollo returns into ``apollo_captures``,
deduped by (apollo_id, record_type). Decoupled from the pipeline (no FKs) so it
accumulates a proprietary dataset over time. Additive + idempotent.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "0012_apollo_captures"
down_revision = "0011_live_experiments"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "apollo_captures"):
        return
    op.create_table(
        "apollo_captures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("apollo_id", sa.String(), nullable=False),
        sa.Column("record_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("endpoint", sa.String(), nullable=True),
        sa.Column("strategy_id", sa.String(), nullable=True),
        sa.Column("payload_json", JSONB(), nullable=True),
        sa.Column("seen_count", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("apollo_id", "record_type", name="uq_apollo_capture_id_type"),
    )
    op.create_index("ix_apollo_captures_apollo_id", "apollo_captures", ["apollo_id"])
    op.create_index("ix_apollo_captures_record_type", "apollo_captures", ["record_type"])
    op.create_index("ix_apollo_captures_domain", "apollo_captures", ["domain"])
    op.create_index("ix_apollo_captures_email", "apollo_captures", ["email"])
    op.create_index("ix_apollo_captures_strategy_id", "apollo_captures", ["strategy_id"])


def downgrade() -> None:
    op.drop_table("apollo_captures")

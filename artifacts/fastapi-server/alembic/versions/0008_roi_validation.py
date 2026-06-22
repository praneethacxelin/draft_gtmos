"""Add roi_json to strategies for ROI expectation validation.

Backs the ROI validator (``app/agents/roi_validator.py``) which judges
whether a product profile's investment vs expected-revenue expectation is
realistic, grounded in the profile's TAM/SAM/SOM + ICP, and stores the
verdict + calculator output on the strategy row.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "0008_roi_validation"
down_revision = "0007_drop_pgvector_signal_pulse"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "strategies", "roi_json"):
        op.add_column(
            "strategies",
            sa.Column("roi_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "strategies", "roi_json"):
        op.drop_column("strategies", "roi_json")

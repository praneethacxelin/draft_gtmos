"""Add source + source_ref columns to contacts.

Tracks where a contact entered the pipeline: ``discovery`` (normal lead
search), ``experiment`` (seeded from a winning experiment batch) or
``campaign``. ``source_ref`` holds the originating batch/experiment id or a
phase label. Both columns are additive and nullable so existing rows keep
working; ``source`` defaults to ``discovery``.\
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0011_contact_source"
down_revision = "0010_ensure_columns"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "contacts", "source"):
        op.add_column(
            "contacts",
            sa.Column("source", sa.String(), nullable=True, server_default="discovery"),
        )
    if not _has_column(bind, "contacts", "source_ref"):
        op.add_column(
            "contacts",
            sa.Column("source_ref", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "contacts", "source_ref"):
        op.drop_column("contacts", "source_ref")
    if _has_column(bind, "contacts", "source"):
        op.drop_column("contacts", "source")

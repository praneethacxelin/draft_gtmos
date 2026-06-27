"""Add contacts.apollo_person_id and users.password_hash.

``contacts.apollo_person_id`` stores the Apollo person id explicitly. Experiment
-promoted contacts reuse ``source_ref`` to hold the originating experiment id, so
``source_ref`` is NOT a reliable Apollo id for them — the dedicated column lets
email reveal match by Apollo id regardless of how the contact entered the
pipeline.

``users.password_hash`` backs basic email/password authentication. Both columns
are additive and nullable so existing rows keep working.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0013_apollo_person_id_password"
down_revision = "0012_apollo_captures"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "contacts", "apollo_person_id"):
        op.add_column(
            "contacts",
            sa.Column("apollo_person_id", sa.String(), nullable=True),
        )
    if not _has_column(bind, "users", "password_hash"):
        op.add_column(
            "users",
            sa.Column("password_hash", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "users", "password_hash"):
        op.drop_column("users", "password_hash")
    if _has_column(bind, "contacts", "apollo_person_id"):
        op.drop_column("contacts", "apollo_person_id")

"""Add users table and user_id columns for auth scoping.

Idempotent: safe to re-run if a previous attempt partially applied the
schema but failed before alembic_version was updated.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0003_auth_users"
down_revision = "0002_vector_1536"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "users" not in insp.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    for table in ("strategies", "accounts", "contacts"):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "user_id" not in cols:
            op.add_column(table, sa.Column("user_id", sa.String(), nullable=True))

        idx_names = {ix["name"] for ix in insp.get_indexes(table)}
        if f"ix_{table}_user_id" not in idx_names:
            op.create_index(f"ix_{table}_user_id", table, ["user_id"])

        fk_names = {fk["name"] for fk in insp.get_foreign_keys(table)}
        if f"fk_{table}_user_id" not in fk_names:
            op.create_foreign_key(
                f"fk_{table}_user_id",
                table,
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    for table in ("contacts", "accounts", "strategies"):
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_user_id", table)
        op.drop_column(table, "user_id")
    op.drop_table("users")

"""Scope app_settings per user.

Adds user_id FK + unique(user_id, integration_name); drops the global
unique on integration_name. Existing rows are reassigned to the first
user (if any) so single-tenant demos keep their saved keys; otherwise
they are deleted.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_user_scoped_settings"
down_revision = "0003_auth_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "app_settings",
        sa.Column("user_id", sa.String(), nullable=True),
    )
    op.create_index("ix_app_settings_user_id", "app_settings", ["user_id"])

    first_user = bind.execute(sa.text("SELECT id FROM users ORDER BY created_at ASC LIMIT 1")).scalar()
    if first_user:
        bind.execute(
            sa.text("UPDATE app_settings SET user_id = :uid WHERE user_id IS NULL"),
            {"uid": first_user},
        )
    else:
        bind.execute(sa.text("DELETE FROM app_settings"))

    op.alter_column("app_settings", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_app_settings_user",
        "app_settings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop the legacy global unique on integration_name (look it up so we
    # don't depend on a specific Postgres-generated name) then add the
    # composite one.
    legacy = bind.execute(sa.text(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'app_settings'::regclass AND contype = 'u' "
        "AND conname <> 'uq_app_settings_user_integration'"
    )).scalars().all()
    for cname in legacy:
        op.drop_constraint(cname, "app_settings", type_="unique")
    op.create_unique_constraint(
        "uq_app_settings_user_integration",
        "app_settings",
        ["user_id", "integration_name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_app_settings_user_integration", "app_settings", type_="unique")
    op.create_unique_constraint(
        "app_settings_integration_name_key",
        "app_settings",
        ["integration_name"],
    )
    op.drop_constraint("fk_app_settings_user", "app_settings", type_="foreignkey")
    op.drop_index("ix_app_settings_user_id", table_name="app_settings")
    op.drop_column("app_settings", "user_id")

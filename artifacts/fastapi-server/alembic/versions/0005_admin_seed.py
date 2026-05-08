"""Admin role + seed a default product strategy.

- Adds ``is_admin`` boolean to ``users``.
- Creates a system admin user (``user_system_admin``) that owns the
  seeded strategy. The system user has no external identity and is only
  used as an FK target for shared/demo data.
- Seeds one default Strategy (the "default product") if no strategy
  with that id exists yet. Idempotent: re-running does nothing.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0005_admin_seed"
down_revision = "0004_user_scoped_settings"
branch_labels = None
depends_on = None


SYSTEM_USER_ID = "user_system_admin"
DEFAULT_STRATEGY_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_admin" not in cols:
        op.add_column(
            "users",
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    bind.execute(
        sa.text(
            "INSERT INTO users (id, email, is_admin, created_at, updated_at) "
            "VALUES (:id, :email, true, NOW(), NOW()) "
            "ON CONFLICT (id) DO UPDATE SET is_admin = true"
        ),
        {"id": SYSTEM_USER_ID, "email": "system+admin@gtmos.local"},
    )

    exists = bind.execute(
        sa.text("SELECT 1 FROM strategies WHERE id = :id"),
        {"id": DEFAULT_STRATEGY_ID},
    ).scalar()
    if not exists:
        bind.execute(
            sa.text(
                "INSERT INTO strategies "
                "(id, user_id, product_name, description, target_market, "
                " pain_points_raw, status, created_at, updated_at) "
                "VALUES (:id, :uid, :pn, :desc, :tm, :pp, 'draft', NOW(), NOW())"
            ),
            {
                "id": DEFAULT_STRATEGY_ID,
                "uid": SYSTEM_USER_ID,
                "pn": "PulseSignal — RevOps Intelligence Platform",
                "desc": (
                    "PulseSignal is an AI-native RevOps intelligence platform that "
                    "unifies CRM, product usage, and intent signals into a single "
                    "score per account. It tells revenue teams which accounts to "
                    "work next, why, and what to say — replacing brittle "
                    "spreadsheets and disconnected dashboards."
                ),
                "tm": (
                    "Series B–D B2B SaaS companies, 200–2,000 employees, with "
                    "$25M–$250M ARR. Primary geos: North America and Western "
                    "Europe. Buyer personas: VP RevOps, VP Sales, Head of "
                    "Marketing Ops."
                ),
                "pp": (
                    "- Reps waste 60% of their week on accounts that will never close.\n"
                    "- RevOps spends days stitching CRM, product, and intent data by hand.\n"
                    "- Forecast accuracy drifts because pipeline scoring is opinion-based.\n"
                    "- Marketing and sales fight over MQL definitions every quarter."
                ),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM strategies WHERE id = :id"),
        {"id": DEFAULT_STRATEGY_ID},
    )
    bind.execute(
        sa.text("DELETE FROM users WHERE id = :id"),
        {"id": SYSTEM_USER_ID},
    )
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_admin" in cols:
        op.drop_column("users", "is_admin")

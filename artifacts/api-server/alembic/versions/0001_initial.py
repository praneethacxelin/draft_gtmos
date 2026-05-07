"""Initial schema baseline.

The application bootstraps the schema via app.db.init_db() (SQLAlchemy
``create_all``) on startup. This Alembic revision is the documented
baseline: it records that the canonical models in ``app.db`` are the
source of truth so future schema changes can be authored as regular
Alembic revisions on top of this point.
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline: schema is created by app.db.init_db() (create_all).
    pass


def downgrade() -> None:
    pass

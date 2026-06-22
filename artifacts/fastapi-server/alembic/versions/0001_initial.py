"""Initial schema with pgvector enabled.

Authors the canonical schema declared in ``app.db`` (SQLAlchemy models)
through Alembic so the production database can be brought up via
``alembic upgrade head``. Enables the ``pgvector`` extension and drops
the legacy ``competitors`` table that was renamed to
``competitor_profiles`` in earlier development.
"""
from alembic import op
import sqlalchemy as sa  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP TABLE IF EXISTS competitors")

    # Import lazily so Alembic env can run without app side-effects at import time.
    from app.db import Base
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.db import Base
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

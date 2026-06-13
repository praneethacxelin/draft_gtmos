"""Drop pgvector arrays for JSONB embeddings + add signal-pulse columns.

The embedding columns were ``float8[]`` arrays that required the ``vector``
extension to be enabled at startup (``CREATE EXTENSION``), which is painful
on Windows. Embeddings are never queried with pgvector operators — the
queryable vector store is now ChromaDB — so we convert the columns to JSONB
and store the same float lists portably.

Also adds ``last_signal_scan`` and ``daily_signal_summary`` to ``strategies``
to back the daily signal cron + dashboard Signal Pulse card.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "0007_drop_pgvector_signal_pulse"
down_revision = "0006_audit_logs"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    # ---- Convert embedding arrays to JSONB ----
    # The legacy columns carry a float8[] server default (``'{}'``) that
    # Postgres can't auto-cast to JSONB, so drop the default first, convert,
    # then restore a JSON-typed default where one is required.
    if _has_column(bind, "icp_embeddings", "embedding"):
        op.execute("ALTER TABLE icp_embeddings ALTER COLUMN embedding DROP DEFAULT")
        op.execute(
            "ALTER TABLE icp_embeddings "
            "ALTER COLUMN embedding TYPE JSONB USING to_jsonb(embedding)"
        )
        op.execute("ALTER TABLE icp_embeddings ALTER COLUMN embedding SET DEFAULT '[]'::jsonb")
    if _has_column(bind, "pattern_clusters", "cluster_embedding"):
        op.execute("ALTER TABLE pattern_clusters ALTER COLUMN cluster_embedding DROP DEFAULT")
        op.execute(
            "ALTER TABLE pattern_clusters "
            "ALTER COLUMN cluster_embedding TYPE JSONB USING to_jsonb(cluster_embedding)"
        )

    # ---- New strategy columns for the daily signal cron ----
    if not _has_column(bind, "strategies", "last_signal_scan"):
        op.add_column(
            "strategies",
            sa.Column("last_signal_scan", sa.DateTime(), nullable=True),
        )
    if not _has_column(bind, "strategies", "daily_signal_summary"):
        op.add_column(
            "strategies",
            sa.Column("daily_signal_summary", postgresql.JSONB(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_column(bind, "strategies", "daily_signal_summary"):
        op.drop_column("strategies", "daily_signal_summary")
    if _has_column(bind, "strategies", "last_signal_scan"):
        op.drop_column("strategies", "last_signal_scan")

    # Revert embeddings to float8[] (data is derived; safe to reset).
    if _has_column(bind, "icp_embeddings", "embedding"):
        op.execute("ALTER TABLE icp_embeddings ALTER COLUMN embedding DROP DEFAULT")
        op.execute(
            "ALTER TABLE icp_embeddings "
            "ALTER COLUMN embedding TYPE float8[] USING ARRAY[]::float8[]"
        )
    if _has_column(bind, "pattern_clusters", "cluster_embedding"):
        op.execute(
            "ALTER TABLE pattern_clusters "
            "ALTER COLUMN cluster_embedding TYPE float8[] USING ARRAY[]::float8[]"
        )

"""Resize pgvector columns to 1536 dims (matches OpenAI text-embedding-3-small).

The original implementation used 384 dims for the SHA-based pseudo-embeddings;
the project spec calls for 1536 so similarity math stays compatible with real
OpenAI embeddings if/when the proxy starts exposing them. We resize via DROP +
ADD because pgvector requires column rebuilds on dim changes; the embedding
columns are derived data and are repopulated by the agent pipeline.
"""
from alembic import op


revision = "0002_vector_1536"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("TRUNCATE TABLE icp_embeddings")
    op.execute("ALTER TABLE icp_embeddings DROP COLUMN embedding")
    op.execute("ALTER TABLE icp_embeddings ADD COLUMN embedding vector(1536) NOT NULL")

    op.execute("ALTER TABLE pattern_clusters DROP COLUMN cluster_embedding")
    op.execute("ALTER TABLE pattern_clusters ADD COLUMN cluster_embedding vector(1536)")


def downgrade() -> None:
    op.execute("ALTER TABLE icp_embeddings DROP COLUMN embedding")
    op.execute("ALTER TABLE icp_embeddings ADD COLUMN embedding vector(384) NOT NULL")
    op.execute("ALTER TABLE pattern_clusters DROP COLUMN cluster_embedding")
    op.execute("ALTER TABLE pattern_clusters ADD COLUMN cluster_embedding vector(384)")

"""Add first-party revision memory, embeddings, and retrieval provenance."""

from alembic import op
from liproser.database import Base

revision = "0004_v02_memory"
down_revision = "0003_v02_review"
branch_labels = None
depends_on = None

TABLES = (
    "revision_memory_eligibility",
    "revision_embeddings",
    "revision_retrievals",
)


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind, checkfirst=True)

"""Add the v0.2 voice and evidence-aware content foundation."""

from alembic import op
from liproser.database import Base

revision = "0002_v02"
down_revision = "0001_v01"
branch_labels = None
depends_on = None

TABLES = (
    "voice_profiles",
    "voice_samples",
    "taxonomy_snapshots",
    "content_ideas",
    "source_references",
    "posts",
    "post_revisions",
    "claim_assessments",
)


def upgrade():
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind, checkfirst=True)

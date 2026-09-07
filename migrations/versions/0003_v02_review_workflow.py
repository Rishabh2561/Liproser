"""Add immutable revision checks, edit deltas, and human review history."""

from alembic import op
from liproser.database import Base

revision = "0003_v02_review"
down_revision = "0002_v02"
branch_labels = None
depends_on = None

TABLES = ("revision_checks", "reviews", "edit_deltas")


def upgrade():
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind, checkfirst=True)

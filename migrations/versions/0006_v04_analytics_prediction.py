"""Add v0.4 analytics, experiments, feature snapshots, and predictions."""

from alembic import op
from liproser.database import Base
import sqlalchemy as sa

revision = "0006_v04_analytics"
down_revision = "0005_v03_calendar"
branch_labels = None
depends_on = None

TABLES = ("experiments", "metric_snapshots", "feature_snapshots", "predictions")


def upgrade():
    bind = op.get_bind()
    post_columns = {column["name"] for column in sa.inspect(bind).get_columns("posts")}
    if "published_at" not in post_columns:
        op.add_column("posts", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind, checkfirst=True)
    post_columns = {column["name"] for column in sa.inspect(bind).get_columns("posts")}
    if "published_at" in post_columns:
        op.drop_column("posts", "published_at")

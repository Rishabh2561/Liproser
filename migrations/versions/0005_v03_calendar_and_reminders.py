"""Add v0.3 calendars, scheduling, outbox jobs, and feedback preferences."""

from alembic import op
from liproser.database import Base

revision = "0005_v03_calendar"
down_revision = "0004_v02_memory"
branch_labels = None
depends_on = None

TABLES = (
    "content_calendars", "calendar_slots", "post_schedules", "publish_actions",
    "outbox_events", "job_runs", "dead_letters", "feedback_signals", "preference_rules",
)


def upgrade():
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind, checkfirst=True)

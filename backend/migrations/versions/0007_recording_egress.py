"""Track the LiveKit egress job behind each session recording (Epic E5,
docs/10-virtual-classroom.md recording orchestration).

Revision ID: 0007_recording_egress
Revises: 0006_sessions_attendance
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_recording_egress"
down_revision = "0006_sessions_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_recordings",
        sa.Column("egress_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_session_recordings_egress_id", "session_recordings", ["egress_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_session_recordings_egress_id", table_name="session_recordings")
    op.drop_column("session_recordings", "egress_id")

"""Class sessions, recordings, attendance (docs/05 sections 3.15-3.17).

Revision ID: 0006_sessions_attendance
Revises: 0005_assignments
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_sessions_attendance"
down_revision = "0005_assignments"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "class_sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "course_id", sa.Uuid, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="scheduled"),
        sa.Column(
            "created_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        *_timestamps(),
    )
    op.create_index("ix_class_sessions_tenant_id", "class_sessions", ["tenant_id"])
    op.create_index("ix_class_sessions_course", "class_sessions", ["course_id", "scheduled_start"])

    op.create_table(
        "session_recordings",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "class_session_id",
            sa.Uuid,
            sa.ForeignKey("class_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("duration_seconds", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="processing"),
        *_timestamps(),
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "class_session_id",
            sa.Uuid,
            sa.ForeignKey("class_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("source", sa.String(8), nullable=False, server_default="auto"),
        sa.Column("marked_by", sa.Uuid, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("class_session_id", "user_id", name="uq_attendance_session_user"),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE class_sessions ENABLE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation_class_sessions ON class_sessions "
            "USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )
        for table in ["class_sessions", "session_recordings", "attendance_records"]:
            op.execute(
                f"CREATE TRIGGER touch_updated_at_{table} BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at()"
            )


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.drop_table("session_recordings")
    op.drop_table("class_sessions")

"""Assignments: assignments, submissions, grades (docs/05 sections 3.12-3.14).

Revision ID: 0005_assignments
Revises: 0004_communication
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_assignments"
down_revision = "0004_communication"
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
        "assignments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "course_id", sa.Uuid, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text, nullable=False, server_default=""),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allow_late", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("max_score", sa.Float, nullable=False, server_default="100"),
        sa.Column("rubric", sa.JSON, nullable=True),
        sa.Column(
            "created_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        *_timestamps(),
    )
    op.create_index("ix_assignments_tenant_id", "assignments", ["tenant_id"])
    op.create_index("ix_assignments_course", "assignments", ["course_id", "due_at"])

    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "assignment_id",
            sa.Uuid,
            sa.ForeignKey("assignments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("content", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "assignment_id", "student_id", name="uq_submissions_assignment_student"
        ),
    )
    op.create_index("ix_submissions_tenant_id", "submissions", ["tenant_id"])
    op.create_index("ix_submissions_student_status", "submissions", ["student_id", "status"])

    op.create_table(
        "grades",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "submission_id",
            sa.Uuid,
            sa.ForeignKey("submissions.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "grader_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("feedback", sa.Text, nullable=False, server_default=""),
        sa.Column("rubric_scores", sa.JSON, nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ["assignments", "submissions"]:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation_{table} ON {table} "
                f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
            )
        for table in ["assignments", "submissions", "grades"]:
            op.execute(
                f"CREATE TRIGGER touch_updated_at_{table} BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at()"
            )


def downgrade() -> None:
    op.drop_table("grades")
    op.drop_table("submissions")
    op.drop_table("assignments")

"""Assignments ORM models: assignments, submissions, grades.

Schema per docs/05-database-design.md sections 3.12-3.14. Submissions carry
client_id + version because they are the flagship offline-mutable entity
(drafted offline, synced on reconnect — FR-ASG-2, docs/09).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import (
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    VersionMixin,
)


class SubmissionStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    LATE = "late"
    GRADED = "graded"


class Assignment(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "assignments"
    __table_args__ = (Index("ix_assignments_course", "course_id", "due_at"),)

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allow_late: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    rubric: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    submissions: Mapped[list["Submission"]] = relationship(back_populates="assignment")


class Submission(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, VersionMixin):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_submissions_assignment_student"),
        Index("ix_submissions_student_status", "student_id", "status"),
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, values_callable=lambda e: [m.value for m in e]),
        default=SubmissionStatus.DRAFT,
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment: Mapped[Assignment] = relationship(back_populates="submissions")
    grade: Mapped["Grade | None"] = relationship(back_populates="submission")


class Grade(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "grades"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("submissions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    grader_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rubric_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="grade")

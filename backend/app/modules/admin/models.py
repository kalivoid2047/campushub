"""Admin/structure ORM models: departments, courses, enrollments, audit log, quotas.

Schema per docs/05-database-design.md §3.4–3.6, §3.18–3.19.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
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
    utcnow,
)


class EnrollmentRole(str, enum.Enum):
    STUDENT = "student"
    LECTURER = "lecturer"
    TA = "ta"


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)

    courses: Mapped[list["Course"]] = relationship(back_populates="department")


class Course(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", "term", name="uq_courses_tenant_code_term"),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    term: Mapped[str] = mapped_column(String(32), nullable=False)

    department: Mapped[Department] = relationship(back_populates="courses")
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(back_populates="course")


class CourseEnrollment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_enrollments_course_user"),
        Index("ix_enrollments_user", "user_id"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[EnrollmentRole] = mapped_column(
        Enum(EnrollmentRole, values_callable=lambda e: [m.value for m in e]),
        default=EnrollmentRole.STUDENT,
        nullable=False,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    course: Mapped[Course] = relationship(back_populates="enrollments")


class AuditLog(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Append-only — no update/delete path exists in the application
    (docs/08-security-design.md §9)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class StorageQuota(Base):
    __tablename__ = "storage_quotas"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

"""Attendance ORM model (docs/05-database-design.md section 3.16).

Records are created automatically from class-session join/leave events
(FR-ATT-1) or manually by a lecturer for in-person sessions.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AttendanceSource(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"


class AttendanceRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("class_session_id", "user_id", name="uq_attendance_session_user"),
    )

    class_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    source: Mapped[AttendanceSource] = mapped_column(
        Enum(AttendanceSource, values_callable=lambda e: [m.value for m in e]),
        default=AttendanceSource.AUTO,
        nullable=False,
    )
    marked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

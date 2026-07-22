"""Virtual classroom ORM models: class sessions + recordings metadata.

Schema per docs/05-database-design.md sections 3.15, 3.17. The WebRTC media
plane (docs/10) attaches to this lifecycle: /join issues signaling/SFU
credentials once the media milestone lands; join/leave events already feed
attendance (docs/10 section 3).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDED = "ended"
    CANCELLED = "cancelled"


class RecordingStatus(str, enum.Enum):
    PROCESSING = "processing"
    AVAILABLE = "available"
    FAILED = "failed"


class ClassSession(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "class_sessions"
    __table_args__ = (Index("ix_class_sessions_course", "course_id", "scheduled_start"),)

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, values_callable=lambda e: [m.value for m in e]),
        default=SessionStatus.SCHEDULED,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    recordings: Mapped[list["SessionRecording"]] = relationship(back_populates="session")


class SessionRecording(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "session_recordings"

    class_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("class_sessions.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus, values_callable=lambda e: [m.value for m in e]),
        default=RecordingStatus.PROCESSING,
        nullable=False,
    )
    # The LiveKit Egress job backing this recording — used to stop it and to
    # reconcile status/size/duration on read (no webhook receiver; see
    # VirtualClassroomService._reconcile_recording).
    egress_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    session: Mapped[ClassSession] = relationship(back_populates="recordings")

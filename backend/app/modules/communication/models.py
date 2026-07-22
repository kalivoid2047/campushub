"""Communication ORM models: channels, messages, announcements.

Schema per docs/05-database-design.md sections 3.10-3.11. Messages carry a
client_id so offline-composed messages deduplicate on sync replay
(docs/09 section 2 / FR-COM-4).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ChannelType(str, enum.Enum):
    COURSE = "course"
    DM = "dm"


class AnnouncementScope(str, enum.Enum):
    INSTITUTION = "institution"
    DEPARTMENT = "department"
    COURSE = "course"


class Channel(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "channels"
    __table_args__ = (Index("ix_channels_course", "course_id"),)

    type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Course channels have course_id set; DMs identify participants via
    # channel_members instead.
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    members: Mapped[list["ChannelMember"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="channel")


class ChannelMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Explicit membership for DM channels (course channels derive membership
    from course enrollment)."""

    __tablename__ = "channel_members"
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_channel_members"),)

    channel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    channel: Mapped[Channel] = relationship(back_populates="members")


class Message(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_channel_created", "channel_id", "created_at"),
        UniqueConstraint("client_id", name="uq_messages_client_id"),
    )

    channel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Offline dedupe key (docs/05 section 3.10); nullable for messages sent
    # online through the REST path.
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    channel: Mapped[Channel] = relationship(back_populates="messages")


class Announcement(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "announcements"
    __table_args__ = (Index("ix_announcements_scope", "scope", "scope_id"),)

    scope: Mapped[AnnouncementScope] = mapped_column(
        Enum(AnnouncementScope, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # NULL for institution-wide; department_id or course_id otherwise.
    scope_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    published_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

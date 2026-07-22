"""Data access for the communication module.

Every query is tenant-scoped (docs/05-database-design.md section 1).
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.communication.models import (
    Announcement,
    AnnouncementScope,
    Channel,
    ChannelMember,
    ChannelType,
    Message,
)


class CommunicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Channels ---

    async def get_channel(self, tenant_id: uuid.UUID, channel_id: uuid.UUID) -> Channel | None:
        result = await self._session.execute(
            select(Channel)
            .where(Channel.id == channel_id, Channel.tenant_id == tenant_id)
            .options(selectinload(Channel.members))
        )
        return result.scalar_one_or_none()

    async def get_course_channel(
        self, tenant_id: uuid.UUID, course_id: uuid.UUID
    ) -> Channel | None:
        result = await self._session.execute(
            select(Channel).where(
                Channel.tenant_id == tenant_id,
                Channel.course_id == course_id,
                Channel.type == ChannelType.COURSE,
            )
        )
        return result.scalar_one_or_none()

    async def create_course_channel(
        self, tenant_id: uuid.UUID, course_id: uuid.UUID, name: str
    ) -> Channel:
        channel = Channel(
            tenant_id=tenant_id,
            course_id=course_id,
            type=ChannelType.COURSE,
            name=name,
        )
        self._session.add(channel)
        await self._session.flush()
        return channel

    async def find_dm_channel(
        self, tenant_id: uuid.UUID, user_a: uuid.UUID, user_b: uuid.UUID
    ) -> Channel | None:
        # A DM between the same two users is reused, not duplicated.
        result = await self._session.execute(
            select(Channel)
            .where(Channel.tenant_id == tenant_id, Channel.type == ChannelType.DM)
            .join(ChannelMember)
            .where(ChannelMember.user_id.in_([user_a, user_b]))
            .options(selectinload(Channel.members))
        )
        for channel in result.scalars().unique():
            member_ids = {m.user_id for m in channel.members}
            if member_ids == {user_a, user_b}:
                return channel
        return None

    async def create_dm_channel(
        self, tenant_id: uuid.UUID, user_a: uuid.UUID, user_b: uuid.UUID
    ) -> Channel:
        channel = Channel(tenant_id=tenant_id, type=ChannelType.DM)
        self._session.add(channel)
        await self._session.flush()
        self._session.add_all(
            [
                ChannelMember(channel_id=channel.id, user_id=user_a),
                ChannelMember(channel_id=channel.id, user_id=user_b),
            ]
        )
        await self._session.flush()
        return channel

    async def is_dm_member(self, channel_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    # --- Messages ---

    async def get_message_by_client_id(
        self, tenant_id: uuid.UUID, client_id: uuid.UUID
    ) -> Message | None:
        result = await self._session.execute(
            select(Message).where(Message.tenant_id == tenant_id, Message.client_id == client_id)
        )
        return result.scalar_one_or_none()

    async def create_message(
        self,
        tenant_id: uuid.UUID,
        channel_id: uuid.UUID,
        sender_id: uuid.UUID,
        body: str,
        attachments: list,
        client_id: uuid.UUID | None,
    ) -> Message:
        message = Message(
            tenant_id=tenant_id,
            channel_id=channel_id,
            sender_id=sender_id,
            body=body,
            attachments=attachments,
            client_id=client_id,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_messages(
        self,
        tenant_id: uuid.UUID,
        channel_id: uuid.UUID,
        before: datetime | None,
        limit: int,
    ) -> list[Message]:
        query = (
            select(Message)
            .where(Message.channel_id == channel_id, Message.tenant_id == tenant_id)
            .order_by(Message.created_at.desc())
            .limit(limit + 1)
        )
        if before is not None:
            query = query.where(Message.created_at < before)
        result = await self._session.execute(query)
        return list(result.scalars())

    # --- Announcements ---

    async def create_announcement(
        self,
        tenant_id: uuid.UUID,
        scope: AnnouncementScope,
        scope_id: uuid.UUID | None,
        title: str,
        body: str,
        published_by: uuid.UUID,
    ) -> Announcement:
        announcement = Announcement(
            tenant_id=tenant_id,
            scope=scope,
            scope_id=scope_id,
            title=title,
            body=body,
            published_by=published_by,
        )
        self._session.add(announcement)
        await self._session.flush()
        return announcement

    async def list_announcements(
        self,
        tenant_id: uuid.UUID,
        course_ids: list[uuid.UUID],
        department_ids: list[uuid.UUID],
        limit: int = 100,
    ) -> list[Announcement]:
        """Institution-wide announcements plus those scoped to any of the
        user's courses/departments."""
        from sqlalchemy import and_, or_

        conditions = [Announcement.scope == AnnouncementScope.INSTITUTION]
        if course_ids:
            conditions.append(
                and_(
                    Announcement.scope == AnnouncementScope.COURSE,
                    Announcement.scope_id.in_(course_ids),
                )
            )
        if department_ids:
            conditions.append(
                and_(
                    Announcement.scope == AnnouncementScope.DEPARTMENT,
                    Announcement.scope_id.in_(department_ids),
                )
            )
        result = await self._session.execute(
            select(Announcement)
            .where(Announcement.tenant_id == tenant_id, or_(*conditions))
            .order_by(Announcement.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

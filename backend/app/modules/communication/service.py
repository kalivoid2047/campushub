"""Business logic for the communication module (Epic E3).

Course channels derive membership from enrollment; DMs use explicit
channel_members. Offline-composed messages arrive both through the REST
path (with client_id) and through the sync engine's "messages" handler —
both deduplicate on client_id (FR-COM-4). Every persisted message appends
to the sync change log so other devices pull it as a delta.
"""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.admin.repository import AdminRepository
from app.modules.communication.models import (
    AnnouncementScope,
    Channel,
    ChannelType,
    Message,
)
from app.modules.communication.repository import CommunicationRepository
from app.modules.communication.schemas import (
    CreateAnnouncementRequest,
    SendMessageRequest,
)
from app.modules.sync.models import SyncOperation
from app.modules.sync.repository import SyncRepository

_ADMIN_ROLES = {"dept_admin", "institution_admin", "super_admin"}
_ANNOUNCE_ROLES = {"dept_admin", "institution_admin", "super_admin"}


class CommunicationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CommunicationRepository(session)
        self._admin_repo = AdminRepository(session)
        self._sync_repo = SyncRepository(session)

    # --- Channels ---

    async def get_or_create_course_channel(
        self, user: CurrentUser, course_id: uuid.UUID
    ) -> Channel:
        await self._ensure_course_member(user, course_id)
        channel = await self._repo.get_course_channel(user.tenant_id, course_id)
        if channel is None:
            course = await self._admin_repo.get_course(user.tenant_id, course_id)
            channel = await self._repo.create_course_channel(
                user.tenant_id, course_id, name=f"{course.code} discussion"
            )
            await self._session.commit()
        return channel

    async def get_or_create_dm(self, user: CurrentUser, recipient_id: uuid.UUID) -> Channel:
        if recipient_id == user.user_id:
            raise HTTPException(status_code=422, detail="Cannot DM yourself")
        recipient = await self._admin_repo.get_tenant_user(user.tenant_id, recipient_id)
        if recipient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        channel = await self._repo.find_dm_channel(user.tenant_id, user.user_id, recipient_id)
        if channel is None:
            channel = await self._repo.create_dm_channel(user.tenant_id, user.user_id, recipient_id)
            await self._session.commit()
        return channel

    # --- Messages ---

    async def send_message(
        self, user: CurrentUser, channel_id: uuid.UUID, request: SendMessageRequest
    ) -> Message:
        channel = await self._get_channel_checked(user, channel_id)

        if request.client_id is not None:
            existing = await self._repo.get_message_by_client_id(user.tenant_id, request.client_id)
            if existing is not None:
                return existing  # offline dedupe (FR-COM-4)

        message = await self._repo.create_message(
            tenant_id=user.tenant_id,
            channel_id=channel.id,
            sender_id=user.user_id,
            body=request.body,
            attachments=request.attachments,
            client_id=request.client_id,
        )
        await self._sync_repo.append_change(
            tenant_id=user.tenant_id,
            entity_table="messages",
            entity_id=message.id,
            operation=SyncOperation.CREATE,
            payload={
                "channel_id": str(channel.id),
                "sender_id": str(user.user_id),
                "body": message.body,
                "created_at": message.created_at.isoformat(),
            },
            version=1,
            changed_by=user.user_id,
        )
        await self._session.commit()

        # Live fan-out to connected sockets (delivery only — the DB row and
        # sync change log above are the durable source of truth).
        from app.core.realtime import channel_topic, get_broker

        await get_broker().publish(
            channel_topic(user.tenant_id, channel.id),
            {
                "type": "message.created",
                "id": str(message.id),
                "channel_id": str(channel.id),
                "sender_id": str(user.user_id),
                "body": message.body,
                "created_at": message.created_at.isoformat(),
            },
        )
        return message

    async def list_messages(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        before: datetime | None,
        limit: int,
    ) -> tuple[list[Message], bool]:
        await self._get_channel_checked(user, channel_id)
        limit = min(max(limit, 1), 100)
        rows = await self._repo.list_messages(user.tenant_id, channel_id, before, limit)
        has_more = len(rows) > limit
        return rows[:limit], has_more

    # --- Announcements ---

    async def create_announcement(self, user: CurrentUser, request: CreateAnnouncementRequest):
        scope = AnnouncementScope(request.scope)
        if scope == AnnouncementScope.COURSE:
            # Lecturers may announce to courses they teach; otherwise admin.
            if request.scope_id is None:
                raise HTTPException(status_code=422, detail="scope_id required")
            await self._ensure_course_member(user, request.scope_id, require_lecturer=True)
        else:
            if not user.has_any_role(*_ANNOUNCE_ROLES):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin role required for this announcement scope",
                )
            if scope == AnnouncementScope.INSTITUTION:
                request.scope_id = None

        announcement = await self._repo.create_announcement(
            tenant_id=user.tenant_id,
            scope=scope,
            scope_id=request.scope_id,
            title=request.title,
            body=request.body,
            published_by=user.user_id,
        )
        await self._sync_repo.append_change(
            tenant_id=user.tenant_id,
            entity_table="announcements",
            entity_id=announcement.id,
            operation=SyncOperation.CREATE,
            payload={
                "scope": scope.value,
                "scope_id": str(request.scope_id) if request.scope_id else None,
                "title": announcement.title,
                "body": announcement.body,
            },
            version=1,
            changed_by=user.user_id,
        )
        await self._session.commit()
        return announcement

    async def list_announcements(self, user: CurrentUser):
        course_ids, department_ids = await self._user_scopes(user)
        return await self._repo.list_announcements(user.tenant_id, course_ids, department_ids)

    # --- Helpers ---

    async def _get_channel_checked(self, user: CurrentUser, channel_id: uuid.UUID) -> Channel:
        channel = await self._repo.get_channel(user.tenant_id, channel_id)
        if channel is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
        if channel.type == ChannelType.COURSE:
            await self._ensure_course_member(user, channel.course_id)
        else:
            if not await self._repo.is_dm_member(channel.id, user.user_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
        return channel

    async def _ensure_course_member(
        self, user: CurrentUser, course_id: uuid.UUID, require_lecturer: bool = False
    ) -> None:
        course = await self._admin_repo.get_course(user.tenant_id, course_id)
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if user.has_any_role(*_ADMIN_ROLES):
            return
        enrollment = await self._admin_repo.get_enrollment(course_id, user.user_id)
        if enrollment is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in course"
            )
        if require_lecturer and enrollment.role.value not in ("lecturer", "ta"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lecturer role required for this course",
            )

    async def _user_scopes(self, user: CurrentUser) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        """Course and department ids the user belongs to, for announcement
        visibility. Admins see everything in the tenant."""
        if user.has_any_role(*_ADMIN_ROLES):
            scopes = await self._admin_repo.list_all_course_scopes(user.tenant_id)
        else:
            scopes = await self._admin_repo.list_user_course_scopes(user.tenant_id, user.user_id)
        return [s[0] for s in scopes], [s[1] for s in scopes]

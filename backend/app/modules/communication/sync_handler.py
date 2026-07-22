"""Sync handler for offline-composed messages (docs/09, FR-COM-4).

Registered for entity_table "messages". Messages are create-only (no
update/delete via sync), so the handler always returns version 1 and never
raises SyncConflict — the only failure modes are validation/authorization,
surfaced as SyncRejected.

Authorization mirrors CommunicationService._get_channel_checked, duplicated
here rather than delegated to the service: the service's send_message also
appends to the sync change log itself (for the REST path, which isn't routed
through the generic sync engine), and calling it from here would double-log
the change — the generic engine already logs one entry per applied item
after this handler returns (app/modules/sync/service.py).

Payload contract (client -> server):
    {"channel_id": "<uuid>", "body": "...", "attachments": [...]}
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.admin.repository import AdminRepository
from app.modules.communication.models import ChannelType
from app.modules.communication.repository import CommunicationRepository
from app.modules.sync.registry import SyncRejected, register_handler
from app.modules.sync.schemas import SyncBatchItem

_ADMIN_ROLES = {"dept_admin", "institution_admin", "super_admin"}


class MessageSyncHandler:
    async def apply(
        self, session: AsyncSession, user: CurrentUser, item: SyncBatchItem
    ) -> tuple[int, dict]:
        payload = item.payload
        try:
            channel_id = uuid.UUID(str(payload["channel_id"]))
        except (KeyError, ValueError) as exc:
            raise SyncRejected("INVALID_PAYLOAD", "channel_id missing/invalid") from exc

        body = payload.get("body")
        if not isinstance(body, str) or not body.strip():
            raise SyncRejected("INVALID_PAYLOAD", "body must be a non-empty string")

        repo = CommunicationRepository(session)
        admin_repo = AdminRepository(session)

        channel = await repo.get_channel(user.tenant_id, channel_id)
        if channel is None:
            raise SyncRejected("NOT_FOUND", "Channel not found")

        if channel.type == ChannelType.COURSE:
            if not user.has_any_role(*_ADMIN_ROLES):
                enrollment = await admin_repo.get_enrollment(channel.course_id, user.user_id)
                if enrollment is None:
                    raise SyncRejected("FORBIDDEN", "Not enrolled in course")
        else:
            if not await repo.is_dm_member(channel.id, user.user_id):
                raise SyncRejected("FORBIDDEN", "Not a member of this conversation")

        message = await repo.create_message(
            tenant_id=user.tenant_id,
            channel_id=channel.id,
            sender_id=user.user_id,
            body=body,
            attachments=payload.get("attachments", []),
            client_id=item.client_id,
        )
        return 1, {
            "channel_id": str(channel.id),
            "sender_id": str(user.user_id),
            "body": message.body,
            "created_at": message.created_at.isoformat(),
        }


def register() -> None:
    register_handler("messages", MessageSyncHandler())

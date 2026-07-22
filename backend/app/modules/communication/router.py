"""HTTP routes for the communication module (docs/06 section 6).

Mounted at /api/v1. Real-time WebSocket fan-out lands with the WebSocket
milestone (docs/00-implementation-roadmap.md); these REST routes are the
durable source of truth either way.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.modules.communication.schemas import (
    AnnouncementResponse,
    ChannelResponse,
    CreateAnnouncementRequest,
    CreateDmRequest,
    MessagePage,
    MessageResponse,
    SendMessageRequest,
)
from app.modules.communication.service import CommunicationService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_db_session)) -> CommunicationService:
    return CommunicationService(session)


def _channel_response(channel) -> ChannelResponse:
    return ChannelResponse(
        id=channel.id,
        type=channel.type.value,
        course_id=channel.course_id,
        name=channel.name,
        created_at=channel.created_at,
    )


@router.get(
    "/courses/{course_id}/channel",
    response_model=ChannelResponse,
    summary="Get (or lazily create) the course discussion channel",
)
async def course_channel(
    course_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: CommunicationService = Depends(_service),
) -> ChannelResponse:
    return _channel_response(await service.get_or_create_course_channel(user, course_id))


@router.post(
    "/channels/dm",
    response_model=ChannelResponse,
    summary="Get (or create) a DM channel with another user",
)
async def create_dm(
    request: CreateDmRequest,
    user: CurrentUser = Depends(get_current_user),
    service: CommunicationService = Depends(_service),
) -> ChannelResponse:
    return _channel_response(await service.get_or_create_dm(user, request.recipient_id))


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    summary="Send a message (idempotent when client_id is supplied)",
)
async def send_message(
    channel_id: uuid.UUID,
    request: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    service: CommunicationService = Depends(_service),
) -> MessageResponse:
    return await service.send_message(user, channel_id, request)


@router.get(
    "/channels/{channel_id}/messages",
    response_model=MessagePage,
    summary="Paginated message history (newest first, cursor on created_at)",
)
async def list_messages(
    channel_id: uuid.UUID,
    before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: CommunicationService = Depends(_service),
) -> MessagePage:
    messages, has_more = await service.list_messages(user, channel_id, before, limit)
    return MessagePage(
        messages=[MessageResponse.model_validate(m) for m in messages],
        next_cursor=messages[-1].created_at.isoformat() if messages else None,
        has_more=has_more,
    )


@router.post(
    "/announcements",
    response_model=AnnouncementResponse,
    status_code=201,
    summary="Publish an announcement (scope-gated)",
)
async def create_announcement(
    request: CreateAnnouncementRequest,
    user: CurrentUser = Depends(get_current_user),
    service: CommunicationService = Depends(_service),
) -> AnnouncementResponse:
    a = await service.create_announcement(user, request)
    return AnnouncementResponse(
        id=a.id,
        scope=a.scope.value,
        scope_id=a.scope_id,
        title=a.title,
        body=a.body,
        published_by=a.published_by,
        created_at=a.created_at,
    )


@router.get(
    "/announcements",
    response_model=list[AnnouncementResponse],
    summary="Announcements visible to the caller",
)
async def list_announcements(
    user: CurrentUser = Depends(get_current_user),
    service: CommunicationService = Depends(_service),
) -> list[AnnouncementResponse]:
    return [
        AnnouncementResponse(
            id=a.id,
            scope=a.scope.value,
            scope_id=a.scope_id,
            title=a.title,
            body=a.body,
            published_by=a.published_by,
            created_at=a.created_at,
        )
        for a in await service.list_announcements(user)
    ]

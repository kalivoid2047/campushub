"""WebSocket endpoints for real-time messaging (docs/06 section 7).

Flow: client POSTs /ws/ticket (JWT-authenticated) → receives a single-use
ticket → opens ws://.../ws/channels/{id}?ticket=... . Messages continue to
be SENT via the REST/sync path (durable, deduplicated); the socket is a
delivery channel only.
"""

import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core import db
from app.core.realtime import (
    WsPrincipal,
    channel_topic,
    get_broker,
    get_ticket_store,
    user_topic,
)
from app.core.security import CurrentUser, get_current_user

ws_router = APIRouter()


class TicketResponse(BaseModel):
    ticket: str
    expires_in: int = 60


@ws_router.post(
    "/ws/ticket",
    response_model=TicketResponse,
    summary="Issue a single-use WebSocket handshake ticket",
)
async def issue_ticket(user: CurrentUser = Depends(get_current_user)) -> TicketResponse:
    ticket = get_ticket_store().issue(
        WsPrincipal(user_id=user.user_id, tenant_id=user.tenant_id, roles=user.roles)
    )
    return TicketResponse(ticket=ticket)


async def _authorize_channel(principal: WsPrincipal, channel_id: uuid.UUID) -> bool:
    """Reuses the communication service's access check against a fresh DB
    session (WebSocket handshakes are outside FastAPI's HTTP DI scope)."""
    from fastapi import HTTPException

    from app.modules.communication.service import CommunicationService

    # Late attribute lookup so tests can point db.async_session_factory at
    # the test database.
    async with db.async_session_factory() as session:
        service = CommunicationService(session)
        user = CurrentUser(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            roles=principal.roles,
        )
        try:
            await service._get_channel_checked(user, channel_id)
        except HTTPException:
            return False
    return True


@ws_router.websocket("/ws/channels/{channel_id}")
async def channel_socket(websocket: WebSocket, channel_id: uuid.UUID) -> None:
    ticket = websocket.query_params.get("ticket", "")
    principal = get_ticket_store().redeem(ticket)
    if principal is None:
        await websocket.close(code=4401)  # unauthenticated
        return
    if not await _authorize_channel(principal, channel_id):
        await websocket.close(code=4403)  # forbidden
        return

    await websocket.accept()
    broker = get_broker()
    topic = channel_topic(principal.tenant_id, channel_id)
    queue = broker.subscribe(topic)
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        broker.unsubscribe(topic, queue)


@ws_router.websocket("/ws/notifications")
async def notification_socket(websocket: WebSocket) -> None:
    ticket = websocket.query_params.get("ticket", "")
    principal = get_ticket_store().redeem(ticket)
    if principal is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    broker = get_broker()
    topic = user_topic(principal.tenant_id, principal.user_id)
    queue = broker.subscribe(topic)
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        broker.unsubscribe(topic, queue)

"""Real-time pub/sub broker and WebSocket ticket store (docs/06 section 7).

Broker: in-process implementation for single-node development. The interface
matches what a Redis pub/sub-backed implementation needs, so multi-node
production (docs/04 section 8) swaps the backend without touching call sites.

Tickets: WebSocket handshakes authenticate with a short-lived single-use
ticket obtained via POST /ws/ticket, so long-lived JWTs never appear in
query strings (docs/06 section 7).
"""

import asyncio
import secrets
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass

TICKET_TTL_SECONDS = 60


@dataclass
class WsPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    roles: list[str]


class TicketStore:
    """Single-use, short-TTL tickets. In-memory (dev/single-node); the
    production multi-node variant stores tickets in Redis with EXPIRE."""

    def __init__(self) -> None:
        self._tickets: dict[str, tuple[WsPrincipal, float]] = {}

    def issue(self, principal: WsPrincipal) -> str:
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (principal, time.monotonic() + TICKET_TTL_SECONDS)
        return ticket

    def redeem(self, ticket: str) -> WsPrincipal | None:
        entry = self._tickets.pop(ticket, None)  # single-use: pop, not get
        if entry is None:
            return None
        principal, expires = entry
        if time.monotonic() > expires:
            return None
        return principal


class Broker:
    """Topic-based fan-out. Topics are strings namespaced by tenant, e.g.
    "{tenant_id}:channel:{channel_id}" or "{tenant_id}:user:{user_id}"."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, topic: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers[topic].add(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        self._subscribers[topic].discard(queue)
        if not self._subscribers[topic]:
            del self._subscribers[topic]

    async def publish(self, topic: str, payload: dict) -> None:
        for queue in list(self._subscribers.get(topic, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Slow consumer: drop rather than block the publisher; the
                # durable REST/sync path remains the source of truth.
                pass


_ticket_store = TicketStore()
_broker = Broker()


def get_ticket_store() -> TicketStore:
    return _ticket_store


def get_broker() -> Broker:
    return _broker


def channel_topic(tenant_id: uuid.UUID, channel_id: uuid.UUID) -> str:
    return f"{tenant_id}:channel:{channel_id}"


def user_topic(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"{tenant_id}:user:{user_id}"

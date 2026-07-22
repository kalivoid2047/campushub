"""Sync entity-handler registry.

Each feature module that supports offline mutation registers a handler for
its entity table (e.g. the Assignments module registers a handler for
"submissions"). The sync service dispatches batch items to the registered
handler; unknown tables are rejected. This keeps the sync engine generic
while each module owns its validation, RBAC, and persistence rules —
consistent with the module boundaries in docs/04-system-architecture.md.
"""

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.sync.schemas import SyncBatchItem


class SyncConflict(Exception):
    """Raised by a handler when base_version does not match the server state
    (docs/09-offline-sync.md section 3)."""

    def __init__(self, server_version: int, server_payload: dict) -> None:
        self.server_version = server_version
        self.server_payload = server_payload


class SyncRejected(Exception):
    """Raised by a handler for non-retryable validation/permission failures.

    The client surfaces these to the user instead of retrying
    (docs/09-offline-sync.md section 9: 4xx-class errors do not retry).
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class SyncEntityHandler(Protocol):
    """Applies one client mutation to one entity table.

    Contract: the handler must scope every read/write to `user.tenant_id`,
    perform object-level authorization, and return the entity's new state.
    """

    async def apply(
        self,
        session: AsyncSession,
        user: CurrentUser,
        item: SyncBatchItem,
    ) -> tuple[int, dict]:
        """Returns (new_version, payload_snapshot). Raises SyncConflict or
        SyncRejected as appropriate."""
        ...


_handlers: dict[str, SyncEntityHandler] = {}


def register_handler(entity_table: str, handler: SyncEntityHandler) -> None:
    _handlers[entity_table] = handler


def get_handler(entity_table: str) -> SyncEntityHandler | None:
    return _handlers.get(entity_table)


def registered_tables() -> list[str]:
    return sorted(_handlers)

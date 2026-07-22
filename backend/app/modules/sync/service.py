"""Sync engine business logic: idempotent batch apply + cursor delta pull.

Implements docs/09-offline-sync.md sections 2-4 (server half):
- Each batch item is dispatched to the registered entity handler.
- client_id replays return the originally stored result (idempotency).
- Version mismatches surface as per-item conflicts, never batch failures —
  one conflicting item must not block the rest of the queue.
- Every applied mutation appends to the change log that powers delta pull.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.sync.models import SyncOperation
from app.modules.sync.registry import SyncConflict, SyncRejected, get_handler
from app.modules.sync.repository import SyncRepository
from app.modules.sync.schemas import (
    SyncBatchItem,
    SyncBatchRequest,
    SyncBatchResponse,
    SyncChangeOut,
    SyncItemResult,
    SyncItemStatus,
    SyncPullResponse,
)

MAX_PULL_LIMIT = 500


class SyncService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SyncRepository(session)

    async def process_batch(
        self, user: CurrentUser, request: SyncBatchRequest
    ) -> SyncBatchResponse:
        results: list[SyncItemResult] = []
        for item in request.items:
            results.append(await self._process_item(user, item))
        await self._session.commit()
        return SyncBatchResponse(results=results)

    async def _process_item(self, user: CurrentUser, item: SyncBatchItem) -> SyncItemResult:
        # Idempotency: a replayed client_id returns the stored result verbatim.
        applied = await self._repo.get_applied_op(item.client_id)
        if applied is not None:
            if applied.tenant_id != user.tenant_id:
                # A client_id from another tenant is treated as unknown —
                # never leak that it exists (docs/08 section 1).
                return self._error(item, "INVALID_CLIENT_ID", "Unknown client_id reuse")
            return SyncItemResult.model_validate(applied.result)

        handler = get_handler(item.entity_table)
        if handler is None:
            return self._error(item, "UNKNOWN_ENTITY", f"No sync handler for '{item.entity_table}'")

        try:
            new_version, payload = await handler.apply(self._session, user, item)
        except SyncConflict as conflict:
            result = SyncItemResult(
                client_id=item.client_id,
                status=SyncItemStatus.CONFLICT,
                entity_id=item.entity_id,
                server_version=conflict.server_version,
                server_payload=conflict.server_payload,
            )
            # Conflicts are terminal for this client_id: the client must
            # resolve and resubmit under a NEW client_id (docs/09 section 3).
            await self._record(user, item, result)
            return result
        except SyncRejected as rejected:
            result = self._error(item, rejected.code, rejected.message)
            await self._record(user, item, result)
            return result

        await self._repo.append_change(
            tenant_id=user.tenant_id,
            entity_table=item.entity_table,
            entity_id=item.entity_id,
            operation=SyncOperation(item.operation.value),
            payload=payload,
            version=new_version,
            changed_by=user.user_id,
        )
        result = SyncItemResult(
            client_id=item.client_id,
            status=SyncItemStatus.APPLIED,
            entity_id=item.entity_id,
            new_version=new_version,
        )
        await self._record(user, item, result)
        return result

    async def pull_changes(
        self, user: CurrentUser, since_cursor: int, limit: int
    ) -> SyncPullResponse:
        limit = min(max(limit, 1), MAX_PULL_LIMIT)
        rows = await self._repo.get_changes_since(user.tenant_id, since_cursor, limit)
        has_more = len(rows) > limit
        rows = rows[:limit]
        changes = [
            SyncChangeOut(
                cursor=row.id,
                entity_table=row.entity_table,
                entity_id=row.entity_id,
                operation=row.operation.value,
                payload=row.payload,
                version=row.version,
                changed_at=row.changed_at,
            )
            for row in rows
        ]
        next_cursor = rows[-1].id if rows else since_cursor
        return SyncPullResponse(changes=changes, next_cursor=next_cursor, has_more=has_more)

    # --- Helpers ---

    def _error(self, item: SyncBatchItem, code: str, message: str) -> SyncItemResult:
        return SyncItemResult(
            client_id=item.client_id,
            status=SyncItemStatus.ERROR,
            entity_id=item.entity_id,
            error_code=code,
            error_message=message,
        )

    async def _record(self, user: CurrentUser, item: SyncBatchItem, result: SyncItemResult) -> None:
        await self._repo.record_applied_op(
            client_id=item.client_id,
            tenant_id=user.tenant_id,
            entity_table=item.entity_table,
            entity_id=item.entity_id,
            result=result.model_dump(mode="json"),
        )

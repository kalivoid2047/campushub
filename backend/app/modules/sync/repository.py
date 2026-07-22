"""Data access for the sync module: change log and applied-op ledger.

All queries are tenant-scoped (docs/05-database-design.md section 1).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sync.models import SyncAppliedOp, SyncChange, SyncOperation


class SyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Idempotency ledger ---

    async def get_applied_op(self, client_id: uuid.UUID) -> SyncAppliedOp | None:
        result = await self._session.execute(
            select(SyncAppliedOp).where(SyncAppliedOp.client_id == client_id)
        )
        return result.scalar_one_or_none()

    async def record_applied_op(
        self,
        client_id: uuid.UUID,
        tenant_id: uuid.UUID,
        entity_table: str,
        entity_id: uuid.UUID,
        result: dict,
    ) -> None:
        self._session.add(
            SyncAppliedOp(
                client_id=client_id,
                tenant_id=tenant_id,
                entity_table=entity_table,
                entity_id=entity_id,
                result=result,
            )
        )
        await self._session.flush()

    # --- Change log ---

    async def append_change(
        self,
        tenant_id: uuid.UUID,
        entity_table: str,
        entity_id: uuid.UUID,
        operation: SyncOperation,
        payload: dict,
        version: int,
        changed_by: uuid.UUID | None,
    ) -> SyncChange:
        change = SyncChange(
            tenant_id=tenant_id,
            entity_table=entity_table,
            entity_id=entity_id,
            operation=operation,
            payload=payload,
            version=version,
            changed_by=changed_by,
        )
        self._session.add(change)
        await self._session.flush()
        return change

    async def get_changes_since(
        self, tenant_id: uuid.UUID, since_cursor: int, limit: int
    ) -> list[SyncChange]:
        result = await self._session.execute(
            select(SyncChange)
            .where(SyncChange.tenant_id == tenant_id, SyncChange.id > since_cursor)
            .order_by(SyncChange.id)
            .limit(limit + 1)  # +1 to detect has_more without a count query
        )
        return list(result.scalars())

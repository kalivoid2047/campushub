"""HTTP routes for the sync module (docs/06-api-design.md section 6, Sync).

Mounted at /api/v1/sync. All routes require authentication; tenant scope
always comes from the JWT, never the request.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.modules.sync.schemas import (
    SyncBatchRequest,
    SyncBatchResponse,
    SyncPullResponse,
)
from app.modules.sync.service import SyncService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_db_session)) -> SyncService:
    return SyncService(session)


@router.post(
    "/batch",
    response_model=SyncBatchResponse,
    summary="Apply a batch of queued offline mutations (idempotent per client_id)",
)
async def sync_batch(
    request: SyncBatchRequest,
    user: CurrentUser = Depends(get_current_user),
    service: SyncService = Depends(_service),
) -> SyncBatchResponse:
    return await service.process_batch(user, request)


@router.get(
    "/changes",
    response_model=SyncPullResponse,
    summary="Pull server-side changes since a cursor (delta sync)",
)
async def sync_changes(
    since: int = Query(0, ge=0, description="Cursor from the previous pull; 0 for full sync"),
    limit: int = Query(100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
    service: SyncService = Depends(_service),
) -> SyncPullResponse:
    return await service.pull_changes(user, since, limit)

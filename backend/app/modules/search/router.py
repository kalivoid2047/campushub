"""HTTP routes for the search module (docs/06 section 6). Mounted at /api/v1."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.modules.search.schemas import SearchResponse
from app.modules.search.service import SearchService

router = APIRouter()


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Permission-scoped keyword search across resources, announcements, messages",
)
async def search(
    q: str = Query(min_length=1, max_length=200),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    return await SearchService(session).search(user, q)

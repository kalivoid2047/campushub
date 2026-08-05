"""HTTP routes for the portfolio module (FR-PORT-1, Epic E10).

Mounted at /api/v1. A single self-service endpoint — no roster/other-user
view exists (or is specified) for this module.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.modules.portfolio.schemas import PortfolioResponse
from app.modules.portfolio.service import PortfolioService

router = APIRouter()


@router.get(
    "/portfolio/me",
    response_model=PortfolioResponse,
    summary="The caller's own academic portfolio: completed courses, grades, graded work",
)
async def my_portfolio(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioResponse:
    return await PortfolioService(session).my_portfolio(user)

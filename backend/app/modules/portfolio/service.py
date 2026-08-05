"""Business logic for the portfolio module (FR-PORT-1, Epic E10).

Aggregates the caller's own completed courses and graded work into a
single read model — no writes, no tables, always the caller's own record
(never a roster; that's an admin/lecturer concern already covered by the
attendance and admin modules' reports).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.iam.repository import IamRepository
from app.modules.portfolio.repository import PortfolioRepository
from app.modules.portfolio.schemas import (
    PortfolioAssignmentEntry,
    PortfolioCourseEntry,
    PortfolioResponse,
)


class PortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = PortfolioRepository(session)
        self._iam_repo = IamRepository(session)

    async def my_portfolio(self, user: CurrentUser) -> PortfolioResponse:
        me = await self._iam_repo.get_user_by_id(user.user_id)
        full_name = me.full_name if me is not None else ""

        courses = await self._repo.enrolled_courses(user.tenant_id, user.user_id)
        course_entries: list[PortfolioCourseEntry] = []
        for course, department in courses:
            graded = await self._repo.graded_assignments(user.tenant_id, user.user_id, course.id)
            assignments = [
                PortfolioAssignmentEntry(
                    assignment_id=assignment.id,
                    title=assignment.title,
                    score=grade.score,
                    max_score=assignment.max_score,
                    graded_at=grade.graded_at,
                )
                for assignment, grade in graded
            ]
            percentages = [
                entry.score / entry.max_score * 100 for entry in assignments if entry.max_score > 0
            ]
            average = round(sum(percentages) / len(percentages), 1) if percentages else None
            course_entries.append(
                PortfolioCourseEntry(
                    course_id=course.id,
                    course_name=course.name,
                    course_code=course.code,
                    term=course.term,
                    department_name=department.name,
                    average_score_percent=average,
                    assignments=assignments,
                )
            )

        return PortfolioResponse(user_id=user.user_id, full_name=full_name, courses=course_entries)

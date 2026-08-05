"""Data access for the portfolio module.

Read-only aggregation across admin (courses/departments/enrollment) and
assignments (assignments/submissions/grades) — every query is scoped to a
single (tenant_id, user_id) pair, since FR-PORT-1 is strictly self-service
(a student's own record, never a roster).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Course, CourseEnrollment, Department
from app.modules.assignments.models import Assignment, Grade, Submission


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enrolled_courses(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[tuple[Course, Department]]:
        result = await self._session.execute(
            select(Course, Department)
            .join(Department, Department.id == Course.department_id)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(CourseEnrollment.user_id == user_id, Course.tenant_id == tenant_id)
            .order_by(Course.term.desc(), Course.code)
        )
        return [(row[0], row[1]) for row in result]

    async def graded_assignments(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, course_id: uuid.UUID
    ) -> list[tuple[Assignment, Grade]]:
        """Only the caller's own graded (not merely submitted) work —
        "selected work products" per FR-PORT-1; ungraded drafts/submissions
        aren't portfolio-worthy yet."""
        result = await self._session.execute(
            select(Assignment, Grade)
            .join(Submission, Submission.assignment_id == Assignment.id)
            .join(Grade, Grade.submission_id == Submission.id)
            .where(
                Assignment.course_id == course_id,
                Assignment.tenant_id == tenant_id,
                Submission.student_id == user_id,
            )
            .order_by(Assignment.due_at)
        )
        return [(row[0], row[1]) for row in result]

"""Data access for the assignments module.

Every query is tenant-scoped (docs/05-database-design.md section 1).
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.assignments.models import Assignment, Grade, Submission


class AssignmentsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Assignments ---

    async def create_assignment(self, **kwargs) -> Assignment:
        assignment = Assignment(**kwargs)
        self._session.add(assignment)
        await self._session.flush()
        return assignment

    async def get_assignment(
        self, tenant_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> Assignment | None:
        result = await self._session.execute(
            select(Assignment).where(
                Assignment.id == assignment_id, Assignment.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_assignments(
        self, tenant_id: uuid.UUID, course_id: uuid.UUID
    ) -> list[Assignment]:
        result = await self._session.execute(
            select(Assignment)
            .where(Assignment.course_id == course_id, Assignment.tenant_id == tenant_id)
            .order_by(Assignment.due_at.is_(None), Assignment.due_at)
        )
        return list(result.scalars())

    # --- Submissions ---

    async def get_submission(
        self, tenant_id: uuid.UUID, submission_id: uuid.UUID
    ) -> Submission | None:
        result = await self._session.execute(
            select(Submission)
            .where(Submission.id == submission_id, Submission.tenant_id == tenant_id)
            .options(selectinload(Submission.assignment), selectinload(Submission.grade))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_student_submission(
        self, tenant_id: uuid.UUID, assignment_id: uuid.UUID, student_id: uuid.UUID
    ) -> Submission | None:
        result = await self._session.execute(
            select(Submission)
            .where(
                Submission.tenant_id == tenant_id,
                Submission.assignment_id == assignment_id,
                Submission.student_id == student_id,
            )
            .options(selectinload(Submission.assignment), selectinload(Submission.grade))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_submissions(
        self, tenant_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> list[Submission]:
        result = await self._session.execute(
            select(Submission)
            .where(
                Submission.assignment_id == assignment_id,
                Submission.tenant_id == tenant_id,
            )
            .options(selectinload(Submission.grade))
            .order_by(Submission.submitted_at)
        )
        return list(result.scalars())

    def add_submission(self, submission: Submission) -> None:
        self._session.add(submission)

    # --- Grades ---

    async def create_grade(
        self,
        submission_id: uuid.UUID,
        grader_id: uuid.UUID,
        score: float,
        feedback: str,
        rubric_scores: dict | None,
        graded_at: datetime,
    ) -> Grade:
        grade = Grade(
            submission_id=submission_id,
            grader_id=grader_id,
            score=score,
            feedback=feedback,
            rubric_scores=rubric_scores,
            graded_at=graded_at,
        )
        self._session.add(grade)
        await self._session.flush()
        return grade

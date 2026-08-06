"""Business logic for the assignments module (Epic E4).

Business rules implemented here:
- BR-5: a submission after due_at is flagged 'late', not blocked, unless the
  assignment disables late submissions (then it is rejected).
- BR-3: grades may only be set by a lecturer of the course or an admin, and
  every grade write is audit-logged.
- FR-ASG-2: submissions are offline-first — the same upsert path serves the
  REST route and the sync-engine handler, deduplicating on client_id and
  detecting conflicts via the submission version counter.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.admin.models import AuditLog
from app.modules.admin.repository import AdminRepository
from app.modules.assignments.models import Assignment, Grade, Submission, SubmissionStatus
from app.modules.assignments.repository import AssignmentsRepository
from app.modules.assignments.schemas import (
    CreateAssignmentRequest,
    GradeRequest,
    SubmitRequest,
)
from app.modules.sync.models import SyncOperation
from app.modules.sync.repository import SyncRepository

_ADMIN_ROLES = {"dept_admin", "institution_admin", "super_admin"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; normalize to UTC for comparisons."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class AssignmentsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AssignmentsRepository(session)
        self._admin_repo = AdminRepository(session)
        self._sync_repo = SyncRepository(session)

    # --- Assignments ---

    async def create_assignment(
        self, user: CurrentUser, course_id: uuid.UUID, request: CreateAssignmentRequest
    ) -> Assignment:
        await self._ensure_course_member(user, course_id, require_lecturer=True)
        assignment = await self._repo.create_assignment(
            tenant_id=user.tenant_id,
            course_id=course_id,
            title=request.title,
            instructions=request.instructions,
            due_at=request.due_at,
            allow_late=request.allow_late,
            max_score=request.max_score,
            rubric=request.rubric,
            created_by=user.user_id,
        )
        await self._sync_repo.append_change(
            tenant_id=user.tenant_id,
            entity_table="assignments",
            entity_id=assignment.id,
            operation=SyncOperation.CREATE,
            payload={
                "course_id": str(course_id),
                "title": assignment.title,
                "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
                "max_score": assignment.max_score,
            },
            version=1,
            changed_by=user.user_id,
        )
        await self._session.commit()
        return assignment

    async def list_assignments(self, user: CurrentUser, course_id: uuid.UUID):
        await self._ensure_course_member(user, course_id)
        return await self._repo.list_assignments(user.tenant_id, course_id)

    async def get_assignment(self, user: CurrentUser, assignment_id: uuid.UUID) -> Assignment:
        assignment = await self._repo.get_assignment(user.tenant_id, assignment_id)
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )
        await self._ensure_course_member(user, assignment.course_id)
        return assignment

    # --- Submissions (shared by REST route and sync handler) ---

    async def upsert_submission(
        self,
        user: CurrentUser,
        assignment_id: uuid.UUID,
        request: SubmitRequest,
        base_version: int | None = None,
    ) -> Submission:
        """Create or update the caller's submission.

        base_version, when supplied (sync path), must match the current
        version or a 409 is raised — the sync handler translates that into
        a SyncConflict.
        """
        assignment = await self.get_assignment(user, assignment_id)

        existing = await self._repo.get_student_submission(
            user.tenant_id, assignment_id, user.user_id
        )

        if existing is not None and existing.status == SubmissionStatus.GRADED:
            raise HTTPException(status_code=422, detail="Submission already graded")

        if base_version is not None and existing is not None and base_version != existing.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Submission was modified elsewhere",
            )

        now = _utcnow()
        new_status = SubmissionStatus.DRAFT
        submitted_at = existing.submitted_at if existing else None
        if request.finalize:
            due_at = _aware(assignment.due_at)
            if due_at is not None and now > due_at:
                if not assignment.allow_late:
                    raise HTTPException(
                        status_code=422,
                        detail="Late submissions are not allowed for this assignment",
                    )
                new_status = SubmissionStatus.LATE
            else:
                new_status = SubmissionStatus.SUBMITTED
            submitted_at = now

        if existing is None:
            submission = Submission(
                tenant_id=user.tenant_id,
                assignment_id=assignment_id,
                student_id=user.user_id,
                content=request.content,
                status=new_status,
                submitted_at=submitted_at,
            )
            self._repo.add_submission(submission)
            await self._session.flush()
            operation = SyncOperation.CREATE
        else:
            existing.content = request.content
            existing.status = new_status
            existing.submitted_at = submitted_at
            existing.version += 1
            await self._session.flush()
            submission = existing
            operation = SyncOperation.UPDATE

        await self._sync_repo.append_change(
            tenant_id=user.tenant_id,
            entity_table="submissions",
            entity_id=submission.id,
            operation=operation,
            payload={
                "assignment_id": str(assignment_id),
                "status": submission.status.value,
                "submitted_at": (
                    submission.submitted_at.isoformat() if submission.submitted_at else None
                ),
            },
            version=submission.version,
            changed_by=user.user_id,
        )
        await self._session.commit()
        return submission

    async def get_my_submission(self, user: CurrentUser, assignment_id: uuid.UUID) -> Submission:
        await self.get_assignment(user, assignment_id)
        submission = await self._repo.get_student_submission(
            user.tenant_id, assignment_id, user.user_id
        )
        if submission is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No submission yet")
        return submission

    async def list_submissions(self, user: CurrentUser, assignment_id: uuid.UUID):
        assignment = await self._repo.get_assignment(user.tenant_id, assignment_id)
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )
        await self._ensure_course_member(user, assignment.course_id, require_lecturer=True)
        return await self._repo.list_submissions(user.tenant_id, assignment_id)

    # --- Grading ---

    async def grade_submission(
        self, user: CurrentUser, submission_id: uuid.UUID, request: GradeRequest
    ) -> Grade:
        submission = await self._repo.get_submission(user.tenant_id, submission_id)
        if submission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )
        assignment = submission.assignment
        await self._ensure_course_member(user, assignment.course_id, require_lecturer=True)

        if request.score > assignment.max_score:
            raise HTTPException(
                status_code=422,
                detail=f"Score exceeds assignment max_score ({assignment.max_score})",
            )
        if submission.grade is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already graded")
        if submission.status == SubmissionStatus.DRAFT:
            raise HTTPException(status_code=422, detail="Cannot grade a draft")

        grade = await self._repo.create_grade(
            submission_id=submission.id,
            grader_id=user.user_id,
            score=request.score,
            feedback=request.feedback,
            rubric_scores=request.rubric_scores,
            graded_at=_utcnow(),
        )
        submission.status = SubmissionStatus.GRADED
        submission.version += 1

        # BR-3: every grade write is audit-logged.
        self._session.add(
            AuditLog(
                tenant_id=user.tenant_id,
                actor_id=user.user_id,
                action="grade.created",
                target_type="submission",
                target_id=submission.id,
                meta={"score": request.score, "assignment_id": str(assignment.id)},
            )
        )
        await self._sync_repo.append_change(
            tenant_id=user.tenant_id,
            entity_table="submissions",
            entity_id=submission.id,
            operation=SyncOperation.UPDATE,
            payload={
                "assignment_id": str(assignment.id),
                "status": SubmissionStatus.GRADED.value,
                "score": request.score,
            },
            version=submission.version,
            changed_by=user.user_id,
        )
        await self._session.commit()
        return grade

    # --- Helpers ---

    async def _ensure_course_member(
        self, user: CurrentUser, course_id: uuid.UUID, require_lecturer: bool = False
    ) -> None:
        course = await self._admin_repo.get_course(user.tenant_id, course_id)
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if user.has_any_role(*_ADMIN_ROLES):
            return
        enrollment = await self._admin_repo.get_enrollment(course_id, user.user_id)
        if enrollment is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in course"
            )
        if require_lecturer and enrollment.role.value not in ("lecturer", "ta"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lecturer role required for this course",
            )

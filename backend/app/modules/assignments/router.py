"""HTTP routes for the assignments module (docs/06 section 6).

Mounted at /api/v1.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.modules.assignments.schemas import (
    AssignmentResponse,
    CreateAssignmentRequest,
    GradeRequest,
    GradeResponse,
    SubmissionResponse,
    SubmitRequest,
)
from app.modules.assignments.service import AssignmentsService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_db_session)) -> AssignmentsService:
    return AssignmentsService(session)


def _submission_response(s) -> SubmissionResponse:
    return SubmissionResponse(
        id=s.id,
        assignment_id=s.assignment_id,
        student_id=s.student_id,
        content=s.content,
        status=s.status.value,
        version=s.version,
        submitted_at=s.submitted_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.post(
    "/courses/{course_id}/assignments",
    response_model=AssignmentResponse,
    status_code=201,
    summary="Create an assignment (lecturer)",
)
async def create_assignment(
    course_id: uuid.UUID,
    request: CreateAssignmentRequest,
    user: CurrentUser = Depends(get_current_user),
    service: AssignmentsService = Depends(_service),
) -> AssignmentResponse:
    return await service.create_assignment(user, course_id, request)


@router.get(
    "/courses/{course_id}/assignments",
    response_model=list[AssignmentResponse],
    summary="List course assignments",
)
async def list_assignments(
    course_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AssignmentsService = Depends(_service),
) -> list[AssignmentResponse]:
    return await service.list_assignments(user, course_id)


@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Assignment detail",
)
async def get_assignment(
    assignment_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AssignmentsService = Depends(_service),
) -> AssignmentResponse:
    return await service.get_assignment(user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=201,
    summary="Submit (or save a draft of) the caller's submission",
)
async def submit(
    assignment_id: uuid.UUID,
    request: SubmitRequest,
    user: CurrentUser = Depends(get_current_user),
    service: AssignmentsService = Depends(_service),
) -> SubmissionResponse:
    return _submission_response(await service.upsert_submission(user, assignment_id, request))


@router.get(
    "/assignments/{assignment_id}/submissions/me",
    response_model=SubmissionResponse,
    summary="The caller's own submission",
)
async def my_submission(
    assignment_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AssignmentsService = Depends(_service),
) -> SubmissionResponse:
    return _submission_response(await service.get_my_submission(user, assignment_id))


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=list[SubmissionResponse],
    summary="All submissions for an assignment (lecturer)",
)
async def list_submissions(
    assignment_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AssignmentsService = Depends(_service),
) -> list[SubmissionResponse]:
    return [_submission_response(s) for s in await service.list_submissions(user, assignment_id)]


@router.patch(
    "/submissions/{submission_id}/grade",
    response_model=GradeResponse,
    summary="Grade a submission (lecturer; audit-logged)",
)
async def grade(
    submission_id: uuid.UUID,
    request: GradeRequest,
    user: CurrentUser = Depends(get_current_user),
    service: AssignmentsService = Depends(_service),
) -> GradeResponse:
    return await service.grade_submission(user, submission_id, request)

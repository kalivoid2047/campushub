"""HTTP routes for the attendance module (docs/06 section 6).

Mounted at /api/v1.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.modules.attendance.schemas import (
    AttendanceRecordResponse,
    CourseAttendanceReport,
    ManualAttendanceRequest,
    MyAttendanceResponse,
)
from app.modules.attendance.service import AttendanceService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_db_session)) -> AttendanceService:
    return AttendanceService(session)


def _record_response(r) -> AttendanceRecordResponse:
    return AttendanceRecordResponse(
        id=r.id,
        class_session_id=r.class_session_id,
        user_id=r.user_id,
        joined_at=r.joined_at,
        left_at=r.left_at,
        duration_seconds=r.duration_seconds,
        source=r.source.value,
        marked_by=r.marked_by,
    )


@router.post(
    "/sessions/{session_id}/attendance/manual",
    response_model=AttendanceRecordResponse,
    summary="Manually mark attendance (lecturer)",
)
async def mark_manual(
    session_id: uuid.UUID,
    request: ManualAttendanceRequest,
    user: CurrentUser = Depends(get_current_user),
    service: AttendanceService = Depends(_service),
) -> AttendanceRecordResponse:
    return _record_response(await service.mark_manual(user, session_id, request))


@router.get(
    "/sessions/{session_id}/attendance",
    response_model=list[AttendanceRecordResponse],
    summary="Attendance for one session (lecturer)",
)
async def session_attendance(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AttendanceService = Depends(_service),
) -> list[AttendanceRecordResponse]:
    return [_record_response(r) for r in await service.list_session_attendance(user, session_id)]


@router.get(
    "/courses/{course_id}/attendance",
    response_model=CourseAttendanceReport,
    summary="Per-course attendance report (lecturer)",
)
async def course_attendance(
    course_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AttendanceService = Depends(_service),
) -> CourseAttendanceReport:
    return await service.course_report(user, course_id)


@router.get(
    "/courses/{course_id}/attendance/me",
    response_model=MyAttendanceResponse,
    summary="The caller's own attendance in a course (any enrolled member)",
)
async def my_attendance(
    course_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AttendanceService = Depends(_service),
) -> MyAttendanceResponse:
    return await service.my_attendance(user, course_id)

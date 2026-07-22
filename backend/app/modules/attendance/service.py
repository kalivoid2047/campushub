"""Business logic for the attendance module (Epic E6).

Auto records come from the virtual classroom join/leave lifecycle; this
module adds manual marking for in-person sessions (FR-ATT-1) and the
per-course attendance report (FR-ATT-2).
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.admin.repository import AdminRepository
from app.modules.attendance.models import AttendanceRecord, AttendanceSource
from app.modules.attendance.repository import AttendanceRepository
from app.modules.attendance.schemas import (
    CourseAttendanceReport,
    CourseAttendanceRow,
    ManualAttendanceRequest,
)
from app.modules.virtual_classroom.repository import VirtualClassroomRepository

_ADMIN_ROLES = {"dept_admin", "institution_admin", "super_admin"}


class AttendanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AttendanceRepository(session)
        self._admin_repo = AdminRepository(session)
        self._vc_repo = VirtualClassroomRepository(session)

    async def mark_manual(
        self, user: CurrentUser, session_id: uuid.UUID, request: ManualAttendanceRequest
    ) -> AttendanceRecord:
        class_session = await self._vc_repo.get_session(user.tenant_id, session_id)
        if class_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        await self._ensure_lecturer(user, class_session.course_id)

        target = await self._admin_repo.get_tenant_user(user.tenant_id, request.user_id)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        record = await self._repo.get_record(session_id, request.user_id)
        if not request.present:
            if record is not None:
                await self._session.delete(record)
                await self._session.commit()
            return AttendanceRecord(
                class_session_id=session_id,
                user_id=request.user_id,
                source=AttendanceSource.MANUAL,
                marked_by=user.user_id,
            )
        if record is None:
            record = AttendanceRecord(
                class_session_id=session_id,
                user_id=request.user_id,
                source=AttendanceSource.MANUAL,
                marked_by=user.user_id,
            )
            self._repo.add_record(record)
        else:
            record.source = AttendanceSource.MANUAL
            record.marked_by = user.user_id
        await self._session.commit()
        return record

    async def list_session_attendance(self, user: CurrentUser, session_id: uuid.UUID):
        class_session = await self._vc_repo.get_session(user.tenant_id, session_id)
        if class_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        await self._ensure_lecturer(user, class_session.course_id)
        return await self._repo.list_session_records(user.tenant_id, session_id)

    async def course_report(
        self, user: CurrentUser, course_id: uuid.UUID
    ) -> CourseAttendanceReport:
        course = await self._admin_repo.get_course(user.tenant_id, course_id)
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        await self._ensure_lecturer(user, course_id)

        total = await self._repo.count_ended_sessions(user.tenant_id, course_id)
        counts = await self._repo.attendance_counts_by_user(user.tenant_id, course_id)
        rows = [
            CourseAttendanceRow(
                user_id=user_id,
                sessions_attended=attended,
                total_sessions=total,
                attendance_rate=round(attended / total, 4) if total else 0.0,
            )
            for user_id, attended in counts
        ]
        return CourseAttendanceReport(course_id=course_id, total_sessions=total, rows=rows)

    async def _ensure_lecturer(self, user: CurrentUser, course_id: uuid.UUID) -> None:
        if user.has_any_role(*_ADMIN_ROLES):
            return
        enrollment = await self._admin_repo.get_enrollment(course_id, user.user_id)
        if enrollment is None or enrollment.role.value not in ("lecturer", "ta"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lecturer role required for this course",
            )

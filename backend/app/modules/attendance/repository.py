"""Data access for the attendance module.

Attendance rows join through class_sessions for tenant scoping
(docs/05-database-design.md section 1).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import CourseEnrollment
from app.modules.attendance.models import AttendanceRecord
from app.modules.iam.models import User
from app.modules.virtual_classroom.models import ClassSession, SessionStatus


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_record(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> AttendanceRecord | None:
        result = await self._session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.class_session_id == session_id,
                AttendanceRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    def add_record(self, record: AttendanceRecord) -> None:
        self._session.add(record)

    async def list_session_records(
        self, tenant_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[AttendanceRecord]:
        result = await self._session.execute(
            select(AttendanceRecord)
            .join(ClassSession, ClassSession.id == AttendanceRecord.class_session_id)
            .where(
                AttendanceRecord.class_session_id == session_id,
                ClassSession.tenant_id == tenant_id,
            )
            .order_by(AttendanceRecord.joined_at)
        )
        return list(result.scalars())

    async def count_ended_sessions(self, tenant_id: uuid.UUID, course_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count(ClassSession.id)).where(
                ClassSession.course_id == course_id,
                ClassSession.tenant_id == tenant_id,
                ClassSession.status == SessionStatus.ENDED,
            )
        )
        return int(result.scalar_one())

    async def attendance_counts_by_user(
        self, tenant_id: uuid.UUID, course_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, str, str, int]]:
        """(user_id, full_name, email, sessions_attended) for every user
        enrolled in the course — including zero-attendance enrollees, via an
        outer join against attendance, so a lecturer can see who never
        showed up rather than only who did."""
        attended = (
            select(AttendanceRecord.user_id, func.count(AttendanceRecord.id).label("attended"))
            .join(ClassSession, ClassSession.id == AttendanceRecord.class_session_id)
            .where(
                ClassSession.course_id == course_id,
                ClassSession.tenant_id == tenant_id,
                ClassSession.status == SessionStatus.ENDED,
            )
            .group_by(AttendanceRecord.user_id)
            .subquery()
        )
        result = await self._session.execute(
            select(
                User.id,
                User.full_name,
                User.email,
                func.coalesce(attended.c.attended, 0),
            )
            .join(CourseEnrollment, CourseEnrollment.user_id == User.id)
            .outerjoin(attended, attended.c.user_id == User.id)
            .where(CourseEnrollment.course_id == course_id, User.tenant_id == tenant_id)
            .order_by(User.full_name)
        )
        return [(row[0], row[1], row[2], int(row[3])) for row in result]

    async def attendance_count_for_user(
        self, tenant_id: uuid.UUID, course_id: uuid.UUID, user_id: uuid.UUID
    ) -> int:
        result = await self._session.execute(
            select(func.count(AttendanceRecord.id))
            .join(ClassSession, ClassSession.id == AttendanceRecord.class_session_id)
            .where(
                ClassSession.course_id == course_id,
                ClassSession.tenant_id == tenant_id,
                ClassSession.status == SessionStatus.ENDED,
                AttendanceRecord.user_id == user_id,
            )
        )
        return int(result.scalar_one())

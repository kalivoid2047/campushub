"""Data access for the virtual classroom module.

Every query is tenant-scoped (docs/05-database-design.md section 1).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models import AttendanceRecord
from app.modules.virtual_classroom.models import ClassSession


class VirtualClassroomRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, **kwargs) -> ClassSession:
        class_session = ClassSession(**kwargs)
        self._session.add(class_session)
        await self._session.flush()
        return class_session

    async def get_session(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> ClassSession | None:
        result = await self._session.execute(
            select(ClassSession).where(
                ClassSession.id == session_id, ClassSession.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_sessions(self, tenant_id: uuid.UUID, course_id: uuid.UUID) -> list[ClassSession]:
        result = await self._session.execute(
            select(ClassSession)
            .where(
                ClassSession.course_id == course_id,
                ClassSession.tenant_id == tenant_id,
            )
            .order_by(ClassSession.scheduled_start.is_(None), ClassSession.scheduled_start)
        )
        return list(result.scalars())

    async def get_attendance(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> AttendanceRecord | None:
        result = await self._session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.class_session_id == session_id,
                AttendanceRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    def add_attendance(self, record: AttendanceRecord) -> None:
        self._session.add(record)

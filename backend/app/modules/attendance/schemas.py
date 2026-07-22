"""Pydantic schemas for the attendance module (docs/06 section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ManualAttendanceRequest(BaseModel):
    user_id: uuid.UUID
    present: bool = True


class AttendanceRecordResponse(BaseModel):
    id: uuid.UUID
    class_session_id: uuid.UUID
    user_id: uuid.UUID
    joined_at: datetime | None
    left_at: datetime | None
    duration_seconds: int
    source: str
    marked_by: uuid.UUID | None


class CourseAttendanceRow(BaseModel):
    user_id: uuid.UUID
    sessions_attended: int
    total_sessions: int
    attendance_rate: float


class CourseAttendanceReport(BaseModel):
    course_id: uuid.UUID
    total_sessions: int
    rows: list[CourseAttendanceRow]

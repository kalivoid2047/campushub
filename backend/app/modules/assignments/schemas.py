"""Pydantic schemas for the assignments module (docs/06 section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateAssignmentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    instructions: str = Field(default="", max_length=50_000)
    due_at: datetime | None = None
    allow_late: bool = True
    max_score: float = Field(default=100.0, gt=0)
    rubric: dict | None = None


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    instructions: str
    due_at: datetime | None
    allow_late: bool
    max_score: float
    rubric: dict | None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitRequest(BaseModel):
    content: dict = Field(default_factory=dict)
    client_id: uuid.UUID | None = None  # offline dedupe
    finalize: bool = True  # False = save draft only


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    content: dict
    status: str
    version: int
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GradeRequest(BaseModel):
    score: float = Field(ge=0)
    feedback: str = Field(default="", max_length=20_000)
    rubric_scores: dict | None = None


class GradeResponse(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    grader_id: uuid.UUID
    score: float
    feedback: str
    rubric_scores: dict | None
    graded_at: datetime

    model_config = {"from_attributes": True}

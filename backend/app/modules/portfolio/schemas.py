"""Pydantic schemas for the portfolio module (FR-PORT-1, Epic E10).

Pure read-model — portfolio has no tables of its own; it aggregates
existing enrollment/assignment/grade data (docs/15-feature-backlog.md
Epic E10: "portfolio aggregation API").
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class PortfolioAssignmentEntry(BaseModel):
    assignment_id: uuid.UUID
    title: str
    score: float
    max_score: float
    graded_at: datetime


class PortfolioCourseEntry(BaseModel):
    course_id: uuid.UUID
    course_name: str
    course_code: str
    term: str
    department_name: str
    # None until at least one assignment in the course has been graded.
    average_score_percent: float | None
    assignments: list[PortfolioAssignmentEntry]


class PortfolioResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    courses: list[PortfolioCourseEntry]

"""Data access for the search module (Epic E7, FR-SRCH-1).

Permission scoping is baked into every query: resources via course
enrollment, announcements via visibility scopes, messages via channel
membership. On PostgreSQL, matching uses real full-text search against the
generated tsvector columns from migration 0008_search_fts (GIN-indexed —
scales past what LIKE can do). SQLite (the test suite; local dev without a
Postgres install) has no tsvector/GIN equivalent, so it falls back to
case-insensitive LIKE, selected per-query by dialect — same permission
scoping and result shape either way, just a different match strategy.
"""

import uuid

from sqlalchemy import ColumnElement, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Course, CourseEnrollment
from app.modules.communication.models import (
    Announcement,
    AnnouncementScope,
    Channel,
    ChannelMember,
    ChannelType,
    Message,
)
from app.modules.resources.models import CourseModule, Resource


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # session.bind is the AsyncEngine; its .dialect is available
        # without a round-trip (docs/13 section 1: Postgres in
        # staging/prod, SQLite in tests/local-dev-without-Postgres).
        self._postgres = session.bind is not None and session.bind.dialect.name == "postgresql"

    def _match(self, fts_table: str, term: str, *ilike_columns: ColumnElement) -> ColumnElement:
        """A boolean WHERE clause matching `term` — full-text search against
        `fts_table`.search_vector on Postgres, ILIKE across `ilike_columns`
        everywhere else."""
        if self._postgres:
            return text(
                f"{fts_table}.search_vector @@ plainto_tsquery('english', :term)"
            ).bindparams(term=term)
        return or_(*(col.ilike(f"%{term}%") for col in ilike_columns))

    async def search_resources(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool,
        term: str,
        limit: int,
    ) -> list[Resource]:
        query = (
            select(Resource)
            .join(CourseModule, CourseModule.id == Resource.module_id)
            .where(
                Resource.tenant_id == tenant_id,
                Resource.deleted_at.is_(None),
                self._match("resources", term, Resource.title),
            )
        )
        if not is_admin:
            query = query.join(
                CourseEnrollment,
                CourseEnrollment.course_id == CourseModule.course_id,
            ).where(CourseEnrollment.user_id == user_id)
        result = await self._session.execute(query.limit(limit))
        return list(result.scalars())

    async def search_announcements(
        self,
        tenant_id: uuid.UUID,
        course_ids: list[uuid.UUID],
        department_ids: list[uuid.UUID],
        term: str,
        limit: int,
    ) -> list[Announcement]:
        visibility = [Announcement.scope == AnnouncementScope.INSTITUTION]
        if course_ids:
            visibility.append(
                (Announcement.scope == AnnouncementScope.COURSE)
                & Announcement.scope_id.in_(course_ids)
            )
        if department_ids:
            visibility.append(
                (Announcement.scope == AnnouncementScope.DEPARTMENT)
                & Announcement.scope_id.in_(department_ids)
            )
        result = await self._session.execute(
            select(Announcement)
            .where(
                Announcement.tenant_id == tenant_id,
                or_(*visibility),
                self._match("announcements", term, Announcement.title, Announcement.body),
            )
            .limit(limit)
        )
        return list(result.scalars())

    async def search_messages(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool,
        term: str,
        limit: int,
    ) -> list[Message]:
        query = (
            select(Message)
            .join(Channel, Channel.id == Message.channel_id)
            .where(
                Message.tenant_id == tenant_id,
                self._match("messages", term, Message.body),
            )
        )
        if not is_admin:
            # Course channels via enrollment; DMs via membership. Admins are
            # NOT exempted from DM privacy — admin override applies to course
            # channels only, so the non-admin filter still applies to DMs.
            course_member = (Channel.type == ChannelType.COURSE) & Channel.course_id.in_(
                select(CourseEnrollment.course_id).where(CourseEnrollment.user_id == user_id)
            )
            dm_member = (Channel.type == ChannelType.DM) & Channel.id.in_(
                select(ChannelMember.channel_id).where(ChannelMember.user_id == user_id)
            )
            query = query.where(or_(course_member, dm_member))
        else:
            course_channel = Channel.type == ChannelType.COURSE
            own_dm = (Channel.type == ChannelType.DM) & Channel.id.in_(
                select(ChannelMember.channel_id).where(ChannelMember.user_id == user_id)
            )
            query = query.where(or_(course_channel, own_dm))
        result = await self._session.execute(query.limit(limit))
        return list(result.scalars())

    async def user_course_ids(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        result = await self._session.execute(
            select(Course.id, Course.department_id)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(Course.tenant_id == tenant_id, CourseEnrollment.user_id == user_id)
        )
        rows = list(result)
        return [r[0] for r in rows], [r[1] for r in rows]

    async def all_course_ids(self, tenant_id: uuid.UUID) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        result = await self._session.execute(
            select(Course.id, Course.department_id).where(Course.tenant_id == tenant_id)
        )
        rows = list(result)
        return [r[0] for r in rows], [r[1] for r in rows]

"""Business logic for the search module (Epic E7, FR-SRCH-1).

Aggregates permission-scoped keyword hits across resources, announcements,
and messages. Every underlying query is tenant- and permission-scoped in the
repository; nothing the caller cannot already read can appear in results.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.search.repository import SearchRepository
from app.modules.search.schemas import SearchHit, SearchResponse

_ADMIN_ROLES = {"dept_admin", "institution_admin", "super_admin"}
_PER_KIND_LIMIT = 20


def _snippet(text: str, term: str, radius: int = 60) -> str:
    lower = text.lower()
    index = lower.find(term.lower())
    if index < 0:
        return text[: radius * 2]
    start = max(0, index - radius)
    end = min(len(text), index + len(term) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = SearchRepository(session)

    async def search(self, user: CurrentUser, query: str) -> SearchResponse:
        term = query.strip()
        if len(term) < 2:
            return SearchResponse(query=query, hits=[])
        is_admin = user.has_any_role(*_ADMIN_ROLES)

        resources = await self._repo.search_resources(
            user.tenant_id, user.user_id, is_admin, term, _PER_KIND_LIMIT
        )
        if is_admin:
            course_ids, department_ids = await self._repo.all_course_ids(user.tenant_id)
        else:
            course_ids, department_ids = await self._repo.user_course_ids(
                user.tenant_id, user.user_id
            )
        announcements = await self._repo.search_announcements(
            user.tenant_id, course_ids, department_ids, term, _PER_KIND_LIMIT
        )
        messages = await self._repo.search_messages(
            user.tenant_id, user.user_id, is_admin, term, _PER_KIND_LIMIT
        )

        hits: list[SearchHit] = []
        hits += [
            SearchHit(
                kind="resource",
                id=r.id,
                title=r.title,
                snippet=_snippet(r.title, term),
                context_id=r.module_id,
                created_at=r.created_at,
            )
            for r in resources
        ]
        hits += [
            SearchHit(
                kind="announcement",
                id=a.id,
                title=a.title,
                snippet=_snippet(a.body or a.title, term),
                context_id=a.scope_id,
                created_at=a.created_at,
            )
            for a in announcements
        ]
        hits += [
            SearchHit(
                kind="message",
                id=m.id,
                title="Message",
                snippet=_snippet(m.body, term),
                context_id=m.channel_id,
                created_at=m.created_at,
            )
            for m in messages
        ]
        hits.sort(key=lambda h: h.created_at, reverse=True)
        return SearchResponse(query=query, hits=hits)

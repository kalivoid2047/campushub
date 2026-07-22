"""Base repository enforcing tenant-scoped queries.

Per docs/05-database-design.md §1 and docs/08-security-design.md §1: every
tenant-scoped table carries tenant_id and is protected by Postgres RLS. This
base class exists so no concrete repository can accidentally omit the
tenant_id filter (defense in depth alongside RLS).
"""

from sqlalchemy.ext.asyncio import AsyncSession


class BaseTenantRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

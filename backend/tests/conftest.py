"""Shared test fixtures.

Uses in-memory SQLite (aiosqlite) so unit-level tests run without a native
PostgreSQL install. RLS-policy behavior is Postgres-only and is covered by
the integration suite once a local PostgreSQL is available
(docs/12-testing-strategy.md section 3).
"""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models_registry
from app.core.db import get_db_session
from app.core.security import hash_password
from app.main import app
from app.modules.iam.models import RoleName, Tenant, TenantStatus, User

Base = models_registry.Base


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(session_factory):
    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_tenant(session):
    """An active tenant with one active student user (password: 'correct-horse')."""
    tenant = Tenant(name="Test College", slug="test-college", status=TenantStatus.ACTIVE)
    session.add(tenant)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        email="student@test-college.edu",
        password_hash=hash_password("correct-horse"),
        full_name="Test Student",
    )
    session.add(user)
    await session.flush()

    from app.modules.iam.repository import IamRepository

    repo = IamRepository(session)
    role = await repo.get_or_create_system_role(RoleName.STUDENT)
    await repo.grant_role(user.id, role.id)
    await session.commit()
    return tenant, user


def make_super_admin_token() -> str:
    """A super-admin access token for admin-endpoint tests (no DB user needed —
    RBAC layer 1 reads roles from the JWT)."""
    from app.core.security import create_access_token

    return create_access_token(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["super_admin"])

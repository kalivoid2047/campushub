"""Health/readiness probe tests (docs/13 section 1).

/readyz checks the two stateful dependencies every request path relies on:
the database and Redis. The module-level `engine` in app.main is swapped for
the test's in-memory SQLite engine so these tests don't depend on a real
Postgres being reachable; Redis is faked the same way LiveKit is faked in
the virtual-classroom recording tests.
"""

import pytest

from app import main as app_main

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    def __init__(self, fail: bool = False):
        self._fail = fail

    async def ping(self):
        if self._fail:
            raise ConnectionError("redis unreachable")
        return True

    async def aclose(self):
        pass


class _FailingEngine:
    def connect(self):
        raise ConnectionError("database unreachable")


async def test_healthz_always_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_ready_when_db_and_redis_reachable(client, engine, monkeypatch):
    monkeypatch.setattr(app_main, "engine", engine)
    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *_args, **_kwargs: _FakeRedis(fail=False)
    )

    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_readyz_not_ready_when_redis_unreachable(client, engine, monkeypatch):
    monkeypatch.setattr(app_main, "engine", engine)
    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *_args, **_kwargs: _FakeRedis(fail=True)
    )

    resp = await client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "redis unavailable"


async def test_readyz_not_ready_when_database_unreachable(client, monkeypatch):
    monkeypatch.setattr(app_main, "engine", _FailingEngine())

    resp = await client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "database unavailable"

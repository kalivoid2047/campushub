"""Sync core proof tests (docs/00-implementation-roadmap.md section 4 step 3:
prove queue/conflict/delta-pull mechanics against a stub entity before any
real feature module uses the engine).

The StubNote entity + handler live only in this test module — they exercise
the registry contract exactly the way Resources/Assignments handlers will.
"""

import uuid

import pytest
from sqlalchemy import String, Text, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import CurrentUser, create_access_token
from app.modules.sync import registry
from app.modules.sync.registry import SyncConflict, SyncRejected
from app.modules.sync.schemas import SyncBatchItem
from app.shared.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin

pytestmark = pytest.mark.asyncio

BATCH = "/api/v1/sync/batch"
CHANGES = "/api/v1/sync/changes"


class StubNote(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin):
    __tablename__ = "stub_notes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)


class StubNoteHandler:
    """Reference implementation of the SyncEntityHandler contract."""

    async def apply(
        self, session: AsyncSession, user: CurrentUser, item: SyncBatchItem
    ) -> tuple[int, dict]:
        result = await session.execute(
            select(StubNote).where(
                StubNote.id == item.entity_id, StubNote.tenant_id == user.tenant_id
            )
        )
        note = result.scalar_one_or_none()

        if item.operation.value == "create":
            if note is not None:
                raise SyncConflict(note.version, self._snapshot(note))
            note = StubNote(
                id=item.entity_id,
                tenant_id=user.tenant_id,
                owner_id=user.user_id,
                title=item.payload.get("title", ""),
                body=item.payload.get("body", ""),
            )
            session.add(note)
            await session.flush()
            return note.version, self._snapshot(note)

        if note is None:
            raise SyncRejected("NOT_FOUND", "Note does not exist")
        if note.owner_id != user.user_id:
            raise SyncRejected("FORBIDDEN", "Not the owner of this note")
        if item.base_version != note.version:
            raise SyncConflict(note.version, self._snapshot(note))

        if item.operation.value == "update":
            note.title = item.payload.get("title", note.title)
            note.body = item.payload.get("body", note.body)
            note.version += 1
            await session.flush()
            return note.version, self._snapshot(note)

        # delete
        await session.delete(note)
        await session.flush()
        return item.base_version + 1, {}

    def _snapshot(self, note: StubNote) -> dict:
        return {"title": note.title, "body": note.body}


@pytest.fixture(autouse=True)
def _register_stub_handler():
    registry.register_handler("stub_notes", StubNoteHandler())
    yield
    registry._handlers.pop("stub_notes", None)


@pytest.fixture
def auth(seeded_tenant):
    tenant, user = seeded_tenant
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=["student"])
    return {"Authorization": f"Bearer {token}"}


def _item(entity_id=None, client_id=None, op="create", payload=None, base_version=None):
    return {
        "client_id": str(client_id or uuid.uuid4()),
        "entity_table": "stub_notes",
        "entity_id": str(entity_id or uuid.uuid4()),
        "operation": op,
        "payload": payload if payload is not None else {"title": "T", "body": "B"},
        "base_version": base_version,
    }


async def test_create_applies_and_appears_in_delta_pull(client, auth):
    entity_id = uuid.uuid4()
    resp = await client.post(BATCH, json={"items": [_item(entity_id)]}, headers=auth)
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["status"] == "applied"
    assert result["new_version"] == 1

    pull = (await client.get(CHANGES, headers=auth)).json()
    assert len(pull["changes"]) == 1
    change = pull["changes"][0]
    assert change["entity_id"] == str(entity_id)
    assert change["operation"] == "create"
    assert change["payload"] == {"title": "T", "body": "B"}
    assert pull["next_cursor"] == change["cursor"]
    assert pull["has_more"] is False


async def test_replay_same_client_id_is_idempotent(client, auth):
    item = _item()
    first = (await client.post(BATCH, json={"items": [item]}, headers=auth)).json()
    replay = (await client.post(BATCH, json={"items": [item]}, headers=auth)).json()
    assert first["results"][0] == replay["results"][0]

    # Exactly one change row despite two submissions.
    pull = (await client.get(CHANGES, headers=auth)).json()
    assert len(pull["changes"]) == 1


async def test_update_with_correct_base_version(client, auth):
    entity_id = uuid.uuid4()
    await client.post(BATCH, json={"items": [_item(entity_id)]}, headers=auth)
    resp = await client.post(
        BATCH,
        json={"items": [_item(entity_id, op="update", payload={"title": "T2"}, base_version=1)]},
        headers=auth,
    )
    result = resp.json()["results"][0]
    assert result["status"] == "applied"
    assert result["new_version"] == 2


async def test_stale_base_version_is_conflict_with_server_state(client, auth):
    entity_id = uuid.uuid4()
    await client.post(BATCH, json={"items": [_item(entity_id)]}, headers=auth)
    await client.post(
        BATCH,
        json={"items": [_item(entity_id, op="update", payload={"title": "T2"}, base_version=1)]},
        headers=auth,
    )
    # A second client still holding base_version=1 now conflicts.
    resp = await client.post(
        BATCH,
        json={"items": [_item(entity_id, op="update", payload={"title": "T3"}, base_version=1)]},
        headers=auth,
    )
    result = resp.json()["results"][0]
    assert result["status"] == "conflict"
    assert result["server_version"] == 2
    assert result["server_payload"]["title"] == "T2"


async def test_conflict_does_not_block_rest_of_batch(client, auth):
    entity_id = uuid.uuid4()
    await client.post(BATCH, json={"items": [_item(entity_id)]}, headers=auth)
    resp = await client.post(
        BATCH,
        json={
            "items": [
                _item(entity_id, op="update", payload={"title": "X"}, base_version=99),
                _item(),  # fresh create, independent
            ]
        },
        headers=auth,
    )
    statuses = [r["status"] for r in resp.json()["results"]]
    assert statuses == ["conflict", "applied"]


async def test_unknown_entity_table_errors(client, auth):
    item = _item()
    item["entity_table"] = "no_such_table"
    resp = await client.post(BATCH, json={"items": [item]}, headers=auth)
    result = resp.json()["results"][0]
    assert result["status"] == "error"
    assert result["error_code"] == "UNKNOWN_ENTITY"


async def test_pull_cursor_pagination(client, auth):
    for _ in range(3):
        await client.post(BATCH, json={"items": [_item()]}, headers=auth)

    page1 = (await client.get(CHANGES, params={"limit": 2}, headers=auth)).json()
    assert len(page1["changes"]) == 2
    assert page1["has_more"] is True

    page2 = (
        await client.get(CHANGES, params={"since": page1["next_cursor"], "limit": 2}, headers=auth)
    ).json()
    assert len(page2["changes"]) == 1
    assert page2["has_more"] is False


async def test_pull_is_tenant_isolated(client, auth):
    await client.post(BATCH, json={"items": [_item()]}, headers=auth)

    other_tenant_token = create_access_token(
        user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["student"]
    )
    other = await client.get(CHANGES, headers={"Authorization": f"Bearer {other_tenant_token}"})
    assert other.status_code == 200
    assert other.json()["changes"] == []


async def test_sync_requires_auth(client):
    assert (await client.get(CHANGES)).status_code == 401
    assert (await client.post(BATCH, json={"items": [_item()]})).status_code == 401

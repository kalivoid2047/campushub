"""Sync handler for offline-drafted submissions (docs/09, FR-ASG-2).

Registered for entity_table "submissions". Delegates to the same service
upsert used by the REST route, translating HTTP conflicts into SyncConflict
so the sync engine reports per-item conflicts instead of failing the batch.

Payload contract (client → server):
    {"assignment_id": "<uuid>", "content": {...}, "finalize": true|false}
"""

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.sync.registry import SyncConflict, SyncRejected, register_handler
from app.modules.sync.schemas import SyncBatchItem


class SubmissionSyncHandler:
    async def apply(
        self, session: AsyncSession, user: CurrentUser, item: SyncBatchItem
    ) -> tuple[int, dict]:
        from app.modules.assignments.repository import AssignmentsRepository
        from app.modules.assignments.schemas import SubmitRequest
        from app.modules.assignments.service import AssignmentsService

        payload = item.payload
        try:
            assignment_id = uuid.UUID(str(payload["assignment_id"]))
        except (KeyError, ValueError) as exc:
            raise SyncRejected("INVALID_PAYLOAD", "assignment_id missing/invalid") from exc

        service = AssignmentsService(session)
        request = SubmitRequest(
            content=payload.get("content", {}),
            finalize=bool(payload.get("finalize", True)),
        )
        try:
            submission = await service.upsert_submission(
                user, assignment_id, request, base_version=item.base_version
            )
        except HTTPException as exc:
            if exc.status_code == 409:
                current = await AssignmentsRepository(session).get_student_submission(
                    user.tenant_id, assignment_id, user.user_id
                )
                raise SyncConflict(
                    server_version=current.version if current else 0,
                    server_payload={
                        "content": current.content if current else {},
                        "status": current.status.value if current else None,
                    },
                ) from exc
            raise SyncRejected("REJECTED", str(exc.detail)) from exc

        return submission.version, {
            "assignment_id": str(assignment_id),
            "status": submission.status.value,
            "submitted_at": (
                submission.submitted_at.isoformat() if submission.submitted_at else None
            ),
        }


def register() -> None:
    register_handler("submissions", SubmissionSyncHandler())

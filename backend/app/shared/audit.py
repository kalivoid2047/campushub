"""Central helper for writing append-only audit_logs entries
(docs/08-security-design.md section 9).

Always commits immediately, independent of whatever the caller does next —
several call sites (a failed login, a detected refresh-token reuse) raise
right after recording the event, and an audit entry that gets rolled back
along with the failure it's describing would defeat the purpose.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def record_audit_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    meta: dict | None = None,
) -> None:
    from app.modules.admin.models import AuditLog

    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta or {},
            ip_address=ip_address,
        )
    )
    await session.commit()

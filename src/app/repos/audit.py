import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def write(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_user_id=target_user_id,
        audit_metadata=metadata or {},
        ip=ip,
        user_agent=user_agent,
    )
    session.add(row)
    await session.flush()
    return row


async def list_paged(
    session: AsyncSession,
    *,
    action: str | None,
    actor_user_id: uuid.UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    size: int,
) -> tuple[list[AuditLog], int]:
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)
    if actor_user_id:
        base = base.where(AuditLog.actor_user_id == actor_user_id)
    if date_from:
        base = base.where(AuditLog.created_at >= date_from)
    if date_to:
        base = base.where(AuditLog.created_at <= date_to)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(
            base.order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size)
        )
    ).scalars().all()
    return list(rows), total

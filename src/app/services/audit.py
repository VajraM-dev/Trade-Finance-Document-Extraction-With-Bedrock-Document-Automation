import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import audit as audit_repo


async def write(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    await audit_repo.write(
        session,
        actor_user_id=actor_user_id,
        action=action,
        target_user_id=target_user_id,
        metadata=metadata,
        ip=ip,
        user_agent=user_agent,
    )

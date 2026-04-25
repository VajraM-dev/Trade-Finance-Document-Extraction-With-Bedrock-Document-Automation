import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey


async def get_by_lookup_hash(session: AsyncSession, lookup_hash: bytes) -> ApiKey | None:
    res = await session.execute(select(ApiKey).where(ApiKey.key_lookup_hash == lookup_hash))
    return res.scalar_one_or_none()


async def get_active_for_user(session: AsyncSession, user_id: uuid.UUID) -> ApiKey | None:
    res = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.status == "active")
    )
    return res.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key_lookup_hash: bytes,
    key_ciphertext: bytes,
    last_four: str,
) -> ApiKey:
    api_key = ApiKey(
        user_id=user_id,
        key_lookup_hash=key_lookup_hash,
        key_ciphertext=key_ciphertext,
        last_four=last_four,
    )
    session.add(api_key)
    await session.flush()
    return api_key


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    res = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.status == "active")
    )
    for ak in res.scalars():
        ak.status = "revoked"
        ak.revoked_at = datetime.now(timezone.utc)

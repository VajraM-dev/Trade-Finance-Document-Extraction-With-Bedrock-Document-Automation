import json
import secrets
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class Session:
    user_id: uuid.UUID
    role: str
    csrf_token: str


def _key(token: str) -> str:
    return f"session:{token}"


async def create_session(redis: Redis, *, user_id: uuid.UUID, role: str, ttl: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": str(user_id), "role": role, "csrf": csrf})
    await redis.set(_key(token), payload, ex=ttl)
    return token, csrf


async def get_session(redis: Redis, token: str) -> Session | None:
    raw = await redis.get(_key(token))
    if raw is None:
        return None
    data = json.loads(raw)
    return Session(user_id=uuid.UUID(data["user_id"]), role=data["role"], csrf_token=data["csrf"])


async def delete_session(redis: Redis, token: str) -> None:
    await redis.delete(_key(token))


async def extend_session(redis: Redis, token: str, *, ttl: int) -> bool:
    return bool(await redis.expire(_key(token), ttl))

import uuid
from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.db import get_session
from app.deps.redis import get_redis
from app.errors import ForbiddenError, UnauthorizedError
from app.repos import api_keys as api_keys_repo
from app.repos import users as users_repo
from app.services.apikeys import compute_lookup_hash
from app.services.sessions import get_session as get_redis_session
from app.settings import Settings, get_settings


@dataclass
class Principal:
    user_id: uuid.UUID
    role: str
    via: str  # "session" | "api_key"
    api_key_id: uuid.UUID | None = None
    csrf_token: str | None = None


async def _resolve_session(
    redis: Redis, session_cookie: str | None, settings: Settings
) -> Principal | None:
    if not session_cookie:
        return None
    sess = await get_redis_session(redis, session_cookie)
    if sess is None:
        return None
    return Principal(user_id=sess.user_id, role=sess.role, via="session", csrf_token=sess.csrf_token)


async def _resolve_api_key(
    redis: Redis, db: AsyncSession, api_key_header: str | None, settings: Settings
) -> Principal | None:
    if not api_key_header:
        return None
    pepper = settings.server_pepper.get_secret_value().encode("utf-8")
    h = compute_lookup_hash(pepper, api_key_header)
    cached_user = await redis.get(f"apikey:{h.hex()}")
    if cached_user:
        return Principal(user_id=uuid.UUID(cached_user.decode()), role="customer", via="api_key")
    ak = await api_keys_repo.get_by_lookup_hash(db, h)
    if not ak or ak.status != "active":
        return None
    user = await users_repo.get_by_id(db, ak.user_id)
    if user is None or user.status != "active" or user.deleted_at is not None:
        return None
    await redis.set(f"apikey:{h.hex()}", str(user.id), ex=settings.apikey_cache_ttl_seconds)
    return Principal(user_id=user.id, role=user.role, via="api_key", api_key_id=ak.id)


async def require_session(
    request: Request,
    session_id: str | None = Cookie(default=None),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> Principal:
    p = await _resolve_session(redis, session_id, settings)
    if p is None:
        raise UnauthorizedError("authentication required")
    if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
        supplied = request.headers.get("x-csrf-token")
        if not supplied or supplied != p.csrf_token:
            raise ForbiddenError("csrf token invalid")
    return p


async def require_api_key_or_session(
    request: Request,
    session_id: str | None = Cookie(default=None),
    x_api_key: str | None = Header(default=None),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Principal:
    p = await _resolve_session(redis, session_id, settings)
    if p is None:
        p = await _resolve_api_key(redis, db, x_api_key, settings)
    if p is None:
        raise UnauthorizedError("authentication required")
    if p.via == "session" and request.method in {"POST", "PATCH", "DELETE", "PUT"}:
        supplied = request.headers.get("x-csrf-token")
        if not supplied or supplied != p.csrf_token:
            raise ForbiddenError("csrf token invalid")
    return p


async def require_admin(p: Principal = Depends(require_session)) -> Principal:
    if p.role != "admin":
        raise ForbiddenError("admin role required")
    return p

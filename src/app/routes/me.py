from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.auth import Principal, require_session
from app.deps.db import get_session
from app.deps.ratelimit import rate_limit
from app.deps.redis import get_redis
from app.errors import UnauthorizedError
from app.repos import api_keys as api_keys_repo
from app.repos import users as users_repo
from app.schemas.auth import PasswordChangeRequest
from app.schemas.users import ApiKeyMaskedResponse, ApiKeyPlaintextResponse
from app.services import audit
from app.services.apikeys import compute_lookup_hash, encrypt_key, generate_key, last_four
from app.services.passwords import hash_password, verify_password
from app.settings import Settings, get_settings

router = APIRouter(prefix="/me", tags=["me"])


@router.post(
    "/api-key/rotate",
    dependencies=[Depends(rate_limit("300/minute", scope="default"))],
)
async def rotate_api_key(
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    p: Principal = Depends(require_session),
) -> ApiKeyPlaintextResponse:
    pepper = settings.server_pepper.get_secret_value().encode("utf-8")
    fkey = settings.fernet_key.get_secret_value().encode("utf-8")
    key = generate_key()
    h = compute_lookup_hash(pepper, key)
    ct = encrypt_key(fkey, key)

    await api_keys_repo.revoke_all_for_user(db, p.user_id)
    ak = await api_keys_repo.create(
        db,
        user_id=p.user_id,
        key_lookup_hash=h,
        key_ciphertext=ct,
        last_four=last_four(key),
    )
    await audit.write(
        db,
        actor_user_id=p.user_id,
        action="api_key_rotate",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return ApiKeyPlaintextResponse(
        id=ak.id, api_key=key, last_four=ak.last_four, created_at=ak.created_at
    )


@router.get("/api-key", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def get_my_api_key(
    db: AsyncSession = Depends(get_session),
    p: Principal = Depends(require_session),
) -> ApiKeyMaskedResponse | None:
    ak = await api_keys_repo.get_active_for_user(db, p.user_id)
    if ak is None:
        return None
    return ApiKeyMaskedResponse(
        id=ak.id, last_four=ak.last_four, status=ak.status, created_at=ak.created_at
    )


@router.post("/password", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    p: Principal = Depends(require_session),
) -> dict[str, str]:
    user = await users_repo.get_by_id(db, p.user_id)
    assert user is not None
    if not await verify_password(body.old_password.get_secret_value(), user.password_hash):
        raise UnauthorizedError("old password incorrect")
    new_hash = await hash_password(body.new_password.get_secret_value())
    await users_repo.update_password(db, user.id, new_hash)
    await audit.write(
        db,
        actor_user_id=user.id,
        action="password_change",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "ok"}

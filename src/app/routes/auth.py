from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.auth import Principal, require_session
from app.deps.db import get_session
from app.deps.ratelimit import rate_limit
from app.deps.redis import get_redis
from app.errors import UnauthorizedError
from app.repos import users as users_repo
from app.schemas.auth import LoginRequest, MeResponse
from app.services import audit
from app.services.passwords import verify_password
from app.services.sessions import create_session, delete_session
from app.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    dependencies=[
        Depends(rate_limit("10/minute", scope="login_ip")),
        Depends(rate_limit("20/hour", scope="login_user")),
    ],
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    user = await users_repo.get_by_username(db, body.username)
    if (
        user is None
        or user.deleted_at is not None
        or user.status != "active"
        or not await verify_password(body.password.get_secret_value(), user.password_hash)
    ):
        await audit.write(
            db,
            actor_user_id=user.id if user else None,
            action="login_failed",
            metadata={"username": body.username},
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise UnauthorizedError("invalid credentials")

    token, csrf = await create_session(
        redis, user_id=user.id, role=user.role, ttl=settings.session_ttl_seconds
    )
    response.set_cookie(
        "session_id",
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )
    await audit.write(
        db,
        actor_user_id=user.id,
        action="login",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return MeResponse(user_id=str(user.id), username=user.username, role=user.role, csrf_token=csrf)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
    p: Principal = Depends(require_session),
) -> dict[str, str]:
    sid = request.cookies.get("session_id")
    if sid:
        await delete_session(redis, sid)
    response.delete_cookie("session_id", path="/")
    return {"status": "ok"}


@router.get("/me")
async def me(
    db: AsyncSession = Depends(get_session),
    p: Principal = Depends(require_session),
) -> MeResponse:
    user = await users_repo.get_by_id(db, p.user_id)
    assert user is not None
    return MeResponse(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
        csrf_token=p.csrf_token or "",
    )

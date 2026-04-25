import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.deps.auth import Principal, require_admin
from app.deps.db import get_session
from app.deps.ratelimit import rate_limit
from app.errors import NotFoundError
from app.repos import api_keys as api_keys_repo
from app.repos import audit as audit_repo
from app.repos import jobs as jobs_repo
from app.repos import users as users_repo
from app.schemas.admin import AuditEntry, DashboardBucket, DashboardResponse
from app.schemas.auth import PasswordChangeRequest
from app.schemas.common import Page
from app.schemas.jobs import JobSummary
from app.schemas.users import (
    ApiKeyPlaintextResponse,
    UserCreateRequest,
    UserPatchRequest,
    UserResponse,
)
from app.services import audit
from app.services.apikeys import compute_lookup_hash, encrypt_key, generate_key, last_four
from app.services.passwords import hash_password
from app.settings import Settings, get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


async def _bucket(db: AsyncSession, since: datetime) -> DashboardBucket:
    totals = await db.execute(
        select(
            func.count(Job.id),
            func.coalesce(func.sum(Job.pages_processed), 0),
            func.coalesce(func.sum(Job.cost_usd), 0),
        ).where(Job.created_at >= since)
    )
    n_total, pages, cost = totals.one()
    n_success = (
        await db.execute(
            select(func.count()).where(Job.created_at >= since, Job.status == "success")
        )
    ).scalar_one()
    rate = (n_success / n_total) if n_total else 0.0
    return DashboardBucket(
        jobs=int(n_total), pages=int(pages), cost_usd=float(cost), success_rate=float(rate)
    )


@router.get("/dashboard", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def dashboard(
    db: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_admin),
) -> DashboardResponse:
    now_tz = datetime.now(timezone.utc)
    # DB stores TIMESTAMP WITHOUT TIME ZONE — strip tzinfo for comparisons
    now = now_tz.replace(tzinfo=None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    by_doc = await db.execute(
        select(Job.matched_blueprint, func.count())
        .where(Job.matched_blueprint.is_not(None))
        .group_by(Job.matched_blueprint)
    )
    by_doc_type = {k: int(v) for k, v in by_doc.all()}
    return DashboardResponse(
        today=await _bucket(db, today),
        last_7d=await _bucket(db, now - timedelta(days=7)),
        last_30d=await _bucket(db, now - timedelta(days=30)),
        by_doc_type=by_doc_type,
    )


@router.get("/users", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def list_users(
    role: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_admin),
) -> Page[UserResponse]:
    rows, total = await users_repo.list_paged(
        db, role=role, status=status, username_substr=q, page=page, size=min(size, 100)
    )
    items = [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role,
            status=u.status,
            created_at=u.created_at,
        )
        for u in rows
    ]
    return Page[UserResponse](items=items, total=total, page=page, size=min(size, 100))


@router.post("/users", status_code=201, dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def create_user(
    body: UserCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    p: Principal = Depends(require_admin),
) -> UserResponse:
    pw_hash = await hash_password(body.password.get_secret_value())
    user = await users_repo.create(
        db,
        username=body.username,
        email=body.email,
        password_hash=pw_hash,
        role=body.role,
    )
    await audit.write(
        db,
        actor_user_id=p.user_id,
        action="user_create",
        target_user_id=user.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )


@router.get("/users/{user_id}", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_admin),
) -> UserResponse:
    user = await users_repo.get_by_id(db, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("user not found")
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def patch_user(
    user_id: uuid.UUID,
    body: UserPatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    p: Principal = Depends(require_admin),
) -> UserResponse:
    user = await users_repo.get_by_id(db, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("user not found")
    if body.role is not None:
        user.role = body.role
    if body.status is not None:
        user.status = body.status
    await audit.write(
        db,
        actor_user_id=p.user_id,
        action="user_patch",
        target_user_id=user.id,
        metadata={"role": body.role, "status": body.status},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}", status_code=204, dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_session),
    p: Principal = Depends(require_admin),
) -> None:
    await users_repo.soft_delete(db, user_id)
    await audit.write(
        db,
        actor_user_id=p.user_id,
        action="user_delete",
        target_user_id=user_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/users/{user_id}/api-key/rotate", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def admin_rotate_api_key(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    p: Principal = Depends(require_admin),
) -> ApiKeyPlaintextResponse:
    pepper = settings.server_pepper.get_secret_value().encode("utf-8")
    fkey = settings.fernet_key.get_secret_value().encode("utf-8")
    key = generate_key()
    h = compute_lookup_hash(pepper, key)
    ct = encrypt_key(fkey, key)
    await api_keys_repo.revoke_all_for_user(db, user_id)
    ak = await api_keys_repo.create(
        db, user_id=user_id, key_lookup_hash=h, key_ciphertext=ct, last_four=last_four(key)
    )
    await audit.write(
        db,
        actor_user_id=p.user_id,
        action="api_key_rotate",
        target_user_id=user_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return ApiKeyPlaintextResponse(
        id=ak.id, api_key=key, last_four=ak.last_four, created_at=ak.created_at
    )


@router.post("/users/{user_id}/password", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def admin_reset_password(
    user_id: uuid.UUID,
    body: PasswordChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    p: Principal = Depends(require_admin),
) -> dict[str, str]:
    new_hash = await hash_password(body.new_password.get_secret_value())
    await users_repo.update_password(db, user_id, new_hash)
    await audit.write(
        db,
        actor_user_id=p.user_id,
        action="password_reset",
        target_user_id=user_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "ok"}


@router.get("/jobs", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def admin_list_jobs(
    user_id: uuid.UUID | None = None,
    status: str | None = None,
    doc_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_admin),
) -> Page[JobSummary]:
    rows, total = await jobs_repo.list_paged(
        db,
        user_id=user_id,
        status=status,
        doc_type=doc_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=min(size, 100),
    )
    items = [
        JobSummary(
            id=r.id,
            status=r.status,
            matched_blueprint=r.matched_blueprint,
            original_filename=r.original_filename,
            file_size_bytes=r.file_size_bytes,
            pages_processed=r.pages_processed,
            cost_usd=r.cost_usd,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in rows
    ]
    return Page[JobSummary](items=items, total=total, page=page, size=min(size, 100))


@router.get("/audit-log", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def admin_audit_log(
    action: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_admin),
) -> Page[AuditEntry]:
    rows, total = await audit_repo.list_paged(
        db,
        action=action,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=min(size, 100),
    )
    items = [
        AuditEntry(
            id=r.id,
            actor_user_id=r.actor_user_id,
            action=r.action,
            target_user_id=r.target_user_id,
            metadata=r.audit_metadata,
            ip=str(r.ip) if r.ip else None,
            user_agent=r.user_agent,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
    return Page[AuditEntry](items=items, total=total, page=page, size=min(size, 100))

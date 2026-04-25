import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    res = await session.execute(select(User).where(User.username == username))
    return res.scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    password_hash: str,
    role: str = "customer",
) -> User:
    user = User(username=username, email=email, password_hash=password_hash, role=role)
    session.add(user)
    await session.flush()
    return user


async def list_paged(
    session: AsyncSession,
    *,
    role: str | None = None,
    status: str | None = None,
    username_substr: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[User], int]:
    base = select(User).where(User.deleted_at.is_(None))
    if role:
        base = base.where(User.role == role)
    if status:
        base = base.where(User.status == status)
    if username_substr:
        base = base.where(User.username.ilike(f"%{username_substr}%"))

    total_q = select(func.count()).select_from(base.subquery())
    total = (await session.execute(total_q)).scalar_one()
    page_q = base.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = (await session.execute(page_q)).scalars().all()
    return list(rows), total


async def soft_delete(session: AsyncSession, user_id: uuid.UUID) -> None:
    user = await session.get(User, user_id)
    if user and user.deleted_at is None:
        # DB stores TIMESTAMP WITHOUT TIME ZONE — use naive UTC datetime
        user.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)


async def set_status(session: AsyncSession, user_id: uuid.UUID, status: str) -> None:
    user = await session.get(User, user_id)
    if user:
        user.status = status


async def update_password(session: AsyncSession, user_id: uuid.UUID, password_hash: str) -> None:
    user = await session.get(User, user_id)
    if user:
        user.password_hash = password_hash

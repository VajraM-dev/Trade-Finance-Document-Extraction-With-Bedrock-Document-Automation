import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job


async def get(session: AsyncSession, job_id: uuid.UUID) -> Job | None:
    return await session.get(Job, job_id)


async def create(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID | None,
    original_filename: str,
    file_size_bytes: int,
    mime_type: str,
    s3_input_uri: str,
    s3_output_prefix: str,
) -> Job:
    job = Job(
        id=job_id,
        user_id=user_id,
        api_key_id=api_key_id,
        original_filename=original_filename,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        s3_input_uri=s3_input_uri,
        s3_output_prefix=s3_output_prefix,
        status="queued",
    )
    session.add(job)
    await session.flush()
    return job


async def list_paged(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    status: str | None,
    doc_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    size: int,
) -> tuple[list[Job], int]:
    base = select(Job)
    if user_id:
        base = base.where(Job.user_id == user_id)
    if status:
        base = base.where(Job.status == status)
    if doc_type:
        base = base.where(Job.matched_blueprint == doc_type)
    if date_from:
        base = base.where(Job.created_at >= date_from)
    if date_to:
        base = base.where(Job.created_at <= date_to)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(
            base.order_by(Job.created_at.desc()).offset((page - 1) * size).limit(size)
        )
    ).scalars().all()
    return list(rows), total


async def aggregate_for_user(
    session: AsyncSession, user_id: uuid.UUID, since: datetime
) -> dict:
    res = await session.execute(
        select(
            func.count(Job.id),
            func.coalesce(func.sum(Job.pages_processed), 0),
            func.coalesce(func.sum(Job.cost_usd), 0),
        ).where(Job.user_id == user_id, Job.status == "success", Job.created_at >= since)
    )
    n, pages, cost = res.one()
    return {"jobs": int(n), "pages": int(pages), "cost_usd": float(cost)}

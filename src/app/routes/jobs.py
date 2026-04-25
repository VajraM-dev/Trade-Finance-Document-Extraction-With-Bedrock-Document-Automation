import io
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.auth import Principal, require_api_key_or_session
from app.deps.db import get_session
from app.deps.ratelimit import rate_limit
from app.errors import BadRequestError, NotFoundError
from app.repos import jobs as jobs_repo
from app.schemas.common import Page
from app.schemas.jobs import (
    JobCreatedItem,
    JobCreatedResponse,
    JobDetail,
    JobSummary,
    PreviewResponse,
)
from app.services import audit
from app.services.presign import presigned_get_url, upload_stream
from app.services.uploads import detect_mime, validate_size
from app.settings import Settings, get_settings
from app.worker.celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _input_key(user_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"{user_id}/{job_id}.bin"


@router.post(
    "",
    dependencies=[Depends(rate_limit("60/minute", scope="upload"))],
    status_code=202,
)
async def create_jobs(
    request: Request,
    files: list[UploadFile] = File(...),
    p: Principal = Depends(require_api_key_or_session),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> JobCreatedResponse:
    if not files:
        raise BadRequestError("no files supplied")
    if len(files) > settings.max_batch_size:
        raise BadRequestError(
            "batch too large", detail=f"got={len(files)} max={settings.max_batch_size}"
        )

    created: list[JobCreatedItem] = []
    for f in files:
        head = await f.read(8)
        await f.seek(0)
        mime = detect_mime(head)
        size = 0
        chunks: list[bytes] = []
        while True:
            chunk = await f.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            validate_size(size, max_mb=settings.max_file_size_mb)
            chunks.append(chunk)

        job_id = uuid.uuid4()
        key = _input_key(p.user_id, job_id)
        await upload_stream(
            settings,
            bucket=settings.s3_input_bucket,
            key=key,
            body=io.BytesIO(b"".join(chunks)),
            content_type=mime,
        )

        await jobs_repo.create(
            db,
            job_id=job_id,
            user_id=p.user_id,
            api_key_id=p.api_key_id,
            original_filename=f.filename or "upload.bin",
            file_size_bytes=size,
            mime_type=mime,
            s3_input_uri=f"s3://{settings.s3_input_bucket}/{key}",
            s3_output_prefix=f"s3://{settings.s3_output_bucket}/{job_id}/",
        )
        await db.commit()  # ensure row visible to worker before dispatch

        celery_app.send_task("process_document", args=[str(job_id)], queue="default")

        created.append(
            JobCreatedItem(job_id=job_id, status_url=f"/api/v1/jobs/{job_id}")
        )

    await audit.write(
        db,
        actor_user_id=p.user_id,
        action="jobs_uploaded",
        metadata={"count": len(created)},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return JobCreatedResponse(jobs=created)


@router.get("", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def list_jobs(
    status: str | None = None,
    doc_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    size: int = 20,
    p: Principal = Depends(require_api_key_or_session),
    db: AsyncSession = Depends(get_session),
) -> Page[JobSummary]:
    rows, total = await jobs_repo.list_paged(
        db,
        user_id=p.user_id,
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


@router.get("/{job_id}", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def get_job(
    job_id: uuid.UUID,
    p: Principal = Depends(require_api_key_or_session),
    db: AsyncSession = Depends(get_session),
) -> JobDetail:
    j = await jobs_repo.get(db, job_id)
    if j is None or (p.role != "admin" and j.user_id != p.user_id):
        raise NotFoundError("job not found")
    return JobDetail(
        id=j.id,
        status=j.status,
        matched_blueprint=j.matched_blueprint,
        original_filename=j.original_filename,
        file_size_bytes=j.file_size_bytes,
        pages_processed=j.pages_processed,
        cost_usd=j.cost_usd,
        created_at=j.created_at,
        completed_at=j.completed_at,
        extracted_fields=j.extracted_fields,
        error_code=j.error_code,
        error_message=j.error_message,
    )


@router.get("/{job_id}/raw", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def get_job_raw(
    job_id: uuid.UUID,
    p: Principal = Depends(require_api_key_or_session),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    j = await jobs_repo.get(db, job_id)
    if j is None or (p.role != "admin" and j.user_id != p.user_id):
        raise NotFoundError("job not found")
    return j.raw_bda_output or {}


@router.get(
    "/{job_id}/preview",
    dependencies=[Depends(rate_limit("300/minute", scope="default"))],
)
async def preview(
    job_id: uuid.UUID,
    p: Principal = Depends(require_api_key_or_session),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PreviewResponse:
    j = await jobs_repo.get(db, job_id)
    if j is None or (p.role != "admin" and j.user_id != p.user_id):
        raise NotFoundError("job not found")
    bucket, _, key = j.s3_input_uri.removeprefix("s3://").partition("/")
    url = await presigned_get_url(settings, bucket=bucket, key=key)
    return PreviewResponse(url=url, expires_in=settings.presigned_url_ttl_seconds)

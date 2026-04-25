import time
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bda.invoke import start_invocation
from app.bda.parse import fetch_and_parse
from app.bda.poll import BdaTerminalFailure, wait_for_completion
from app.repos import jobs as jobs_repo
from app.services.billing import compute_cost
from app.settings import Settings

log = structlog.get_logger("jobs.runner")


async def run_job(
    *,
    job_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    structlog.contextvars.bind_contextvars(job_id=str(job_id))
    # DB stores TIMESTAMP WITHOUT TIME ZONE — use naive UTC datetimes throughout.
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    started_perf = time.perf_counter()

    async with session_factory() as session:
        job = await jobs_repo.get(session, job_id)
        if job is None:
            log.error("jobs.runner.missing")
            return
        job.status = "processing"
        job.started_at = started_at
        s3_input_uri = job.s3_input_uri
        s3_output_prefix = job.s3_output_prefix
        await session.commit()

    try:
        invoked = await start_invocation(
            settings,
            job_id=str(job_id),
            s3_input_uri=s3_input_uri,
            s3_output_prefix=s3_output_prefix,
        )
        async with session_factory() as session:
            row = await jobs_repo.get(session, job_id)
            if row is not None:
                row.bda_invocation_arn = invoked.invocation_arn
                await session.commit()

        completion = await wait_for_completion(settings, invocation_arn=invoked.invocation_arn)
        parsed = await fetch_and_parse(settings, output_s3_uri=completion.output_s3_uri)
        cost = compute_cost(pages=parsed.pages, field_count=parsed.field_count)

        async with session_factory() as session:
            row = await jobs_repo.get(session, job_id)
            if row is None:
                return
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            row.status = "success"
            row.matched_blueprint = parsed.matched_blueprint
            row.pages_processed = parsed.pages
            row.blueprint_field_count = parsed.field_count
            row.cost_usd = cost
            row.extracted_fields = {"fields": parsed.fields, "confidences": parsed.confidences}
            row.raw_bda_output = parsed.raw
            row.completed_at = now
            row.duration_ms = int((time.perf_counter() - started_perf) * 1000)
            await session.commit()

        log.info(
            "job.completed",
            duration_ms=int((time.perf_counter() - started_perf) * 1000),
            pages=parsed.pages,
            cost_usd=str(cost),
            blueprint=parsed.matched_blueprint,
        )
    except BdaTerminalFailure as err:
        await _mark_failed(session_factory, job_id, code=err.code, message=str(err), started_perf=started_perf)
        log.warning("job.failed", code=err.code, message=str(err))
    except Exception as err:  # noqa: BLE001
        await _mark_failed(
            session_factory,
            job_id,
            code=type(err).__name__,
            message=str(err)[:500],
            started_perf=started_perf,
        )
        log.exception("job.failed.unhandled")
    finally:
        structlog.contextvars.unbind_contextvars("job_id")


async def _mark_failed(
    factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    *,
    code: str,
    message: str,
    started_perf: float,
) -> None:
    async with factory() as session:
        row = await jobs_repo.get(session, job_id)
        if row is None:
            return
        row.status = "failed"
        row.error_code = code
        row.error_message = message
        row.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        row.duration_ms = int((time.perf_counter() - started_perf) * 1000)
        await session.commit()

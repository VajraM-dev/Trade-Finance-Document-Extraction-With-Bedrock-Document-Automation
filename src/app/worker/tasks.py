import asyncio
import uuid

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.engine import make_engine
from app.logging import configure_logging
from app.services.jobs_runner import run_job
from app.settings import get_settings

log = structlog.get_logger("worker.task")


@shared_task(name="process_document", bind=True, max_retries=0)
def process_document(self, job_id: str) -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    structlog.contextvars.bind_contextvars(task_name="process_document", attempt=self.request.retries)
    log.info("worker.task.started", job_id=job_id)

    async def _run() -> None:
        engine = make_engine(settings)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            await run_job(
                job_id=uuid.UUID(job_id),
                session_factory=factory,
                settings=settings,
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())
    structlog.contextvars.unbind_contextvars("task_name", "attempt")

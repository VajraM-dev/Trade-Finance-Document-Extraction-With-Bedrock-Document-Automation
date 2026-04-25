from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis_async
import structlog
from fastapi import FastAPI

from app.db.engine import make_engine, make_session_factory
from app.db.migrations import run_migrations
from app.logging import configure_logging
from app.middleware.error_handler import install_error_handlers
from app.middleware.log_context import LogContextMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes import admin, auth, health, jobs, me, usage
from app.settings import get_settings

log = structlog.get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    log.info("app.starting", env="docker")

    engine = make_engine(settings)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.redis = redis_async.from_url(settings.redis_url, decode_responses=False)

    await run_migrations(engine, settings)

    log.info("app.ready")
    try:
        yield
    finally:
        await app.state.redis.close()
        await engine.dispose()
        log.info("app.stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="document-automation",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(LogContextMiddleware)
    app.add_middleware(RequestIdMiddleware)

    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(me.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(usage.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    return app


app = create_app()

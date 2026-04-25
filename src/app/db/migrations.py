import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from structlog import get_logger

from app.settings import Settings

log = get_logger(__name__)

ADVISORY_LOCK_KEY = 9_572_481_023


def _build_config(settings: Settings) -> Config:
    repo_root = Path(__file__).resolve().parents[3]
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


async def run_migrations(engine: AsyncEngine, settings: Settings) -> None:
    if not settings.run_migrations_on_startup:
        log.info("migrations.skipped")
        return

    async with engine.connect() as conn:
        await conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY})
        try:
            log.info("migrations.starting")
            await asyncio.to_thread(command.upgrade, _build_config(settings), "head")
            log.info("migrations.completed")
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})

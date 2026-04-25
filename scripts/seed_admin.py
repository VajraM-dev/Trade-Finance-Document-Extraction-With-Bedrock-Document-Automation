"""Idempotently seed the first admin user.

Run inside the api container:
  docker compose exec api uv run python scripts/seed_admin.py admin admin@example.com hunter2-strong
"""
import asyncio
import sys

import structlog

from app.db.engine import make_engine, make_session_factory
from app.repos import users as users_repo
from app.services.passwords import hash_password
from app.settings import get_settings

log = structlog.get_logger("seed")


async def main(username: str, email: str, password: str) -> None:
    settings = get_settings()
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    async with factory() as session:
        existing = await users_repo.get_by_username(session, username)
        if existing is not None:
            log.info("seed.exists", username=username)
            return
        pw_hash = await hash_password(password)
        user = await users_repo.create(
            session, username=username, email=email, password_hash=pw_hash, role="admin"
        )
        await session.commit()
        log.info("seed.created", username=user.username, user_id=str(user.id))
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: seed_admin.py <username> <email> <password>")
        sys.exit(2)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))

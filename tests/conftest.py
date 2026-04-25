import asyncio
import os
import sys
from collections.abc import AsyncIterator

import boto3
import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base

# On Windows, asyncpg requires ProactorEventLoop (default for Python 3.8+).
# The Windows ProactorEventLoop can have intermittent cleanup issues,
# but it is required for asyncpg's TCP connections to work correctly.


@pytest.fixture(scope="session", autouse=True)
def _env():
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5433/test_app")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
    os.environ.setdefault("SESSION_SECRET", "x" * 32)
    os.environ.setdefault("SERVER_PEPPER", "y" * 32)
    from cryptography.fernet import Fernet
    os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
    os.environ.setdefault("AWS_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("S3_INPUT_BUCKET", "demo-bda-inputs")
    os.environ.setdefault("S3_OUTPUT_BUCKET", "demo-bda-outputs")
    os.environ.setdefault("BDA_PROJECT_ARN", "arn:aws:bedrock:us-east-1:123:data-automation-project/abc")
    os.environ.setdefault("BDA_PROFILE_ARN", "arn:aws:bedrock:us-east-1:123:data-automation-profile/x")
    os.environ.setdefault("RUN_MIGRATIONS_ON_STARTUP", "false")
    os.environ.setdefault("COOKIE_SECURE", "false")
    yield


@pytest_asyncio.fixture
async def engine():
    from sqlalchemy.pool import NullPool
    e = create_async_engine(
        os.environ["DATABASE_URL"],
        future=True,
        # Use NullPool so connections are not pooled/cached between tests
        # This avoids asyncpg connection pool cleanup hanging on Windows
        poolclass=NullPool,
    )
    from sqlalchemy import text
    async with e.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def fake_redis():
    # Each test gets a fresh FakeRedis server instance with no shared state
    server = fakeredis.FakeServer()
    r = fakeredis.aioredis.FakeRedis(server=server, decode_responses=False)
    yield r
    await r.aclose()


@pytest.fixture
def s3_buckets():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="demo-bda-inputs")
        s3.create_bucket(Bucket="demo-bda-outputs")
        yield s3


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the rate limiter cache and real Redis rate-limit keys between tests.

    The rate limiter connects directly to the real Redis URL (not fakeredis),
    so we must flush those keys from the real Redis between tests.
    Clearing _limiters also prevents coredis connection reuse across event loops
    (Windows ProactorEventLoop requirement).
    """
    import redis as _redis

    from app.deps import ratelimit

    # Flush rate-limit keys from real Redis before each test
    try:
        _r = _redis.Redis(host="localhost", port=6379, db=0)
        keys = _r.keys("LIMITS:*")
        if keys:
            _r.delete(*keys)
        _r.close()
    except Exception:
        pass  # Redis may not be needed for health/readyz tests
    ratelimit._limiters.clear()
    yield
    ratelimit._limiters.clear()


@pytest_asyncio.fixture
async def app_client(engine, fake_redis, s3_buckets) -> AsyncIterator[AsyncClient]:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.deps.db import get_session as get_db_session
    from app.deps.redis import get_redis
    from app.main import create_app

    # Clear settings cache so env vars from _env fixture are picked up
    from app.settings import get_settings
    get_settings.cache_clear()

    app = create_app()
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _override_redis():
        return fake_redis

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_redis] = _override_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

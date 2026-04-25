import uuid

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.services.sessions import (
    create_session,
    delete_session,
    extend_session,
    get_session,
)


@pytest_asyncio.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    yield r
    await r.flushall()


@pytest.mark.asyncio
async def test_create_then_get(redis):
    user_id = uuid.uuid4()
    token, csrf = await create_session(redis, user_id=user_id, role="admin", ttl=60)
    sess = await get_session(redis, token)
    assert sess is not None
    assert sess.user_id == user_id
    assert sess.role == "admin"
    assert sess.csrf_token == csrf


@pytest.mark.asyncio
async def test_delete_session(redis):
    token, _ = await create_session(redis, user_id=uuid.uuid4(), role="customer", ttl=60)
    await delete_session(redis, token)
    assert await get_session(redis, token) is None


@pytest.mark.asyncio
async def test_extend_session(redis):
    token, _ = await create_session(redis, user_id=uuid.uuid4(), role="customer", ttl=60)
    assert await extend_session(redis, token, ttl=120) is True
    assert await extend_session(redis, "missing", ttl=120) is False

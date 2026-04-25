import pytest

from app.services.passwords import hash_password, verify_password


@pytest.mark.asyncio
async def test_hash_and_verify_round_trip():
    h = await hash_password("hunter2!")
    assert h.startswith("$argon2")
    assert await verify_password("hunter2!", h) is True
    assert await verify_password("wrong", h) is False


@pytest.mark.asyncio
async def test_hashes_are_unique_per_invocation():
    h1 = await hash_password("same")
    h2 = await hash_password("same")
    assert h1 != h2

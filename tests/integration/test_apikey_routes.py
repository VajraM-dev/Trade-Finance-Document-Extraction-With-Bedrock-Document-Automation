import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos import users as users_repo
from app.services.passwords import hash_password


async def _login(client, engine, username="carol", password="StrongPass!1"):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        existing = await users_repo.get_by_username(session, username)
        if existing is None:
            await users_repo.create(
                session,
                username=username,
                email=f"{username}@example.com",
                password_hash=await hash_password(password),
            )
            await session.commit()
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return r.json()["csrf_token"], r.cookies["session_id"]


@pytest.mark.asyncio
async def test_rotate_api_key_returns_plaintext_once_then_masked(app_client, engine):
    csrf, sid = await _login(app_client, engine)
    r = await app_client.post(
        "/api/v1/me/api-key/rotate",
        cookies={"session_id": sid},
        headers={"x-csrf-token": csrf},
    )
    assert r.status_code == 200
    plain = r.json()["api_key"]
    assert len(plain) > 30
    last4 = r.json()["last_four"]
    assert plain.endswith(last4)

    r2 = await app_client.get("/api/v1/me/api-key", cookies={"session_id": sid})
    assert r2.status_code == 200
    body = r2.json()
    assert body["last_four"] == last4
    assert "api_key" not in body

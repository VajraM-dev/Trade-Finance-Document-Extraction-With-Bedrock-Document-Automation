import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos import users as users_repo
from app.services.passwords import hash_password


@pytest.mark.asyncio
async def test_login_logout_flow(app_client, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await users_repo.create(
            session,
            username="alice",
            email="alice@example.com",
            password_hash=await hash_password("StrongPass!1"),
            role="customer",
        )
        await session.commit()

    r = await app_client.post("/api/v1/auth/login", json={"username": "alice", "password": "StrongPass!1"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "alice"
    csrf = body["csrf_token"]
    cookie = r.cookies.get("session_id")
    assert cookie

    r2 = await app_client.get("/api/v1/auth/me", cookies={"session_id": cookie})
    assert r2.status_code == 200

    r3 = await app_client.post(
        "/api/v1/auth/logout",
        cookies={"session_id": cookie},
        headers={"x-csrf-token": csrf},
    )
    assert r3.status_code == 200

    r4 = await app_client.get("/api/v1/auth/me", cookies={"session_id": cookie})
    assert r4.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(app_client, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await users_repo.create(
            session,
            username="bob",
            email="bob@example.com",
            password_hash=await hash_password("Right!"),
        )
        await session.commit()
    r = await app_client.post("/api/v1/auth/login", json={"username": "bob", "password": "wrong"})
    assert r.status_code == 401
    body = r.json()
    assert body["title"] == "invalid credentials"
    assert "request_id" in body

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos import users as users_repo
from app.services.passwords import hash_password


async def _login_admin(client, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await users_repo.create(
            session,
            username="root",
            email="root@example.com",
            password_hash=await hash_password("StrongPass!1"),
            role="admin",
        )
        await session.commit()
    r = await client.post("/api/v1/auth/login", json={"username": "root", "password": "StrongPass!1"})
    return r.json()["csrf_token"], r.cookies["session_id"]


@pytest.mark.asyncio
async def test_admin_dashboard_empty(app_client, engine):
    csrf, sid = await _login_admin(app_client, engine)
    r = await app_client.get("/api/v1/admin/dashboard", cookies={"session_id": sid})
    assert r.status_code == 200
    body = r.json()
    assert body["today"]["jobs"] == 0
    assert body["last_30d"]["jobs"] == 0
    assert body["by_doc_type"] == {}


@pytest.mark.asyncio
async def test_admin_user_lifecycle(app_client, engine):
    csrf, sid = await _login_admin(app_client, engine)
    r = await app_client.post(
        "/api/v1/admin/users",
        cookies={"session_id": sid},
        headers={"x-csrf-token": csrf},
        json={
            "username": "frank",
            "email": "frank@example.com",
            "password": "StrongPass!1",
            "role": "customer",
        },
    )
    assert r.status_code == 201
    user_id = r.json()["id"]

    r2 = await app_client.patch(
        f"/api/v1/admin/users/{user_id}",
        cookies={"session_id": sid},
        headers={"x-csrf-token": csrf},
        json={"status": "suspended"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "suspended"

    r3 = await app_client.delete(
        f"/api/v1/admin/users/{user_id}",
        cookies={"session_id": sid},
        headers={"x-csrf-token": csrf},
    )
    assert r3.status_code == 204


@pytest.mark.asyncio
async def test_customer_cannot_access_admin(app_client, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await users_repo.create(
            session,
            username="grace",
            email="grace@example.com",
            password_hash=await hash_password("StrongPass!1"),
            role="customer",
        )
        await session.commit()
    r = await app_client.post("/api/v1/auth/login", json={"username": "grace", "password": "StrongPass!1"})
    sid = r.cookies["session_id"]
    r2 = await app_client.get("/api/v1/admin/dashboard", cookies={"session_id": sid})
    assert r2.status_code == 403

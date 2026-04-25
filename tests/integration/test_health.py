import pytest


@pytest.mark.asyncio
async def test_healthz(app_client):
    r = await app_client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz(app_client):
    r = await app_client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["postgres"] is True
    assert body["checks"]["redis"] is True

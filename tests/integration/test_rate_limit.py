import pytest


@pytest.mark.asyncio
async def test_login_ip_rate_limit_returns_429(app_client):
    last = None
    for _ in range(12):
        last = await app_client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "x"}
        )
    assert last is not None
    assert last.status_code == 429
    assert "Retry-After" in last.headers
    body = last.json()
    assert body["title"] == "rate limit exceeded"

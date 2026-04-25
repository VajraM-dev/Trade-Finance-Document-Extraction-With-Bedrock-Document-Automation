import io
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos import api_keys as api_keys_repo
from app.repos import users as users_repo
from app.services.apikeys import compute_lookup_hash, encrypt_key, generate_key, last_four
from app.services.passwords import hash_password
from app.settings import get_settings

PDF = b"%PDF-1.4\n%fake\n" + b"\x00" * 1024


@pytest.mark.asyncio
async def test_upload_creates_queued_job(app_client, engine):
    """Upload a PDF; expect 202, DB row with status=queued, and a preview URL.

    moto mock_aws does not support aioboto3 (async botocore) so we patch the
    two async S3 helpers directly.
    """
    settings = get_settings()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await users_repo.create(
            session,
            username="dave",
            email="dave@example.com",
            password_hash=await hash_password("StrongPass!1"),
        )
        key = generate_key()
        h = compute_lookup_hash(settings.server_pepper.get_secret_value().encode(), key)
        ct = encrypt_key(settings.fernet_key.get_secret_value().encode(), key)
        await api_keys_repo.create(
            session, user_id=user.id, key_lookup_hash=h, key_ciphertext=ct, last_four=last_four(key)
        )
        await session.commit()
        api_key = key

    with (
        patch("app.routes.jobs.upload_stream", new_callable=AsyncMock) as mock_upload,
        patch(
            "app.routes.jobs.presigned_get_url",
            new_callable=AsyncMock,
            return_value="https://s3.example.com/presigned",
        ),
    ):
        r = await app_client.post(
            "/api/v1/jobs",
            headers={"x-api-key": api_key},
            files=[("files", ("doc.pdf", io.BytesIO(PDF), "application/pdf"))],
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert len(body["jobs"]) == 1
        job_id = body["jobs"][0]["job_id"]
        assert mock_upload.called

        r2 = await app_client.get(f"/api/v1/jobs/{job_id}", headers={"x-api-key": api_key})
        assert r2.status_code == 200
        detail = r2.json()
        assert detail["status"] == "queued"
        assert detail["original_filename"] == "doc.pdf"

        r3 = await app_client.get(f"/api/v1/jobs/{job_id}/preview", headers={"x-api-key": api_key})
        assert r3.status_code == 200
        assert r3.json()["url"].startswith("https://")


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_type(app_client, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await users_repo.create(
            session,
            username="eve",
            email="eve@example.com",
            password_hash=await hash_password("StrongPass!1"),
        )
        from app.repos import api_keys as api_keys_repo
        from app.services.apikeys import compute_lookup_hash, encrypt_key, generate_key, last_four
        from app.settings import get_settings
        settings = get_settings()
        key = generate_key()
        h = compute_lookup_hash(settings.server_pepper.get_secret_value().encode(), key)
        ct = encrypt_key(settings.fernet_key.get_secret_value().encode(), key)
        await api_keys_repo.create(
            session, user_id=user.id, key_lookup_hash=h, key_ciphertext=ct, last_four=last_four(key)
        )
        await session.commit()
        api_key = key

    r = await app_client.post(
        "/api/v1/jobs",
        headers={"x-api-key": api_key},
        files=[("files", ("data.bin", io.BytesIO(b"junkdata"), "application/octet-stream"))],
    )
    assert r.status_code == 415

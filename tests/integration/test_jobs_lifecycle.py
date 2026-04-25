import io
import uuid

import boto3
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos import api_keys as api_keys_repo
from app.repos import users as users_repo
from app.services.apikeys import compute_lookup_hash, encrypt_key, generate_key, last_four
from app.services.passwords import hash_password
from app.settings import get_settings
from tests._fakes.bda import FakeBdaState, make_fake_modules

PDF = b"%PDF-1.4\n%fake\n" + b"\x00" * 256


def _patch_upload_stream(monkeypatch):
    """Replace aioboto3-backed upload_stream with a sync boto3 put_object so it
    works under moto's mock_aws (which does not intercept aiobotocore reliably).
    """

    async def fake_upload_stream(settings, *, bucket, key, body, content_type):
        data = body.read() if hasattr(body, "read") else body
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

    monkeypatch.setattr("app.routes.jobs.upload_stream", fake_upload_stream)


@pytest.mark.asyncio
async def test_upload_runs_to_success(app_client, engine, s3_buckets, monkeypatch):
    settings = get_settings()
    state = FakeBdaState()
    fake_start, fake_wait, fake_fetch = make_fake_modules(
        state, output_bucket=settings.s3_output_bucket
    )

    monkeypatch.setattr("app.services.jobs_runner.start_invocation", fake_start)
    monkeypatch.setattr("app.services.jobs_runner.wait_for_completion", fake_wait)
    monkeypatch.setattr("app.services.jobs_runner.fetch_and_parse", fake_fetch)
    _patch_upload_stream(monkeypatch)

    captured: dict[str, str] = {}

    def fake_send_task(name, args, queue):
        captured["name"] = name
        captured["job_id"] = args[0]

    monkeypatch.setattr("app.routes.jobs.celery_app.send_task", fake_send_task)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await users_repo.create(
            session,
            username="hank",
            email="hank@example.com",
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

    upload = await app_client.post(
        "/api/v1/jobs",
        headers={"x-api-key": api_key},
        files=[("files", ("doc.pdf", io.BytesIO(PDF), "application/pdf"))],
    )
    assert upload.status_code == 202
    job_id = uuid.UUID(upload.json()["jobs"][0]["job_id"])
    assert captured == {"name": "process_document", "job_id": str(job_id)}

    from app.services.jobs_runner import run_job

    await run_job(job_id=job_id, session_factory=factory, settings=settings)

    detail = await app_client.get(f"/api/v1/jobs/{job_id}", headers={"x-api-key": api_key})
    body = detail.json()
    assert body["status"] == "success"
    assert body["matched_blueprint"] == "bill_of_lading"
    assert body["pages_processed"] == 1
    assert body["extracted_fields"]["fields"]["bol_number"] == "BOL-FAKE-1"
    assert float(body["cost_usd"]) > 0


@pytest.mark.asyncio
async def test_terminal_failure_marks_job_failed(app_client, engine, s3_buckets, monkeypatch):
    from app.bda.poll import BdaTerminalFailure
    from app.services.jobs_runner import run_job

    async def boom_start(*args, **kwargs):
        raise BdaTerminalFailure("ClientError", "blueprint not found")

    monkeypatch.setattr("app.services.jobs_runner.start_invocation", boom_start)
    _patch_upload_stream(monkeypatch)

    settings = get_settings()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await users_repo.create(
            session,
            username="ivy",
            email="ivy@example.com",
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

    monkeypatch.setattr("app.routes.jobs.celery_app.send_task", lambda *a, **k: None)

    upload = await app_client.post(
        "/api/v1/jobs",
        headers={"x-api-key": api_key},
        files=[("files", ("doc.pdf", io.BytesIO(PDF), "application/pdf"))],
    )
    job_id = uuid.UUID(upload.json()["jobs"][0]["job_id"])
    await run_job(job_id=job_id, session_factory=factory, settings=settings)

    detail = await app_client.get(f"/api/v1/jobs/{job_id}", headers={"x-api-key": api_key})
    body = detail.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "ClientError"
    assert "blueprint not found" in body["error_message"]

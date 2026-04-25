import os
import pytest
from pydantic import ValidationError

from app.settings import Settings


def _required_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql+asyncpg://app:app@localhost:5432/app",
        "REDIS_URL": "redis://localhost:6379/0",
        "RABBITMQ_URL": "amqp://guest:guest@localhost:5672//",
        "SESSION_SECRET": "x" * 32,
        "SERVER_PEPPER": "y" * 32,
        "FERNET_KEY": "FRu6m1Q8uW6Lk5dJYQ_W2i_KGYx3hn_sKDcxGOO2_PE=",
        "AWS_REGION": "us-east-1",
        "S3_INPUT_BUCKET": "in",
        "S3_OUTPUT_BUCKET": "out",
        "BDA_PROJECT_ARN": "arn:aws:bedrock:us-east-1:123:data-automation-project/abc",
        "BDA_PROFILE_ARN": "arn:aws:bedrock:us-east-1:123:data-automation-profile/x",
    }


def test_settings_loads_from_env(monkeypatch):
    for k in ("RUN_MIGRATIONS_ON_STARTUP", "COOKIE_SECURE", "LOG_LEVEL"):
        monkeypatch.delenv(k, raising=False)
    for k, v in _required_env().items():
        monkeypatch.setenv(k, v)
    s = Settings()
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.max_file_size_mb == 10
    assert s.max_batch_size == 10
    assert s.celery_concurrency == 10
    assert s.run_migrations_on_startup is True


def test_settings_missing_required_var(monkeypatch):
    env = _required_env()
    env.pop("SESSION_SECRET")
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValidationError):
        Settings()

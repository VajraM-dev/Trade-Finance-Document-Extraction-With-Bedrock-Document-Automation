from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    database_url: str
    redis_url: str
    rabbitmq_url: str

    session_secret: SecretStr
    server_pepper: SecretStr
    fernet_key: SecretStr

    aws_region: str
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    s3_input_bucket: str
    s3_output_bucket: str

    bda_project_arn: str
    bda_profile_arn: str

    run_migrations_on_startup: bool = True
    log_level: str = "INFO"
    celery_concurrency: int = 10

    rate_limit_upload: str = "60/minute"
    rate_limit_read: str = "300/minute"
    rate_limit_login_ip: str = "10/minute"
    rate_limit_login_user: str = "20/hour"

    max_file_size_mb: int = 10
    max_batch_size: int = 10

    cookie_secure: bool = True
    cookie_domain: str | None = None
    session_ttl_seconds: int = 24 * 3600

    presigned_url_ttl_seconds: int = 300
    apikey_cache_ttl_seconds: int = 60

    bda_poll_max_seconds: int = 300

    cors_origins: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

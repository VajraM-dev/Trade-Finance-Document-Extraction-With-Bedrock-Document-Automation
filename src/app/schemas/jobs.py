import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class JobSummary(BaseModel):
    id: uuid.UUID
    status: str
    matched_blueprint: str | None
    original_filename: str
    file_size_bytes: int
    pages_processed: int | None
    cost_usd: Decimal | None
    created_at: datetime
    completed_at: datetime | None


class JobDetail(JobSummary):
    extracted_fields: dict[str, Any] | None
    error_code: str | None
    error_message: str | None


class JobCreatedItem(BaseModel):
    job_id: uuid.UUID
    status_url: str


class JobCreatedResponse(BaseModel):
    jobs: list[JobCreatedItem]


class PreviewResponse(BaseModel):
    url: str
    expires_in: int


class UsageBucket(BaseModel):
    jobs: int
    pages: int
    cost_usd: float


class UsageMeResponse(BaseModel):
    today: UsageBucket
    last_7d: UsageBucket
    last_30d: UsageBucket
    total: UsageBucket

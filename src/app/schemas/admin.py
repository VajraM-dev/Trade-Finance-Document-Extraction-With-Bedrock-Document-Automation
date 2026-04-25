import uuid

from pydantic import BaseModel


class DashboardBucket(BaseModel):
    jobs: int
    pages: int
    cost_usd: float
    success_rate: float


class DashboardResponse(BaseModel):
    today: DashboardBucket
    last_7d: DashboardBucket
    last_30d: DashboardBucket
    by_doc_type: dict[str, int]


class AuditEntry(BaseModel):
    id: int
    actor_user_id: uuid.UUID | None
    action: str
    target_user_id: uuid.UUID | None
    metadata: dict
    ip: str | None
    user_agent: str | None
    created_at: str

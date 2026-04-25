from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.auth import Principal, require_api_key_or_session
from app.deps.db import get_session
from app.deps.ratelimit import rate_limit
from app.repos import jobs as jobs_repo
from app.schemas.jobs import UsageBucket, UsageMeResponse

router = APIRouter(prefix="/usage", tags=["usage"])


def _bucket_dict_to_model(d: dict) -> UsageBucket:
    return UsageBucket(jobs=d["jobs"], pages=d["pages"], cost_usd=d["cost_usd"])


@router.get("/me", dependencies=[Depends(rate_limit("300/minute", scope="default"))])
async def usage_me(
    p: Principal = Depends(require_api_key_or_session),
    db: AsyncSession = Depends(get_session),
) -> UsageMeResponse:
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return UsageMeResponse(
        today=_bucket_dict_to_model(await jobs_repo.aggregate_for_user(db, p.user_id, today)),
        last_7d=_bucket_dict_to_model(
            await jobs_repo.aggregate_for_user(db, p.user_id, now - timedelta(days=7))
        ),
        last_30d=_bucket_dict_to_model(
            await jobs_repo.aggregate_for_user(db, p.user_id, now - timedelta(days=30))
        ),
        total=_bucket_dict_to_model(
            await jobs_repo.aggregate_for_user(db, p.user_id, datetime(1970, 1, 1, tzinfo=timezone.utc))
        ),
    )

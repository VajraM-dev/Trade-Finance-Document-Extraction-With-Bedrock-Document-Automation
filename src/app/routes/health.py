from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.deps.db import get_session
from app.deps.redis import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(
    request: Request,
    db=Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    checks: dict[str, bool] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False
    try:
        await redis.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    healthy = all(checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )

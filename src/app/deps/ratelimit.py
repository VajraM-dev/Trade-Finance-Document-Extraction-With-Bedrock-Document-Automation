from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, Request
from limits import parse
from limits.aio.storage import RedisStorage
from limits.aio.strategies import MovingWindowRateLimiter

from app.errors import RateLimitedError
from app.settings import Settings, get_settings

# Module-level cache: one limiter per redis URL
_limiters: dict[str, MovingWindowRateLimiter] = {}


def _key_for(request: Request) -> str:
    p = getattr(request.state, "principal", None)
    if p is not None:
        if p.via == "api_key":
            return f"apikey:{p.api_key_id}"
        return f"user:{p.user_id}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _get_limiter(redis_url: str) -> MovingWindowRateLimiter:
    if redis_url not in _limiters:
        storage = RedisStorage(redis_url)
        _limiters[redis_url] = MovingWindowRateLimiter(storage)
    return _limiters[redis_url]


def rate_limit(spec: str, *, scope: str) -> Callable[..., Coroutine[Any, Any, None]]:
    parsed = parse(spec)

    async def _dep(request: Request, settings: Settings = Depends(get_settings)) -> None:
        limiter = _get_limiter(settings.redis_url)
        key = _key_for(request)
        if not await limiter.hit(parsed, scope, key):
            window = await limiter.get_window_stats(parsed, scope, key)
            retry = max(int(window.reset_time - window.remaining), 1)
            raise RateLimitedError(
                "rate limit exceeded",
                detail=f"limit={spec} scope={scope}",
                headers={"Retry-After": str(retry)},
            )

    return _dep

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger("http")


class LogContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = getattr(request.state, "request_id", None)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=rid,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        log.debug("request.started")
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request.failed")
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        log.info("request.completed", status_code=response.status_code, duration_ms=duration_ms)
        return response

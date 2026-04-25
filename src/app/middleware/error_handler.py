import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import AppError, error_to_problem

log = structlog.get_logger("errors")


def _problem_response(status: int, body: dict, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app(request: Request, exc: AppError) -> JSONResponse:
        rid = getattr(request.state, "request_id", "")
        log.warning("error.app", title=exc.title, status=exc.status, detail=exc.detail)
        return _problem_response(exc.status, error_to_problem(exc, request_id=rid), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = getattr(request.state, "request_id", "")
        body = {
            "type": "about:blank",
            "title": "validation error",
            "status": 422,
            "detail": str(exc.errors()),
            "request_id": rid,
        }
        return _problem_response(422, body)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = getattr(request.state, "request_id", "")
        body = {
            "type": "about:blank",
            "title": exc.detail or "http error",
            "status": exc.status_code,
            "detail": None,
            "request_id": rid,
        }
        return _problem_response(exc.status_code, body)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", "")
        log.exception("error.unhandled")
        body = {
            "type": "about:blank",
            "title": "internal server error",
            "status": 500,
            "detail": None,
            "request_id": rid,
        }
        return _problem_response(500, body)

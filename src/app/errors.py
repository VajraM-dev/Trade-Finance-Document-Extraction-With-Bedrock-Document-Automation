from typing import Any


class AppError(Exception):
    status: int = 500

    def __init__(self, title: str, *, detail: str | None = None, headers: dict[str, str] | None = None):
        super().__init__(title)
        self.title = title
        self.detail = detail
        self.headers = headers or {}


class BadRequestError(AppError):
    status = 400


class UnauthorizedError(AppError):
    status = 401


class ForbiddenError(AppError):
    status = 403


class NotFoundError(AppError):
    status = 404


class ConflictError(AppError):
    status = 409


class PayloadTooLargeError(AppError):
    status = 413


class UnsupportedMediaTypeError(AppError):
    status = 415


class RateLimitedError(AppError):
    status = 429


def error_to_problem(err: AppError, *, request_id: str) -> dict[str, Any]:
    return {
        "type": "about:blank",
        "title": err.title,
        "status": err.status,
        "detail": err.detail,
        "request_id": request_id,
    }

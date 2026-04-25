from app.errors import (
    AppError,
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
    error_to_problem,
)


def test_error_to_problem_includes_request_id():
    err = NotFoundError("job not found", detail="job_id=abc")
    problem = error_to_problem(err, request_id="req-123")
    assert problem["status"] == 404
    assert problem["title"] == "job not found"
    assert problem["detail"] == "job_id=abc"
    assert problem["request_id"] == "req-123"
    assert problem["type"] == "about:blank"


def test_status_codes_per_class():
    assert BadRequestError("x").status == 400
    assert UnauthorizedError("x").status == 401
    assert ForbiddenError("x").status == 403
    assert NotFoundError("x").status == 404
    assert RateLimitedError("x").status == 429


def test_app_error_default_status():
    assert AppError("x").status == 500

import hmac

from app.errors import ForbiddenError


def verify_csrf(expected: str, supplied: str | None) -> None:
    if not supplied or not hmac.compare_digest(expected, supplied):
        raise ForbiddenError("csrf token invalid")

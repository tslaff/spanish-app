import hmac

from fastapi import Request

from .config import settings


def is_authenticated(request: Request) -> bool:
    return request.session.get("auth") is True


def check_password(candidate: str) -> bool:
    # Constant-time comparison to avoid leaking the password via timing.
    return hmac.compare_digest(candidate, settings.password)

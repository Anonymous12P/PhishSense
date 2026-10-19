"""Reusable password hashing and JWT access-token utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.settings import get_settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a one-way bcrypt hash for a plaintext password."""
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a previously stored bcrypt hash."""
    return password_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any]) -> str:
    """Encode a signed JWT with the configured access-token expiration."""
    settings = get_settings()
    if not settings.secret_key:
        raise ValueError("SECRET_KEY must be configured to create access tokens.")

    claims = data.copy()
    claims["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode a JWT, validating its signature and expiration claim.

    Raises the ``python-jose`` JWT exceptions for malformed, invalid, or
    expired tokens. A missing signing key is reported as a configuration error.
    """
    settings = get_settings()
    if not settings.secret_key:
        raise ValueError("SECRET_KEY must be configured to decode access tokens.")

    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"require_exp": True},
    )
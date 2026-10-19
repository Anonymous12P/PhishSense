"""Pydantic schemas for authentication requests and token responses."""

from pydantic import Field

from app.schemas.base import SchemaBase


class LoginRequest(SchemaBase):
    """Credentials submitted to authenticate a user."""

    username: str = Field(min_length=3, max_length=50, description="User's username.")
    password: str = Field(min_length=1, description="User's plaintext password.")


class Token(SchemaBase):
    """Bearer access token returned after successful authentication."""

    access_token: str = Field(description="Signed JWT access token.")
    token_type: str = Field(default="bearer", description="Token type for authorization.")


class TokenPayload(SchemaBase):
    """Core subject and expiration claims carried by an access token."""

    sub: str = Field(description="Subject identifying the token's owner.")
    exp: int = Field(description="Token expiration as a Unix timestamp.")
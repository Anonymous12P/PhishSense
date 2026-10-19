from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import SchemaBase


class UserBase(SchemaBase):
    """Shared user fields used by create, update, and read schemas."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    """Fields required to create a user."""

    password: str = Field(min_length=8)


class UserRead(UserBase):
    """Public user representation returned by the API."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(SchemaBase):
    """Optional fields accepted when updating a user."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=8)
    is_active: bool | None = None

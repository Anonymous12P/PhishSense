"""Pydantic schemas for URL scan requests."""

from datetime import datetime

from pydantic import Field

from app.schemas.base import SchemaBase


class ScanCreate(SchemaBase):
    """Fields required to persist a scan result for the current user."""

    url: str = Field(min_length=1, max_length=2048)
    prediction: str = Field(min_length=1, max_length=32)
    confidence: float
    risk_score: float


class ScanRead(SchemaBase):
    """Public representation of a persisted scan result."""

    id: int
    url: str
    prediction: str
    confidence: float
    risk_score: float
    user_id: int
    created_at: datetime
    updated_at: datetime
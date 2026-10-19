from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import TimestampModel

if TYPE_CHECKING:
    from app.models.scan import Scan


class User(TimestampModel):
    """Represent an authenticated PhishSense application user."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    """Unique, indexed login name used to identify the user."""

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    """Unique, indexed email address used for user communication and lookup."""

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    """One-way password hash used to verify credentials without storing a password."""

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    """Display name for the user."""

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    """Flag indicating whether the user is allowed to access the application."""

    scans: Mapped[list["Scan"]] = relationship(
        "Scan",
        back_populates="user",
    )

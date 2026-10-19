from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import TimestampModel

if TYPE_CHECKING:
    from app.models.user import User


class Scan(TimestampModel):
    """Represent a URL scan and its phishing risk prediction."""

    __tablename__ = "scans"

    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    prediction: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="scans",
    )
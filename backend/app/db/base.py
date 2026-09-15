from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy declarative models."""


# Models will inherit from Base when the application's data layer is added.

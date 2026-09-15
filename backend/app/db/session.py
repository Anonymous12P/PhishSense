from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings


# Load the validated application settings so the engine uses DATABASE_URL.
settings = get_settings()
if not settings.database_url:
    raise RuntimeError(
        "DATABASE_URL must be configured before the database session is used."
    )


# Create one application-wide engine with connection health checks enabled.
# DATABASE_URL should use the psycopg dialect, for example:
# postgresql+psycopg://user:password@host:5432/database
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


# Create SQLAlchemy 2.0 sessions without implicit commits or expiration.
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

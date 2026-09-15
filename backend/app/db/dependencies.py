from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        # Yield lets FastAPI provide this session to an endpoint and resume
        # execution afterward so dependency cleanup can run.
        yield db
    finally:
        # Always release the session and return its connection to the pool,
        # including when the endpoint raises an exception.
        db.close()

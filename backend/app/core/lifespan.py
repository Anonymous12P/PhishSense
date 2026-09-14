from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.core.logger import setup_logging


@asynccontextmanager
async def lifespan(_: object) -> AsyncIterator[None]:
    """Manage application startup and shutdown tasks for FastAPI."""
    # Configure logging before yielding control to the running application.
    logger = setup_logging()
    logger.info("Starting PhishSense API...")

    try:
        yield
    finally:
        # Always log shutdown, including when the application stops on error.
        logger.info("Stopping PhishSense API...")
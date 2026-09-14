from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.settings import get_settings


# Load configuration once so application metadata and runtime behavior use the
# same validated settings throughout the process.
settings = get_settings()


# Configure the application shell. The documentation URLs remain enabled for
# now and can be made environment-dependent when deployment settings mature.
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    description="An API for detecting and analyzing phishing threats.",
    contact={
        "name": "PhishSense Team",
        "email": "support@phishsense.example",
    },
    license_info={
        "name": "Apache 2.0",
        "identifier": "Apache-2.0",
    },
)


# Register one consistent JSON error contract for all application failures.
register_exception_handlers(app)


# Register versioned API routes separately from application-level endpoints.
app.include_router(v1_router)


# Provide a lightweight endpoint for confirming that the API is running.
@app.get("/")
def root():
    return {
        "application": "PhishSense",
        "status": "running",
        "version": settings.app_version,
    }

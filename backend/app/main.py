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
    summary="Phishing threat detection and analysis API",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    description=(
        "PhishSense provides APIs for detecting, analyzing, and monitoring "
        "phishing threats."
    ),
    contact={
        "name": "PhishSense Team",
        "email": "support@phishsense.example",
    },
    license_info={
        "name": "Apache 2.0",
        "identifier": "Apache-2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    openapi_tags=[
        {
            "name": "Health",
            "description": "Service health and availability checks.",
        },
        {
            "name": "Authentication",
            "description": "Authentication and access control operations.",
        },
        {
            "name": "Prediction",
            "description": "Phishing threat prediction operations.",
        },
        {
            "name": "Analytics",
            "description": "Threat metrics, trends, and analytical insights.",
        },
    ],
)


# Register one consistent JSON error contract for all application failures.
register_exception_handlers(app)


# Register versioned API routes separately from application-level endpoints.
app.include_router(v1_router)


# Provide a lightweight endpoint for confirming that the API is running.
@app.get(
    "/",
    summary="Get API status",
    description="Return the application name, runtime status, and API version.",
    tags=["Health"],
)
def root():
    return {
        "application": "PhishSense",
        "status": "running",
        "version": settings.app_version,
    }

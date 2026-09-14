from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Return the current health status for the PhishSense API."""
    return {
        "status": "healthy",
        "service": "PhishSense API",
        "version": "1.0.0",
    }
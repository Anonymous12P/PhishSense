from fastapi import APIRouter

from app.api.v1.health import router as health_router


# Keep all v1 endpoints behind one version prefix so future API versions can
# evolve independently without changing existing client URLs.
router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
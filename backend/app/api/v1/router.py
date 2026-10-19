from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.scan import router as scan_router
from app.api.v1.health import router as health_router


# Keep all v1 endpoints behind one version prefix so future API versions can
# evolve independently without changing existing client URLs.
router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(scan_router)
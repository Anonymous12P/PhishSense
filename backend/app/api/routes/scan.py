"""Authenticated endpoints for managing URL scans."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.dependencies import get_db
from app.models.scan import Scan
from app.models.user import User
from app.repositories.scan_repository import ScanRepository
from app.schemas.scan import ScanCreate, ScanRead
from app.services.scan_service import ScanService


router = APIRouter(prefix="/scans", tags=["Scans"])


def get_scan_service(db: Session = Depends(get_db)) -> ScanService:
    """Build a scan service using the request-scoped database session."""
    return ScanService(ScanRepository(db))


@router.post(
    "",
    response_model=ScanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scan",
    description="Create and store a website scan for the authenticated user.",
)
def create_scan(
    scan_data: ScanCreate,
    current_user: User = Depends(get_current_user),
    service: ScanService = Depends(get_scan_service),
) -> ScanRead:
    """Create a scan owned by the authenticated user."""
    scan = service.create_scan(current_user, scan_data)
    return ScanRead.model_validate(scan)


@router.get(
    "",
    response_model=list[ScanRead],
    status_code=status.HTTP_200_OK,
    summary="List scans",
    description="Return a paginated list of scans owned by the authenticated user.",
)
def list_scans(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    current_user: User = Depends(get_current_user),
    service: ScanService = Depends(get_scan_service),
) -> list[ScanRead]:
    """Return the authenticated user's paginated scan history."""
    scans = service.list_scans(current_user, skip=skip, limit=limit)
    return [ScanRead.model_validate(scan) for scan in scans]


@router.get(
    "/{scan_id}",
    response_model=ScanRead,
    status_code=status.HTTP_200_OK,
    summary="Get a scan",
    description="Return a scan owned by the authenticated user.",
)
def get_scan(
    scan_id: int,
    current_user: User = Depends(get_current_user),
    service: ScanService = Depends(get_scan_service),
) -> ScanRead:
    """Return a scan after the service verifies ownership."""
    try:
        scan: Scan = service.get_scan(current_user, scan_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return ScanRead.model_validate(scan)


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a scan",
    description="Delete a scan owned by the authenticated user.",
)
def delete_scan(
    scan_id: int,
    current_user: User = Depends(get_current_user),
    service: ScanService = Depends(get_scan_service),
) -> Response:
    """Delete a scan after the service verifies ownership."""
    try:
        service.delete_scan(current_user, scan_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
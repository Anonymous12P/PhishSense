"""Business operations for creating and managing user scans."""

from app.models.scan import Scan
from app.models.user import User
from app.repositories.scan_repository import ScanRepository
from app.schemas.scan import ScanCreate


class ScanService:
    """Apply ownership rules and coordinate Scan persistence operations."""

    def __init__(self, repository: ScanRepository) -> None:
        self.repository = repository

    def create_scan(self, current_user: User, scan_data: ScanCreate) -> Scan:
        """Create and persist a scan associated with the current user."""
        scan = Scan(
            url=scan_data.url,
            prediction=scan_data.prediction,
            confidence=scan_data.confidence,
            risk_score=scan_data.risk_score,
            user_id=current_user.id,
        )
        return self.repository.create(scan)

    def get_scan(self, current_user: User, scan_id: int) -> Scan:
        """Return an existing scan after verifying that the user owns it."""
        scan = self.repository.get_by_id(scan_id)
        if scan is None:
            raise ValueError("Scan not found")
        if scan.user_id != current_user.id:
            raise PermissionError("User does not own this scan")
        return scan

    def list_scans(
        self,
        current_user: User,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Scan]:
        """Return a paginated history containing only the user's scans."""
        return self.repository.list_by_user(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )

    def delete_scan(self, current_user: User, scan_id: int) -> None:
        """Delete an existing scan after verifying that the user owns it."""
        scan = self.get_scan(current_user, scan_id)
        self.repository.delete(scan)